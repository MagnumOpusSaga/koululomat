import os
from pathlib import Path
"""Moottori: kunta -> löytö -> luku -> yhdistäminen -> tarkistukset -> tulos (tietomallin muoto)."""
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from . import fetch
from .adapters import attachment_links, classify_source, dynasty_siblings, read, same_site
from .cal import week_of
from .checks import confidence, plausibility, run_checks
from .discover import discover
from .extract_fi import extract
from . import ai_reader
from .discover import AGGREGATOR_RX, CONTENT_KW, NONSCHOOL_RX, SHARE_RX, URL_HIT

AI_MAX_PER_MUN = 4
AI_EXTRA_STRONG = 3  # lisäkutsut vahvoille ehdokkaille (URL kertoo työ-/loma-ajoista), ettei roskasivu vie kiintiötä
AI_SKIP = re.compile(r"opisto|uutinen|uutiset|/news|/aktuellt|feedback|formular|anmalan|ilmoittaut|lomake|blankett|kerho|harrastus|byggnad|rakennus|kaava|planlagg", re.I)

KIND_RANK = {"paatos": 0, "lovdata": 0, "forskrift": 0, "kuntasivu": 1, "liite": 2, "wilma": 3, "koulu": 4, "muu": 5}
MAIN_FIELDS = ("start", "syys", "joulu", "talvi", "end")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def about_this_municipality(doc, mun, home) -> bool:
    if home and same_site(doc["url"], home):
        return True
    names = [mun["fi"]] + ([mun["sv"]] if mun.get("sv") else [])
    stem = [n[:-1] if len(n) > 5 else n for n in names]  # taivutusmuodot (Kuopion, Oulun)
    asc = lambda x: x.lower().replace("ä", "a").replace("ö", "o").replace("å", "a")
    # url ilman ääkkösiä (peda.net/merijarvi, larsmo.fi) ja nimi ilman ääkkösiä
    return any(re.search(re.escape(s), doc["text"][:20000], re.I) for s in stem) or \
        any(asc(s) in asc(doc["url"]) for s in stem)


FORM_ESI = re.compile(r"varhaiskasvat|esiopetu|paivakoti|päiväkoti|förskol|smabarn|småbarn", re.I)
FORM_LUKIO = re.compile(r"lukio|gymnasi", re.I)
FORM_OTHER = re.compile(r"(?<![a-zäöå])[a-zäöå]*-?opisto\b|tredu|ammatti|ammattiopisto|kansalaisopisto|musiikkiopisto|aikuis|amk|yliopisto|medborgarinstitut|arbis|taidekoulu|kuvataidekoulu", re.I)
FORM_PERUS = re.compile(r"(?<![a-zäöå])opetuksen|perusopetu|koulujen|grundskol|grundläggande|skolornas|peruskoul", re.I)


def school_form(doc) -> str:
    # vain viimeinen polun osa + otsikko (koko polku sisältää usein "kasvatus-ja-opetus")
    last = [p for p in urlparse(doc["url"]).path.split("/") if p][-1:] or [""]
    s = last[0] + " " + (doc.get("title") or "")
    if FORM_PERUS.search(s):
        return "perus"
    segs = [p.lower() for p in urlparse(doc["url"]).path.split("/") if p]
    if any(re.fullmatch(r"varhaiskasvatus|esiopetus|smabarnspedagogik|forskoleundervisning|paivakodit", x) for x in segs[:-1]):
        return "esi"
    if any(re.fullmatch(r"lukio(t|koulutus)?|gymnasi(er|um)", x) for x in segs[:-1]):
        return "lukio"
    if FORM_OTHER.search(s):
        return "muu"
    if FORM_LUKIO.search(s):
        return "lukio"
    if FORM_ESI.search(s):
        return "esi"
    return "perus"


def process(mun: dict, years=("2026-2027", "2027-2028"), country="fi", max_docs=14, monitor=None, extra_urls=()):
    log = []
    ai_calls = [0]
    ai_log = []
    disc = discover(mun, log=log)
    cands = [c[0] for c in disc["candidates"]] + list(extra_urls)
    queue = list(dict.fromkeys(list(extra_urls) + cands))[:max_docs]
    obsv = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # variant -> year -> field -> [...]
    fobs = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))  # variant -> form -> year -> field -> [...]
    sources = []
    flags_by_url = {}
    read_urls = set()
    i = 0
    while i < len(queue) and i < max_docs + 10:
        url = queue[i]
        i += 1
        if url in read_urls:
            continue
        read_urls.add(url)
        m = fetch.get(url)
        doc = read(m)
        if not doc.get("text"):
            sources.append({"url": url, "error": doc.get("error")})
            continue
        if os.environ.get("DUMP_DOCS"):  # vianetsintä: talleta luettu teksti
            dd = Path("out_all/dump") / mun["id"]
            dd.mkdir(parents=True, exist_ok=True)
            (dd / f"{i:02d}.txt").write_text(f"URL: {doc['url']}\nFLAGS: {doc.get('flags')}\n\n" + doc["text"][:20000], encoding="utf-8")
        if AGGREGATOR_RX.search(doc["url"]) or AGGREGATOR_RX.search(url):
            sources.append({"url": doc["url"], "skipped": "kooste, ei kunnan oma lähde"})
            continue
        if NONSCHOOL_RX.search(doc["url"]) or NONSCHOOL_RX.search(doc.get("title") or ""):
            sources.append({"url": doc["url"], "skipped": "opisto/harrastus"})
            continue
        if not about_this_municipality(doc, mun, disc["home"]):
            sources.append({"url": url, "skipped": "toinen kunta"})
            continue
        kind = classify_source(doc["url"])
        form = school_form(doc)
        if form == "muu":
            sources.append({"url": doc["url"], "skipped": f"koulumuoto {form}"})
            continue
        h = fetch.content_hash(doc["text"])
        change = monitor.check(doc["url"], h, now()) if monitor else None
        variant = doc_variant(doc)
        obs = obsv[variant]
        res = extract(doc["text"], want_years=set(years), default_form=form)
        reader = "rules"
        # kaksipalstainen ruudukko: syys keväällä ja talvi syksyllä = palstat sekaisin -> päivät ovat todennäköisesti
        # myös väärin (Ilmajoki: talvi 5.10.). Ei vaihdeta, vaan merkitään epäjärkeväksi -> tekoäly lukee kuvana.
        swapped_grid = any("syys" in r and "talvi" in r and 6 <= week_of(date.fromisoformat(r["syys"]["start"])) <= 14
                           and 38 <= week_of(date.fromisoformat(r["talvi"]["start"])) <= 45 for r in res.values())
        incomplete = not any(all(k in r for k in ("syys", "joulu", "talvi")) for r in res.values())
        # järkevyyspoikkeama (esim. talviloma lokakuussa, Ilmajoki: kaksipalstainen ruudukko) -> tekoäly lukee uudelleen
        implausible = any(plausibility(country, y, r) for y, r in res.items()) or swapped_grid
        has_words = bool(CONTENT_KW.search(doc["text"]))
        looks_calendar = has_words or bool(URL_HIT.search(doc["url"]))  # värikoodattu ruudukko: ei lomasanoja tekstissä
        strong = bool(URL_HIT.search(doc["url"])) and not AI_SKIP.search(doc["url"])
        budget = AI_MAX_PER_MUN + (AI_EXTRA_STRONG if strong else 0)
        rules_good = not incomplete and not implausible
        if ai_reader.available() and ai_calls[0] < budget and (doc["flags"].get("grid") or incomplete or implausible) \
                and looks_calendar and not AI_SKIP.search(doc["url"]) and re.search(r"20(26|27|28)", doc["text"] + doc["url"]):
            is_pdf = doc["format"] in ("pdf", "pdf_scan")
            imgs = ai_reader.pdf_pages_png(m["path"], max_pages=3) if is_pdf and (doc["flags"].get("grid") or not has_words or implausible) else []
            ai = ai_reader.read_with_ai(mun["fi"], doc["text"], images=imgs, hard=bool(imgs), years=years, key=fetch.content_hash(doc["text"]))
            ai_calls[0] += 1
            ai_res = ai_reader.to_records(ai)
            ai_ok = any(all(k in r for k in ("syys", "joulu", "talvi")) for r in ai_res.values())
            ai_clean = ai_ok and not any(plausibility(country, y, r) for y, r in ai_res.items())
            # sääntölukijan täydellinen ja järkevä tulos voittaa (Kerava: tekoäly palautti vain alun ja lopun)
            if ai_ok and (incomplete or implausible or (ai_clean and doc["flags"].get("grid") and not rules_good)):
                res, reader = ai_res, "ai"
            lv = (ai or {}).get("lukuvuodet") or {}
            ai_log.append({"url": doc["url"], "ok": ai_ok, "clean": ai_clean, "images": len(imgs), "used": reader == "ai",
                           "error": (ai or {}).get("error"), "kunta_oikein": (ai or {}).get("kunta_oikein"),
                           "seen": {y: [k for k in ("koulumuoto", "syysloma", "joululoma", "talviloma") if isinstance(v, dict) and v.get(k)]
                                    + ([str(v.get("koulumuoto"))] if isinstance(v, dict) else []) for y, v in lv.items()}})
        # esiopetus ja lukio samasta dokumentista (vain säännöt; näytetään kuntasivun välilehdillä)
        for F in ("esi", "lukio"):
            for y, r in extract(doc["text"], want_years=set(years), default_form=form, want_form=F).items():
                for f, v in r.items():
                    if f in MAIN_FIELDS + ("term1_end", "term2_start") and isinstance(v, dict) and not v.get("derived"):
                        fobs[variant][F][y][f].append(((v["start"], v["end"]), doc["url"], v["quote"]))
        src = {"url": doc["url"], "kind": kind, "format": doc["format"], "flags": doc["flags"],
               "hash": h[:16], "change": change, "variant": variant, "reader": reader, "years": sorted(res.keys())}
        sources.append(src)
        flags_by_url[doc["url"]] = doc["flags"]
        for y, r in res.items():
            for f, v in r.items():
                if f in MAIN_FIELDS + ("term1", "term2", "paasiainen") and isinstance(v, dict):
                    obs[y][f].append(((v["start"], v["end"]), doc["url"], kind, v["quote"], v.get("derived", False)))
                elif f in ("saturday", "free"):
                    for x in v:
                        obs[y][f].append(((x["start"], x["end"]), doc["url"], kind, x["quote"], False))
                elif f == "days_doc":
                    obs[y]["days_doc"].append((v, doc["url"], kind, "", False))
        # seuraa liitteet ja Dynasty-sisaret
        if doc["format"] == "html" or doc["flags"].get("attachment_only"):
            for a in attachment_links(doc) + dynasty_siblings(doc["url"]):
                if a not in read_urls and a not in queue and not SHARE_RX.search(a):
                    queue.insert(i, a)
    out = {"municipality": mun["id"], "name": mun["fi"], "home": disc["home"],
           "pages_crawled": disc["pages_crawled"], "n_candidates": len(disc["candidates"]),
           "sources": sources, "ai": ai_log, "log": log if os.environ.get("DUMP_DOCS") else None, "years": {}}
    primary = "fi" if obsv.get("fi") else ("sv" if obsv.get("sv") else "fi")
    out["variant"] = primary
    out["years"] = merge_years(obsv.get(primary, {}), years, country, flags_by_url)
    out["variants"] = {v: merge_years(o, years, country, flags_by_url) for v, o in obsv.items() if v != primary}
    out["forms"] = merge_forms(fobs.get(primary, {}))
    return out


def doc_variant(doc) -> str:
    u = doc["url"].lower()
    if re.search(r"/sv/|/sv-|/svenska|/pa-svenska|svenska-", u):
        return "sv"
    sv = len(re.findall(r"höstlov|jullov|sportlov|läsår|skolor", doc["text"], re.I))
    fi = len(re.findall(r"syysloma|joululoma|talviloma|hiihtoloma|lukuvuo|koulu", doc["text"], re.I))
    return "sv" if sv > fi else "fi"


def _doc_records(obs_y):
    """Havainnot dokumenteittain: url -> {field: {...}} (ei sekoiteta eri dokumenttien kenttiä)."""
    recs = defaultdict(dict)
    for f, lst in obs_y.items():
        for v, u, kind, q, derived in lst:
            if f in ("saturday", "free"):
                recs[u].setdefault(f, []).append({"start": v[0], "end": v[1], "quote": q})
            elif f == "days_doc":
                recs[u]["days_doc"] = v
            elif f not in recs[u]:
                recs[u][f] = {"start": v[0], "end": v[1], "quote": q, "derived": derived}
    return recs


def merge_forms(fo):
    """Esiopetus/lukio: kentän yleisin arvo dokumenteista, lähteet mukaan. -> {form: {year: {field: {...}}}}"""
    out = {}
    for F, ys in fo.items():
        for y, fields in ys.items():
            rec = {}
            for f, lst in fields.items():
                ok = [x for x in lst if not (f in ("syys", "talvi") and (date.fromisoformat(x[0][1]) - date.fromisoformat(x[0][0])).days < 2)
                      and not (f == "joulu" and (date.fromisoformat(x[0][1]) - date.fromisoformat(x[0][0])).days < 5)]
                c = Counter(x[0] for x in ok)
                if not c:
                    continue
                top = c.most_common(2)
                if len(top) > 1 and top[0][1] == top[1][1]:
                    continue  # tasapeli: ei näytetä
                (a, b), n = top[0]
                lst = ok
                srcs = sorted({x[1] for x in lst if x[0] == (a, b)})
                rec[f] = {"start": a, "end": b, "quote": next(x[2] for x in lst if x[0] == (a, b)), "sources": srcs,
                          "conflict": len(c) > 1}
            if sum(1 for f in MAIN_FIELDS if f in rec) >= 2:
                out.setdefault(F, {})[y] = rec
    return out


def merge_years(obs, years, country, flags_by_url):
    """Valitaan YKSI ensisijainen dokumentti (laskenta täsmää, eniten kenttiä, virallisin tyyppi);
    muut dokumentit vain vahvistavat (sama arvo -> toinen lähde) tai kirjataan ristiriidoiksi."""
    out = {}
    for y in years:
        recs = _doc_records(obs.get(y, {}))
        if not recs:
            out[y] = None
            continue
        scored = []
        for u, r in recs.items():
            chk = run_checks(country, y, r)
            nmain = sum(1 for f in MAIN_FIELDS if f in r)
            perus_url = bool(re.search(r"perusopetu|koulujen|peruskoul|grundskol|skolornas", u, re.I))
            scored.append(((chk["days_ok"] is True, nmain >= 4, perus_url, nmain, -KIND_RANK.get(classify_source(u), 9),
                            -len(chk["plausibility"])), u, r, chk))
        scored.sort(key=lambda x: x[0], reverse=True)
        _, pu, merged, chk = scored[0]
        merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in merged.items()}
        field_sources, conflicts = {}, []
        for f in MAIN_FIELDS + ("term1", "term2", "paasiainen"):
            if f not in merged:
                continue
            val = (merged[f]["start"], merged[f]["end"])
            agree = [u for u, r in recs.items() if f in r and (r[f]["start"], r[f]["end"]) == val and not r[f].get("derived")]
            if not merged[f].get("derived") and pu not in agree:
                agree.append(pu)
            merged[f]["sources"] = sorted(set(agree))
            field_sources[f] = merged[f]["sources"]
            other = {(r[f]["start"], r[f]["end"]) for u, r in recs.items() if f in r} - {val}
            if other:
                conflicts.append({f: [{"value": v, "urls": sorted(u for u, r in recs.items() if f in r and (r[f]["start"], r[f]["end"]) == v)} for v in other]})
        used = {pu}
        is_prop = any(flags_by_url.get(u, {}).get("proposal") for u in used)
        official = any(classify_source(u) in ("paatos", "kuntasivu", "lovdata", "liite") for u in used)
        # riippumattomuus: eri lähdetyyppi tai eri palvelin (sama sivu kahdella kielellä ei ole kaksi lähdettä)
        fs = {f: {(classify_source(u), urlparse(u).netloc) for u in field_sources[f]}
              for f in MAIN_FIELDS if f in field_sources}
        out[y] = {"fields": merged, "checks": chk, "conflicts": conflicts, "primary": pu,
                  "status": "ehdotus" if is_prop else "päätetty",
                  "confidence": confidence(fs, is_prop, chk["days_ok"], official,
                                                complete=all(f in merged for f in ("syys", "joulu", "talvi"))
                                                and not chk["plausibility"]),
                  "missing": [f for f in MAIN_FIELDS if f not in merged]}
    return out
