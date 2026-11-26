"""Svenska lovsidor och artiklar (tvåspråkiga kommuner och Åland).

Datumen är de svenskspråkiga skolornas när de hittats (view(rec, "sv")), annars kommunens finskspråkiga
skolors med tydlig anmärkning på kommunsidan. Uppskattningar räknas aldrig med i artiklarnas siffror.
"""
import html
from collections import Counter, defaultdict
from datetime import date, timedelta

Y1 = "2026-2027"
REG_SV = {"Uusimaa": "Nyland", "Varsinais-Suomi": "Egentliga Finland", "Kymenlaakso": "Kymmenedalen",
          "Pohjanmaa": "Österbotten", "Keski-Pohjanmaa": "Mellersta Österbotten", "Ahvenanmaa": "Åland"}
REG_ORDER = ["Åland", "Egentliga Finland", "Nyland", "Kymmenedalen", "Österbotten", "Mellersta Österbotten"]
SV_WD = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
SV_WD2 = ["må", "ti", "on", "to", "fr", "lö", "sö"]
HPAGE_SV = {"syys": ("/sv/hostlov/", "Höstlov 2026"), "joulu": ("/sv/jullov/", "Jullov 2026–2027"),
            "talvi": ("/sv/sportlov-2027/", "Sportlov 2027"), "kesa": ("/sv/sommarlov/", "Sommarlov 2027")}
ART_SV = {"talvi": "/sv/sportlov-2027/", "joulu": "/sv/jullov/"}  # en sida per fråga: artikel + kommunlista på samma sida


def _join(xs, last="eller"):
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + f" {last} " + xs[-1]


def km(n):
    return f"{n} kommun" if n == 1 else f"{n} kommuner"


def _ex(items, n=3):
    return ", ".join(nm for _, _, nm in sorted(items, key=lambda t: -(t[0].get("pop") or 0))[:n])


def build(views, today, write, h):
    """views: [(rec_sv_view, sv_slug, sv_name, språkspecifik_och_indexerbar)]. h: page, search_form, icon, badge, HOL, DARK, BASE, schema_fn, faq_fn.
    -> lista över artiklar (för /sv/-startsidan) och sidornas sökvägar."""
    page, search_form, icon, HOL, DARK, G = h["page"], h["search_form"], h["icon"], h["HOL"], h["DARK"], h["G"]
    lists = {}
    L = {"syys": "Höstlov", "joulu": "Jullov", "talvi": "Sportlov", "kesa": "Sommarlov"}
    urls = []

    def dates(k, rec):
        v = rec["years"].get(Y1)
        if not v:
            return None
        f = v["fields"]
        if k == "kesa":
            return (date.fromisoformat(f["end"]["start"]),) * 2 + (v["confidence"],) if "end" in f else None
        return (date.fromisoformat(f[k]["start"]), date.fromisoformat(f[k]["end"]), v["confidence"]) if k in f else None

    # ---------------- lovsidor ----------------
    intro = {"syys": "Höstlovet beror på kommun – och i tvåspråkiga kommuner ibland på skolans språk.",
             "joulu": "När börjar jullovet i din kommun?",
             "talvi": "Vilken vecka har din kommun sportlov?",
             "kesa": "När slutar skolan i din kommun?"}
    for k, (path, label) in HPAGE_SV.items():
        groups = defaultdict(list)
        for rec, ss, nm, ls in views:
            x = dates(k, rec)
            if x:
                key = x[0].isocalendar()[1] if k in ("syys", "talvi") else x[0]
                groups[key].append((rec, ss, nm, x, ls))
        cols = ""
        for key, rs in sorted(groups.items()):
            n_est = sum(1 for *_, x, _ in rs if x[2] == "arvio")
            if k in ("syys", "talvi"):
                mon = date.fromisocalendar(2026 if k == "syys" else 2027, key, 1)
                fri = mon + timedelta(4)
                chip = f'<div class="wkb" style="--bg:{HOL[k]["bg"]};--c:{DARK[k]}"><small>v.</small><b>{key}</b></div>'
                title = f"{mon.day}.{mon.month}.–{fri.day}.{fri.month}.{fri.year}"
                # avvikande veckodagar (t.ex. höstlov on–fr 14.–16.10.)
                odd = sorted({(x[0], x[1]) for *_, x, _ in rs if x[0] != mon or x[1] != fri})
                if odd:
                    title += " · " + ", ".join(f"{SV_WD2[a.weekday()]}–{SV_WD2[b.weekday()]} {a.day}.–{b.day}.{b.month}." for a, b in odd[:2])
            else:
                chip = f'<div class="wkb" style="--bg:{HOL[k]["bg"]};--c:{DARK[k]}"><small>{SV_WD2[key.weekday()]}</small><b>{key.day}.{key.month}.</b></div>'
                title = (f"Skolan slutar {SV_WD[key.weekday()]} {key.day}.{key.month}.{key.year}" if k == "kesa"
                         else f"Börjar {SV_WD[key.weekday()]} {key.day}.{key.month}.{key.year}")
            li = "".join(f'<li><a href="/sv/{ss}/">{html.escape(nm)}</a>' + (' <span class="b est">uppskattning</span>' if x[2] == "arvio" else "") + "</li>"
                         for rec, ss, nm, x, _ in sorted(rs, key=lambda t: t[2]))
            anchor = f"v-{key}" if k in ("syys", "talvi") else f"d-{key.month}-{key.day}"
            cols += (f'<div class="card" id="{anchor}"><div class="gh">{chip}<div><b>{title}</b><div class="dt">{km(len(rs))}'
                     + (f" ({n_est} uppskattningar)" if n_est else "") + f'</div></div></div><ul class="list" style="columns:2 140px;margin-top:12px">{li}</ul></div>')
        n_ls = sum(1 for rs in groups.values() for *_, x, ls in rs if ls and x[2] != "arvio")
        if k in ART_SV:
            lists[k] = (cols, n_ls)
            continue
        art = (f'<h2 style="margin-top:30px">Läs också</h2><div class="acards"><a class="acard" href="{ART_SV[k]}" style="--c:{HOL[k]["c"]}">'
               f'<div class="ic" style="background:{HOL[k]["bg"]};flex:none">{icon(k, 26)}</div><div><b>'
               + ("När är sportlovet 2027?" if k == "talvi" else "När börjar jullovet 2026?") + "</b></div></a></div>") if k in ART_SV else ""
        body = (f'<p class="lng"><a href="{h["HPAGE"][k][0]}" hreflang="fi" lang="fi">Suomeksi</a></p>'
                f'<section class="hero" style="height:auto;text-align:left;align-items:stretch">'
                f'<div style="display:flex;align-items:center;gap:12px">{icon(k, 44, "currentColor")}<h1 style="margin:0;color:inherit">{label} per kommun</h1></div>'
                f'<p class="lead" style="margin:10px 0 16px">{intro[k]}</p>{search_form("q2", "Skriv din kommun", big=True, lang="sv")}</section>'
                f'<div class="wk" style="margin-top:22px">{cols}</div>'
                f'<p class="src">Tvåspråkiga kommuner och Åland. Där de svenskspråkiga skolornas lov hittats visas de; annars gäller uppgiften kommunens finskspråkiga skolor (anges på kommunsidan). '
                f'Övriga kommuner finns <a href="{h["HPAGE"][k][0]}" lang="fi">på finska</a>.</p>{art}')
        write(path, page(f"{label} per kommun – tvåspråkiga kommuner och Åland | Koululomat",
                         f"{label}: skolornas lovdatum i tvåspråkiga kommuner och på Åland. Uppgifter från kommunernas egna källor.",
                         body, path, theme=k, top_search=False, lang="sv",
                         g=("loma_sv", *G.count_ok(n_ls, G.MIN_KUNNAT_LOMA_SV, "kommuner med svenskspråkiga datum")),
                         sig=sorted((ss, str(x)) for rs in groups.values() for _, ss, _, x, _ in rs)))
        urls.append(path)

    # ---------------- artiklar ----------------
    ok = [(rec, ss, nm) for rec, ss, nm, _ in views if (rec["years"].get(Y1) or {}).get("confidence") not in (None, "arvio")]
    n_src = len(ok)
    upd = f"{today.day}.{today.month}.{today.year}"
    meta = (f'<div class="meta"><span>Kontrollerad {upd}</span><span>·</span><span>Läsetid 2 min</span><span>·</span>'
            f'<span class="b ok">Källa: {n_src} kommuners egna beslut</span></div>')
    arts = []

    def region_list(by_reg, fmt):
        rows = ""
        for reg in REG_ORDER:
            c = by_reg.get(reg)
            if not c:
                continue
            parts = ", ".join(f"{fmt(v)} ({km(n)})" for v, n in sorted(c.items()))
            rows += f"<li><b>{reg}:</b> {parts}</li>"
        return f"<ul>{rows}</ul>"

    # Sportlov 2027
    weeks, by_reg = defaultdict(list), defaultdict(Counter)
    for rec, ss, nm in ok:
        t = rec["years"][Y1]["fields"].get("talvi")
        if t:
            w = date.fromisoformat(t["start"]).isocalendar()[1]
            weeks[w].append((rec, ss, nm))
            by_reg[REG_SV.get(rec["region"], rec["region"])][w] += 1
    if weeks:
        ws = sorted(weeks)
        short = f"Sportlovet 2027 är beroende på kommun vecka {_join(ws)}."
        rows = ""
        for w in ws:
            mon = date.fromisocalendar(2027, w, 1)
            fri = mon + timedelta(4)
            rows += (f'<a class="row" href="#v-{w}"><div class="chip"><small>v.</small><b>{w}</b></div>'
                     f'<div><b class="t">{mon.day}.{mon.month}.–{fri.day}.{fri.month}.2027</b><span>{km(len(weeks[w]))} · t.ex. {_ex(weeks[w])}</span></div></a>')
        faq = [("Är sportlov samma sak som vinterlov?", "Ja. Kommunerna använder båda namnen om samma lovvecka på vintern."),
               ("Har svenska och finska skolor samma sportlov?", "Oftast ja, men i tvåspråkiga kommuner kan de svenskspråkiga skolornas lov avvika. Kommunsidan visar vilka skolor uppgiften gäller."),
               ("Varför har grannkommunen en annan vecka?", "Varje kommun beslutar själv om skolornas lov. Sportloven sprids ut över flera veckor så att skidorter och tåg inte blir överfulla.")]
        body = (f'<p class="lng"><a href="/fi/hiihtoloma-2027/" hreflang="fi" lang="fi">Suomeksi</a></p>'
                f'<article class="art" style="--c2:#0F4A80"><div class="kick">Sportlov</div><h1>Sportlov 2027: när är sportlovet?</h1>{meta}'
                f'<section class="ans"><div class="lbl">{icon("talvi", 20, "currentColor")} Kort svar</div><p class="short">{short}</p>{rows}</section>'
                f'<h2 style="font-size:19px;margin:22px 0 8px">Vilken vecka har din kommun?</h2>{search_form("q2", "Skriv din kommun", big=True, lang="sv")}'
                f'<h2>Sportlovsveckor per landskap</h2>{region_list(by_reg, lambda w: f"vecka {w}")}'
                f'<h2 id="kommuner">Alla kommuner per vecka</h2><div class="wk">{lists.get("talvi", ("", 0))[0]}</div>'
                f'<h2>Vanliga frågor</h2>{h["faq"](faq)}'
                f'<p class="src">Källor: {n_src} tvåspråkiga kommuners och åländska kommuners egna beslut om skolornas arbets- och lovtider (grundskolan), kontrollerade {upd}. '
                f'Kommuner vars beslut inte hittats är inte med i siffrorna.</p></article>')
        title = "Sportlov 2027: när är sportlovet?"
        desc = f"Sportlovet 2027 är vecka {_join(ws)} beroende på kommun. Se din kommuns vecka – uppgifter från kommunernas egna beslut."
        path = ART_SV["talvi"]
        write(path, page(f"{title} Veckor per kommun | Koululomat", desc, body, path, h["schema"](title, desc, path, h["BASE"], today, faq, "sv"),
                         theme="talvi", top_search=False, lang="sv",
                         g=("loma_sv", *G.count_ok(lists.get("talvi", ("", 0))[1], G.MIN_KUNNAT_LOMA_SV, "kommuner med svenskspråkiga datum")),
                         sig=sorted((ss, w) for w, rs in weeks.items() for _, ss, _ in rs)))
        arts.append({"path": path, "title": "Sportlov 2027: när är sportlovet?", "sub": f"Vecka {_join(ws)} per kommun", "k": "talvi"})
        urls.append(path)

    # Jullov 2026
    starts, by_reg, ends = defaultdict(list), defaultdict(Counter), Counter()
    for rec, ss, nm in ok:
        j = rec["years"][Y1]["fields"].get("joulu")
        if j:
            a = date.fromisoformat(j["start"])
            starts[a].append((rec, ss, nm))
            by_reg[REG_SV.get(rec["region"], rec["region"])][a] += 1
            ends[date.fromisoformat(j["end"])] += 1
    if starts:
        ds = sorted(starts)
        short = f"Jullovet 2026 börjar beroende på kommun {_join([f'{SV_WD[d.weekday()]} {d.day}.{d.month}.' for d in ds])}"
        short = short if short.endswith(".") else short + "."
        e1 = ends.most_common(1)[0][0]
        short += f" Skolan börjar igen oftast efter trettondagen; lovet slutar vanligen {SV_WD[e1.weekday()]} {e1.day}.{e1.month}.{e1.year}."
        rows = "".join(f'<a class="row" href="#d-{d.month}-{d.day}"><div class="chip"><small>{SV_WD2[d.weekday()]}</small><b style="font-size:16px">{d.day}.{d.month}.</b></div>'
                       f'<div><b class="t">Börjar {SV_WD[d.weekday()]} {d.day}.{d.month}.2026</b><span>{km(len(starts[d]))} · t.ex. {_ex(starts[d])}</span></div></a>' for d in ds)
        faq = [("Är julfesten en skoldag?", "Ja, om julfesten är inskriven som skoldag i läsårets arbetstider. En julfest på lördag ersätter en annan skoldag."),
               ("Har svenska och finska skolor samma jullov?", "Inte alltid. I Vanda börjar t.ex. de svenskspråkiga skolornas jullov 21.12. och de finskspråkigas 23.12. Kommunsidan visar vilka skolor uppgiften gäller."),
               ("När börjar skolan efter jullovet?", "Oftast torsdag 7.1.2027, efter trettondagen. Se din kommuns datum med sökningen.")]
        body = (f'<p class="lng"><a href="/fi/joululoma/" hreflang="fi" lang="fi">Suomeksi</a></p>'
                f'<article class="art" style="--c2:#0E5A2B"><div class="kick">Jullov</div><h1>Jullov 2026: när börjar jullovet?</h1>{meta}'
                f'<section class="ans"><div class="lbl">{icon("joulu", 20, "currentColor")} Kort svar</div><p class="short">{short}</p>{rows}</section>'
                f'<h2 style="font-size:19px;margin:22px 0 8px">När börjar lovet i din kommun?</h2>{search_form("q2", "Skriv din kommun", big=True, lang="sv")}'
                f'<h2>Jullovets början per landskap</h2>{region_list(by_reg, lambda d: f"{SV_WD2[d.weekday()]} {d.day}.{d.month}.")}'
                f'<h2 id="kommuner">Alla kommuner</h2><div class="wk">{lists.get("joulu", ("", 0))[0]}</div>'
                f'<h2>Vanliga frågor</h2>{h["faq"](faq)}'
                f'<p class="src">Källor: {n_src} kommuners egna beslut om skolornas arbets- och lovtider (grundskolan), kontrollerade {upd}.</p></article>')
        title = "Jullov 2026: när börjar jullovet?"
        desc = "Jullovet 2026 börjar " + _join([f"{d.day}.{d.month}." for d in ds]) + " beroende på kommun. Se din kommuns datum."
        path = ART_SV["joulu"]
        write(path, page(f"{title} Datum per kommun | Koululomat", desc, body, path, h["schema"](title, desc, path, h["BASE"], today, faq, "sv"),
                         theme="joulu", top_search=False, lang="sv",
                         g=("loma_sv", *G.count_ok(lists.get("joulu", ("", 0))[1], G.MIN_KUNNAT_LOMA_SV, "kommuner med svenskspråkiga datum")),
                         sig=sorted((ss, str(d)) for d, rs in starts.items() for _, ss, _ in rs)))
        arts.insert(0, {"path": path, "title": "Jullov 2026: när börjar jullovet?", "sub": "Datum per kommun", "k": "joulu"})
        urls.append(path)
    return arts, urls
