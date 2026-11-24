"""Sääntölukija: suomen- ja ruotsinkielinen teksti -> lukuvuosien työ- ja loma-ajat.

Palauttaa jokaiselle lukuvuodelle kentät + lainauksen jokaiselle luetulle päivälle.
Tekoälylukija (ai_reader.py) käytetään, kun tämä ei löydä tai tarkistukset hylkäävät.
"""
import re
from datetime import date

from .cal import clip_to_weekdays, iso_week_range

DASH = r"[–—‐‑−-]"
FIELDS = {
    "term1": r"syysluku\w*|syyskau(si|den)|syyslukukau\w*|hösttermin\w*",
    "term2": r"kevätluku\w*|kevätkau(si|den)|kevätlukukau\w*|vårtermin\w*",
    "syys": r"syysloma\w*|höstlov\w*|syyslomaviik\w*",
    "joulu": r"joululoma\w*|jullov\w*",
    "talvi": r"talviloma\w*|hiihtoloma\w*|sportlov\w*|vinterlov\w*|talvilomaviik\w*",
    "paasiainen": r"pääsiäisloma\w*|påsklov\w*",
    "term1_end": r"syys(luku)?kauden\s+päättäjäi\w*|joulujuhla\w*|syys(luku)?kausi\s+päättyy|hösttermin(en)?\s+(slutar|avslutas)|sista\s+skoldag(en)?\s+(på|före|inför)\s+(hösten|jul\w*)|höstterminens\s+sista\s+\w*dag",
    "term2_start": r"vårtermin(en)?\s+inleds|kevät(luku)?kausi\s+alkaa|vårtermin(en)?\s+(börjar|startar)",
    "start": r"syy\w{0,2}lukukausi\s+alkaa|koulun\s+alkaminen|hösttermin(en)?\s+inleds|(?<!esi)opetus\s+alkaa|syys(luku)?kausi\s+alkaa|undervisningen\s+börjar|hösttermin(en)?\s+(börjar|startar)|koulu(t|työ|työt)?\s+alka(a|vat)|lukuvuosi\s+alkaa|työt\s+alkavat|skol(an|arbetet)\s+börjar|läsåret\s+börjar|ensimmäinen\s+koulupäivä|första\s+skoldag\w*",
    "end": r"lukuvuoden\s+viimeinen\s+(työ|koulu)päivä|(?<=\d)\s+ja\s+päättyy|(?<=\d)\s+ja\s+päättyvät|kevät(luku)?kausi\s+päättyy|läsårets\s+sista\s+(arbets|skol)dag|vårtermin(en)?\s+(slutar|avslutas)|lukuvuosi\s+päättyy|koulu(t|työ|työt)?\s+päätty(y|vät)|lukuvuoden\s+päät\w*|läsåret\s+(slutar|avslutas)|skolavslutning\w*|viimeinen\s+koulupäivä|sista\s+skoldag\w*|kevätjuhla\w*",
    "saturday": r"lauantai(koulu|työ)?päiv\w*|työlauantai\w*|koulupäivä(nä)?\s+lauantai\w*|lauantaina\s+koulupäivä|lördag(en)?\s+(är\s+)?(en\s+)?skoldag|skoldag\s+lördag\w*|arbetslördag\w*",
    "kesa": r"kesäloma\w*|sommarlov\w*",
    "generic_start": r"(?:^|(?<=\n))[ \t]*alkaa\b",
    "generic_end": r"(?<=\d)\s+och\s+avslutas|(?<![a-zåäö])avslutning(?!\w)|(?:^|(?<=\n))[ \t]*päättyy\b|(?<![a-zäö])lukukausi\s+päättyy",
    "free": r"helatorstain\s+(jälkeinen|jälkeisenä|seuraava)\s+perjantai\w*|helavapaa\w*|vapaapäiv\w*|ylimääräi\w*\s+vapaa\w*|lomapäiv\w*|ledig\s+dag|lovdag\w*",
}
KW = {k: re.compile(v, re.I) for k, v in FIELDS.items()}
ANY_KW = re.compile("|".join(f"(?:{v})" for v in FIELDS.values()), re.I)

TERM_YEAR = re.compile(r"(syyslukukau\w*|syyskau\w*|hösttermin\w*|kevätlukukau\w*|kevätkau\w*|vårtermin\w*)\s+(20[2-3]\d)(?!\s*[–—/‐-]\s*\d)", re.I)
YEARPAIR = re.compile(r"(?<!\d)(20[2-3]\d)\s*[–—/‐-]\s*(20[2-3]\d|[2-3]\d)(?!\d)")
DAYS_RE = re.compile(r"(?:(\d{3})\s*(?:koulu|työ)päivä|(?:koulu|työ)päiviä\s*(?:on\s*)?(?:yhteensä\s*)?(\d{3})|(\d{3})\s*skoldagar|skoldagar\w*\s*:?\s*(\d{3}))", re.I)

D = r"(\d{1,2})\.\s?(\d{1,2})(?:\.|(?=\s*[–—‐‑−-])|(?=[ \t]*(?:\(|,|;|$)))(?:\s?(20\d\d|\d\d)(?!\d))?"
RANGE_FULL = re.compile(D + r"\s*" + DASH + r"\s*(?:\w{2,12}\s+)?" + D)
RANGE_SHORT = re.compile(r"(?<![\d.])(\d{1,2})\.?\s*" + DASH + r"\s*(?:\w{2,12}\s+)?" + D)
SINGLE = re.compile(r"(?<![\d.])" + D)
WEEK = re.compile(r"\b(?:vko|viikko|viikolla|viikot|vk|v\.|vecka|veckorna|v)\s*(\d{1,2})(?:\s*(?:ja|och|" + DASH + r")\s*(\d{1,2}))?\b", re.I)


WD = (r"(ma|ti|ke|to|pe|la|su|maanantai|tiistai|keskiviikko|torstai|perjantai|lauantai|sunnuntai|"
      r"mån|tis|ons|tors|tor|fre|lör|sön|må|on|fr|lö|sö)")


FI_MONTHS = ["tammikuu", "helmikuu", "maaliskuu", "huhtikuu", "toukokuu", "kesäkuu", "heinäkuu",
             "elokuu", "syyskuu", "lokakuu", "marraskuu", "joulukuu"]
SV_MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september",
             "oktober", "november", "december"]
MONTH_RE = re.compile(r"(\d{1,2})\.?\s*(" + "|".join(FI_MONTHS) + r")(?:ta|ssa|lle|n)?\b|(\d{1,2})\.?\s+(" + "|".join(SV_MONTHS) + r")\b", re.I)


def _months(t: str) -> str:
    def rep(m):
        if m.group(2):
            return f"{m.group(1)}.{FI_MONTHS.index(m.group(2).lower()) + 1}."
        return f"{m.group(3)}.{SV_MONTHS.index(m.group(4).lower()) + 1}."
    t = MONTH_RE.sub(rep, t)
    return re.sub(r"(\d{1,2}\.\d{1,2}\.)\s+(20\d\d)", r"\1\2", t)


def _norm(t: str) -> str:
    t = _months(t)
    t = re.sub(r"\s*\(" + WD + r"\.?\)", "", t, flags=re.I)
    t = t.replace("\xa0", " ").replace("\u00ad", "").replace(" ", " ")
    t = re.sub(r"(\d)\s*" + DASH + r"\s*(\d)", r"\1–\2", t)
    return t


def _year(y, sy):
    if y:
        y = int(y)
        return y + 2000 if y < 100 else y
    return None


def _mk(d, m, y, sy, ref_month=None):
    d, m = int(d), int(m)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    yy = _year(y, sy)
    if yy is None:
        if sy is None:
            return None
        yy = sy[0] if m >= 7 else sy[1]
    try:
        return date(yy, m, d)
    except ValueError:
        return None


def parse_dates(win: str, sy):
    """Palauttaa (alku, loppu, kuvaus, kohta) ikkunan ENSIMMÄISESTÄ päivämäärälausekkeesta.
    Samassa kohdassa etusija: täysi väli > lyhyt väli > viikko > yksittäinen."""
    cands = []
    for prio, rx in enumerate((RANGE_FULL, RANGE_SHORT, WEEK, SINGLE)):
        for m in rx.finditer(win):
            r = None
            if rx is RANGE_FULL:
                d1, m1, y1, d2, m2, y2 = m.groups()
                b = _mk(d2, m2, y2, sy)
                a = _mk(d1, m1, y1 or (b.year if b and int(m1) <= int(m2) else None), sy)
                r = (a, b) if a and b and a <= b else None
            elif rx is RANGE_SHORT:
                d1, d2, mm, yy = m.groups()
                b = _mk(d2, mm, yy, sy)
                a = _mk(d1, mm, yy or (b.year if b else None), sy)
                r = (a, b) if a and b and a <= b else None
            elif rx is WEEK:
                if sy:
                    w1 = int(m.group(1))
                    w2 = int(m.group(2)) if m.group(2) else w1
                    if 1 <= w1 <= 53 and w1 <= w2 <= w1 + 2:
                        y = sy[0] if w1 >= 30 else sy[1]
                        r = (iso_week_range(y, w1)[0], iso_week_range(y, w2)[1])
            else:
                a = _mk(*m.groups(), sy)
                r = (a, a) if a else None
            if r:
                cands.append((m.start(), prio, r[0], r[1], m.group(0)))
                break
    if not cands:
        return None
    pos, _, a, b, raw = min(cands, key=lambda c: (c[0], c[1]))
    return a, b, raw, pos


def school_year_of(d: date):
    return (d.year, d.year + 1) if d.month >= 7 else (d.year - 1, d.year)


HEAD_FORM = [("poikkeus", re.compile(r"muutokset|poikkeu|koulukohtai|ändringar|avvikels|undantag", re.I)),
             ("esi", re.compile(r"esiopetu|förskol|varhaiskasvat|småbarnspedagog", re.I)),
             ("lukio", re.compile(r"lukio|gymnasi|aikuislukio|vuxengymnas", re.I)),
             ("muu", re.compile(r"ammatillinen|ammattiopisto|kansalaisopisto|musiikkiopisto|aamu- ja iltapäivä", re.I)),
             ("perus", re.compile(r"perusopetu|peruskoul|grundskol|grundläggande|koulujen|skolorna|koulut\b|alakoul|yläkoul|vuosiluok", re.I))]
PERUS_RX = re.compile(r"perusopetu|peruskoul|grundskol|grundläggande|koulujen|skolorna|koulut\b|alakoul|yläkoul|vuosiluok", re.I)
OTHER_FORM = re.compile(r"esiopetu|förskol|varhaiskasvat|lukio|gymnasi|aikuis|vuxen", re.I)
HEAD_VAR = [("sv", re.compile(r"ruotsinkiel|svenskspråkig|svenska skol", re.I)),
            ("fi", re.compile(r"suomenkiel|finskspråkig|finska skol", re.I))]


def _sections(t, default_form="perus"):
    """Lyhyet otsikkorivit vaihtavat osion koulumuotoa ja kieliversiota."""
    out, pos, prev = [(0, default_form, "")], 0, ""
    for line in t.split("\n"):
        L = line.strip()
        cont = bool(L) and L[0].islower() and re.search(r"(\bja|\bsekä|\boch|,)\s*$", prev)
        if L:
            prev = L
        if cont:  # rivitetyn otsikon jatko ("…peruskouluissa ja / lukiossa") ei vaihda osiota
            pos += len(line) + 1
            continue
        if 3 < len(L) < 130 and YEARPAIR.search(L) and not re.search(r"\d{1,2}\.\d{1,2}\.", L):
            # lukuvuoden otsikko nollaa osion (valikoiden otsikot eivät periydy sisältöön)
            form = next((f for f, rx in HEAD_FORM if rx.search(L)), default_form)
            if form not in ("perus", "poikkeus") and PERUS_RX.search(L):
                form = "perus"
            var = next((v for v, rx in HEAD_VAR if rx.search(L)), "")
            out.append((pos, form, var))
        elif 3 < len(L) < 90 and not re.search(r"\d{1,2}\.\d{1,2}\.", L):
            form = next((f for f, rx in HEAD_FORM if rx.search(L)), None)
            var = next((v for v, rx in HEAD_VAR if rx.search(L)), None)
            if form or var:
                pf, pv = out[-1][1], out[-1][2]
                # "peruskoulut ja lukiot" -> perus voittaa
                if form and form not in ("perus", "poikkeus") and PERUS_RX.search(L):
                    form = "perus"
                out.append((pos, form or pf, var if var is not None else (pv if not form else "")))
        pos += len(line) + 1
    return out


def _section_at(sections, p):
    cur = sections[0]
    for s in sections:
        if s[0] <= p:
            cur = s
    return cur[1], cur[2]


DATE_FIRST = re.compile(r"^\s*\d{1,2}\.\s*(\d{1,2}\.)?\s*(\d{2,4})?\s*[–-]?\s*\d{0,2}")


def extract(text: str, want_years=None, want_variant=None, default_form="perus") -> dict:
    """-> {'2026-2027': {field: {'start','end','quote'}}, ...}"""
    t = _norm(text)
    headers = [(m.start(), (int(m.group(1)), _year(m.group(2), None)))
               for m in YEARPAIR.finditer(t)]
    headers = [(p, (a, b)) for p, (a, b) in headers if b == a + 1]
    # "Höstterminen 2026" / "Syyslukukausi 2026" / "Vårterminen 2027" -> lukuvuosi
    for m in TERM_YEAR.finditer(t):
        y = int(m.group(2))
        headers.append((m.start(), (y, y + 1) if m.group(1).lower().startswith(("syys", "höst")) else (y - 1, y)))
    headers.sort()
    raw = sorted(((m.start(), m.end(), k) for k, rx in KW.items() for m in rx.finditer(t)), key=lambda x: (x[0], -(x[1] - x[0])))
    kws, last_end = [], -1
    for s_, e_, k_ in raw:
        if s_ < last_end:
            continue  # sisältyy pidempään osumaan (esim. "syyslukukausi alkaa")
        kws.append((s_, e_, k_))
        last_end = e_
    sections = _sections(t, default_form)
    out: dict = {}
    for i, (s, e, field) in enumerate(kws):
        form, variant = _section_at(sections, s)
        if form != "perus" or (want_variant is not None and variant not in (want_variant, "")):
            continue
        ls, le = t.rfind("\n", 0, s) + 1, t.find("\n", e)
        line = t[ls:le if le > 0 else len(t)]
        if OTHER_FORM.search(line) and not PERUS_RX.search(line):
            continue  # rivi koskee esiopetusta/lukiota ("esiopetuksen syyslukukausi päättyy …")
        sy = None
        for p, pair in headers:
            if p <= s:
                sy = pair
        nxt = kws[i + 1][0] if i + 1 < len(kws) else len(t)
        # ikkuna avainsanan jälkeen seuraavaan avainsanaan asti (max 140 merkkiä)
        win = t[e:min(nxt, e + 140)]
        sy = None
        for p, pair in headers:
            if p <= s:
                sy = pair
        # "13.8.2026 (to) Skolan börjar" – päivä rivin alussa ja avainsanan jälkeen ei päivää samalla rivillä
        line_rest = t[e:le if le > 0 else len(t)]
        head = t[ls:s]
        r = None
        date_first = bool(DATE_FIRST.match(head)) and head.strip()[:1].isdigit() and not parse_dates(line_rest, sy)
        if date_first:
            r = parse_dates(head, sy)
            if not r:
                continue
        if not r:
            r = parse_dates(win, sy)
            if r:  # päivä löytyi myöhemmältä riviltä, joka koskee toista koulumuotoa ("Esiopetus alkaa 13.8.") -> ohita
                ap = e + r[3]
                dl = t[t.rfind("\n", 0, ap) + 1: (t.find("\n", ap) if t.find("\n", ap) >= 0 else len(t))]
                if t.rfind("\n", 0, ap) > s and OTHER_FORM.search(dl) and not PERUS_RX.search(dl):
                    r = None
                    continue
        if not r:  # taulukossa päivä voi olla ennen avainsanaa samalla rivillä
            line_start = t.rfind("\n", 0, s) + 1
            before = t[max(line_start, s - 60):s]
            r = parse_dates(before, sy) if not ANY_KW.search(before) else None
        if not r:
            continue
        a, b, raw, _ = r
        fixed = False
        if sy and field not in ("saturday", "free"):
            lo, hi = date(sy[0], 7, 15), date(sy[1], 6, 30)
            if not (lo <= a <= hi):  # kirjoitusvirhe vuodessa (Lumparland "16.10.2025" lukuvuoden 2026–27 alla)
                for dy in (1, -1):
                    try:
                        a2, b2 = a.replace(year=a.year + dy), b.replace(year=b.year + dy)
                    except ValueError:
                        continue
                    if lo <= a2 <= hi and lo <= b2 <= hi:
                        a, b, fixed = a2, b2, True
                        break
        # lukuvuosi päivien perusteella
        ys = school_year_of(a if field not in ("joulu",) else a)
        key = f"{ys[0]}-{ys[1]}"
        if want_years and key not in want_years:
            continue
        if field in ("term1", "term2") and a == b:
            continue  # lukukausi tarvitsee välin
        if field in ("saturday", "free") and (b - a).days > 6:
            continue  # yksittäiset päivät, ei jaksoja ("työ- ja lomapäivät lukuvuonna …")
        if field in ("syys", "talvi") and (b - a).days > 13:
            continue
        if field == "generic_start":
            field = "start" if a.month in (7, 8, 9) else ("term2_start" if a.month in (1, 2) else None)
        elif field == "generic_end":
            field = "end" if a.month in (5, 6) else ("term1_end" if a.month in (11, 12, 1) else None)
        if field is None:
            continue
        # "alkaa … ja päättyy" voi koskea syyslukukautta: joulun tienoon loppu = syyslukukauden loppu
        if field == "end" and a.month in (11, 12, 1):
            field = "term1_end"
        if field == "start" and a.month in (1, 2):
            field = "term2_start"
        # "Kevätlukukausi alkaa 7.1. - 5.6.2027" -> myös loppu
        if field in ("term2_start", "start") and a != b and b.month in (5, 6):
            out.setdefault(f"{school_year_of(a)[0]}-{school_year_of(a)[1]}" if a.month >= 7 else f"{a.year - 1}-{a.year}", {}).setdefault(
                "end", {"start": b.isoformat(), "end": b.isoformat(), "quote": " ".join(t[max(0, s - 10):e + 60].split())[:180]})
            b = a
        quote = " ".join(t[max(0, s - 10):e + len(raw) + 40].split())[:180]
        rec = out.setdefault(key, {})
        item = {"start": a.isoformat(), "end": b.isoformat(), "quote": quote}
        if fixed:
            item["year_fixed"] = True
        if field in ("saturday", "free"):
            rec.setdefault(field, [])
            if item["start"] not in [x["start"] for x in rec[field]]:
                rec[field].append(item)
        elif field not in rec:
            rec[field] = item
        else:
            rec.setdefault("_conflicts", []).append({field: item})
    # ilmoitettu koulupäivien määrä
    for m in DAYS_RE.finditer(t):
        n = int(next(g for g in m.groups() if g))
        if 170 <= n <= 200:
            sy = None
            for p, pair in headers:
                if p <= m.start():
                    sy = pair
            if sy:
                out.setdefault(f"{sy[0]}-{sy[1]}", {}).setdefault("days_doc", n)
    return {k: _derive(k, v) for k, v in out.items()}


def _derive(year: str, r: dict, country: str = "fi") -> dict:
    """Lukukaudet <-> alku/loppu, joululoma lukukausien välistä, lomat arkipäiviin.
    FI: jos loppua ei ilmoiteta, se on laissa: viikon 22 viimeinen arkipäivä (la) – perusopetusasetus 7 §."""
    if "term1_end" in r and "term1" not in r and "start" in r:
        r["term1"] = {"start": r["start"]["start"], "end": r["term1_end"]["start"], "quote": r["term1_end"]["quote"]}
    if "term2_start" in r and "term2" not in r and "end" in r:
        r["term2"] = {"start": r["term2_start"]["start"], "end": r["end"]["start"], "quote": r["term2_start"]["quote"]}
    if "term1" in r:
        r.setdefault("start", {"start": r["term1"]["start"], "end": r["term1"]["start"], "quote": r["term1"]["quote"]})
    if "term2" in r:
        r.setdefault("end", {"start": r["term2"]["end"], "end": r["term2"]["end"], "quote": r["term2"]["quote"]})
    # lukukausi ilmoittaa viimeisen koulupäivän: joululoma alkaa vasta sen jälkeen (Pietarsaari 22.12.)
    t1e = (r.get("term1") or r.get("term1_end") or {}).get("end")
    if "joulu" in r and t1e and r["joulu"]["start"] <= t1e:
        from datetime import timedelta
        r["joulu"]["start"] = (date.fromisoformat(t1e) + timedelta(1)).isoformat()
    if "end" not in r and country == "fi" and any(k in r for k in ("syys", "talvi", "start")):
        y2 = int(year[5:])
        sat = date.fromisocalendar(y2, 22, 6)
        r["end"] = {"start": sat.isoformat(), "end": sat.isoformat(), "quote": "laki: viikon 22 lauantai (PoA 7 §)", "derived": True}
    if "joulu" not in r and "term1" in r and "term2" in r:
        a = date.fromisoformat(r["term1"]["end"])
        b = date.fromisoformat(r["term2"]["start"])
        from datetime import timedelta
        s, e = clip_to_weekdays(a + timedelta(1), b - timedelta(1))
        if s:
            r["joulu"] = {"start": s.isoformat(), "end": e.isoformat(), "quote": "johdettu lukukausista", "derived": True}
    if "joulu" in r:
        from datetime import timedelta
        from .cal import public_holidays
        e = date.fromisoformat(r["joulu"]["end"])
        ph = public_holidays("fi", e.year) | public_holidays("fi", e.year + 1)
        n = e + timedelta(1)
        while n in ph or n.weekday() >= 5:
            if n in ph and n.weekday() < 5:
                r["joulu"]["end"] = n.isoformat()  # "joululoma 23.12.–5.1., loppiainen 6.1." -> 23.12.–6.1.
            n += timedelta(1)
            if (n - e).days > 4:
                break
    for k in ("syys", "joulu", "talvi", "paasiainen"):
        if k in r:
            s, e = clip_to_weekdays(date.fromisoformat(r[k]["start"]), date.fromisoformat(r[k]["end"]))
            if s:
                r[k]["start"], r[k]["end"] = s.isoformat(), e.isoformat()
    return r
