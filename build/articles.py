"""SEO-artikkelit (design: G1 "vastaus ensin" + G2 maakuntaruudukko, valittu 24.11.2026).

Kaikki luvut lasketaan rakennushetkellä kuntien omista päätöksistä (arviot eivät ole mukana),
joten artikkelit pysyvät ajan tasalla jokaisessa ajossa.
"""
import html
import json
from collections import Counter, defaultdict
from datetime import date, timedelta

Y1, Y2 = "2026-2027", "2027-2028"
# maakunnat suunnilleen pohjoisesta etelään (ruudukon järjestys)
REGIONS = ["Lappi", "Pohjois-Pohjanmaa", "Kainuu", "Pohjanmaa", "Keski-Pohjanmaa", "Pohjois-Savo", "Pohjois-Karjala",
           "Etelä-Pohjanmaa", "Keski-Suomi", "Etelä-Savo", "Satakunta", "Pirkanmaa", "Päijät-Häme", "Etelä-Karjala",
           "Varsinais-Suomi", "Kanta-Häme", "Kymenlaakso", "Ahvenanmaa", "Uusimaa"]
WEEK_SHADE = {8: ("#DDEAF7", "#1D4F91"), 9: ("#BCD5F0", "#174A80"), 10: ("#9DC0E8", "#0F3A68"), 11: ("#EEF4FB", "#1D4F91"), 7: ("#EEF4FB", "#1D4F91")}
DAY_SHADE = [("#DCF2E3", "#0E5A2B"), ("#BFE5CB", "#0E5A2B"), ("#A2D8B4", "#0B4A23")]
FI_WD = ["maanantaina", "tiistaina", "keskiviikkona", "torstaina", "perjantaina", "lauantaina", "sunnuntaina"]
FI_NUM = {1: "Yhdessä", 2: "Kahdessa", 3: "Kolmessa", 4: "Neljässä", 5: "Viidessä"}

CSS = """.art{max-width:720px;margin:0 auto}.art .kick{font-size:14px;font-weight:800;color:var(--c2)}
.art h1{font-size:32px;line-height:1.12;margin:6px 0 4px}.art h2{font-size:24px;line-height:1.2;margin:34px 0 10px}
.art p,.art li{font-size:18px;line-height:1.6;max-width:36em}.art .meta{display:flex;gap:8px;flex-wrap:wrap;align-items:center;font-size:13px;font-weight:800;color:#5F4B3A;margin:6px 0 16px}
.ans{background:var(--hero);color:var(--ht);border-radius:28px;padding:18px 18px 8px;box-shadow:0 6px 0 var(--hs)}
.ans .lbl{display:flex;align-items:center;gap:8px;font-size:14px;font-weight:900;text-transform:uppercase;letter-spacing:.04em}
.ans .short{font-size:20px;line-height:1.45;font-weight:800;margin:8px 0 10px;max-width:none}
.ans .row{display:flex;align-items:center;gap:12px;padding:10px 0;border-top:1px solid rgba(255,255,255,.28);text-decoration:none;color:inherit}
.ans .row:hover{color:inherit}.ans .chip{width:58px;height:58px;border-radius:16px;background:#fff;color:var(--hero);display:flex;flex-direction:column;align-items:center;justify-content:center;flex:none;line-height:1}
.ans .chip small{font-size:11px;font-weight:800}.ans .chip b{font-size:21px;font-weight:900}.ans .row b.t{font-size:18px}.ans .row span{display:block;font-size:14px;font-weight:700}
.rg{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;background:#fff;border-radius:24px;padding:12px;box-shadow:0 3px 0 #E5D8C4}
.rg div{border-radius:14px;padding:8px 10px;min-height:58px}.rg small{display:block;font-size:12.5px;font-weight:800;line-height:1.2}.rg b{font-size:18px;font-weight:900}
.leg{display:flex;gap:12px;flex-wrap:wrap;font-size:14px;font-weight:800;margin:10px 0 0}.leg i{display:inline-block;width:16px;height:16px;border-radius:5px;vertical-align:-3px;margin-right:5px}
.art details{background:#fff;border-radius:20px;padding:14px 18px;margin:0 0 10px;box-shadow:0 3px 0 #E5D8C4}.art details summary{font-size:18px}
.art details p{margin:8px 0 0}.art .src{margin-top:26px}
.acards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
.acard{display:flex;gap:14px;align-items:center;background:#fff;border-radius:24px;padding:16px;text-decoration:none;color:#2A1B0F;box-shadow:0 4px 0 var(--c)}
.acard:hover{color:#2A1B0F;transform:translateY(-2px)}.acard b{font-size:18px;line-height:1.25;display:block}.acard span{font-size:14px;font-weight:700;color:#5F4B3A}
@media(min-width:900px){.art h1{font-size:44px}.rg{grid-template-columns:repeat(4,minmax(0,1fr))}}"""


def _wk(s):
    return date.fromisoformat(s).isocalendar()[1]


def _ok(data, year=Y1):
    return [r for r in data if (r["years"].get(year) or {}).get("confidence") not in (None, "arvio")]


def _examples(rs, n=3):
    return ", ".join(r["name"] for r in sorted(rs, key=lambda r: -(r.get("pop") or 0))[:n])


def _join(xs, last="tai"):
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + f" {last} " + xs[-1]


def _grid(by_region, shade_of, label_of):
    cells = ""
    mixed = []
    for reg in REGIONS:
        c = by_region.get(reg)
        if not c:
            continue
        top, n = c.most_common(1)[0]
        if len(c) > 1:
            mixed.append(reg)
        bg, fg = shade_of(top)
        sec = c.most_common(2)[1][0] if len(c) > 1 else None
        cells += (f'<div style="background:{bg};color:{fg}"><small>{html.escape(reg)}</small><b>{label_of(top)}</b>'
                  + (f'<small style="font-weight:700;margin-top:2px">osa {label_of(sec)}</small>' if sec is not None else "") + '</div>')
    return f'<div class="rg">{cells}</div>', mixed


def _faq(items):
    return "".join(f"<details{' open' if i == 0 else ''}><summary>{html.escape(q)}</summary><p>{a}</p></details>" for i, (q, a) in enumerate(items))


def _schema(title, desc, path, base, today, faq):
    return [{"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc,
             "datePublished": "2026-11-24", "dateModified": today.isoformat(), "inLanguage": "fi", "mainEntityOfPage": base + path,
             "author": {"@type": "Organization", "name": "Koululomat.fi"},
             "publisher": {"@type": "Organization", "name": "BR Entertainment", "logo": {"@type": "ImageObject", "url": base + "/icon-512.png"}}},
            {"@context": "https://schema.org", "@type": "FAQPage",
             "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": html.unescape(a.replace("<b>", "").replace("</b>", ""))}} for q, a in faq]}]


def build_articles(data, today, write, h):
    """h: apufunktiot build_site.py:stä (page, search_form, icon, share_btn, HOL, BASE). Palauttaa artikkelien tiedot linkitystä varten."""
    page, search_form, icon, share_btn, HOL, BASE = h["page"], h["search_form"], h["icon"], h["share_btn"], h["HOL"], h["BASE"]
    ok = _ok(data)
    n_src = len(ok)
    upd = f"{today.day}.{today.month}.{today.year}"
    meta = (f'<div class="meta"><span>Päivitetty {upd}</span><span>·</span><span>Lukuaika 3 min</span><span>·</span>'
            f'<span class="b ok">Lähteenä {n_src} kunnan omat päätökset</span></div>')
    out = []

    # ---------------- Hiihtoloma 2027 ----------------
    weeks = defaultdict(list)
    by_reg = defaultdict(Counter)
    for r in ok:
        t = r["years"][Y1]["fields"].get("talvi")
        if t:
            w = _wk(t["start"])
            weeks[w].append(r)
            by_reg[r["region"]][w] += 1
    main = [w for w in sorted(weeks) if len(weeks[w]) >= 5]
    rare = [w for w in sorted(weeks) if len(weeks[w]) < 5]
    short = f"Koulujen hiihtoloma on talvella 2027 kunnasta riippuen viikolla {_join(main)}."
    for w in rare:
        k = len(weeks[w])
        short += f" {FI_NUM.get(k, str(k))} kunnassa se on viikolla {w}."
    rows = ""
    for w in sorted(weeks):
        mon = date.fromisocalendar(2027, w, 1)
        fri = mon + timedelta(4)
        rows += (f'<a class="row" href="/fi/hiihtoloma-2027/"><div class="chip"><small>vk</small><b>{w}</b></div>'
                 f'<div><b class="t">{mon.day}.{mon.month}.–{fri.day}.{fri.month}.2027</b><span>{len(weeks[w])} kuntaa · esim. {_examples(weeks[w])}</span></div></a>')
    grid, mixed = _grid(by_reg, lambda w: WEEK_SHADE.get(w, WEEK_SHADE[11]), lambda w: f"vk {w}")
    legend = "".join(f'<span><i style="background:{WEEK_SHADE[w][0]}"></i>vk {w}</span>' for w in main)
    mixed_txt = (f'<p style="font-size:15px;font-weight:700;color:#5F4B3A;margin:8px 0 0">Ruudussa maakunnan yleisin viikko. ”Osa” = osalla kunnista eri viikko – tarkista oma kuntasi.</p>' if mixed else "")
    south = [reg for reg in REGIONS if by_reg.get(reg) and by_reg[reg].most_common(1)[0][0] == 8]
    north = [reg for reg in REGIONS if by_reg.get(reg) and by_reg[reg].most_common(1)[0][0] == 10]
    c28 = Counter(_wk(v["fields"]["talvi"]["start"]) for r in data
                  if (v := r["years"].get(Y2)) and v["confidence"] != "arvio" and "talvi" in v["fields"])
    n28 = sum(c28.values())
    faq = [("Onko hiihtoloma sama kuin talviloma?", "Kyllä. Kunnat käyttävät kumpaakin nimeä samasta talven lomaviikosta."),
           ("Miksi naapurikunnalla on eri viikko?", "Jokainen kunta päättää koulujen loma-ajat itse. Samalla alueella viikko on yleensä sama, mutta maakuntien rajoilla on poikkeuksia."),
           ("Onko esikoululla ja lukiolla sama hiihtoloma?", "Yleensä kyllä, mutta esiopetuksen ja lukion päivät voivat poiketa. Oman kuntasi sivulta näet perusopetuksen päivät ja lähteen."),
           ("Milloin on hiihtoloma 2028?",
            (f"{n28} kuntaa on jo päättänyt seuraavan lukuvuoden: " + ", ".join(f"viikolla {w} {c28[w]} kuntaa" for w in sorted(c28)) + ". Lista täydentyy talven aikana, kun kunnat tekevät päätöksiä.")
            if n28 else "Kunnat päättävät seuraavan lukuvuoden yleensä loka–helmikuussa. Päivitämme tiedot heti, kun päätökset julkaistaan."),
           ]
    body = (f'<article class="art" style="--c2:#1D4F91"><div class="kick">Artikkeli · Hiihtoloma</div>'
            f'<h1>Hiihtoloma 2027: milloin on hiihtoloma?</h1>{meta}'
            f'<section class="ans"><div class="lbl">{icon("talvi", 20, "currentColor")} Lyhyt vastaus</div><p class="short">{short}</p>{rows}</section>'
            f'<h2 style="font-size:19px;margin:22px 0 8px">Mikä viikko on sinun kunnassasi?</h2>'
            f'{search_form("q2", "Kirjoita kuntasi", big=True, prefix="/fi/hiihtoloma-2027/")}'
            f'<h2>Hiihtolomaviikot maakunnittain</h2>'
            f'<p>Hiihtoloma alkaa etelästä ja siirtyy pohjoiseen. {_join(south[:4], "ja")} lomailevat viikolla 8, keskinen Suomi viikolla 9 ja '
            f'{_join(north[:5], "ja")} viikolla 10.</p>{grid}<div class="leg">{legend}</div>{mixed_txt}'
            f'<h2>Miksi hiihtolomat ovat eri viikoilla?</h2>'
            f'<p>Hiihtolomat porrastetaan, jotta hiihtokeskukset, junat ja mökit eivät ruuhkaudu yhdellä viikolla. '
            f'Jokainen kunta päättää viikon itse, mutta naapurikunnat valitsevat yleensä saman.</p>'
            f'<h2>Usein kysyttyä</h2>{_faq(faq)}'
            f'<div class="btns"><a class="btn" href="/fi/hiihtoloma-2027/">Kaikki kunnat viikoittain</a>'
            f'{share_btn("Koululomat", text="Hiihtoloma 2027 – katso oman kuntasi viikko:")}</div>'
            f'<p class="src">Lähteet: {n_src} kunnan omat päätökset koulujen työ- ja loma-ajoista (perusopetus), tarkistettu {upd}. '
            f'Kunnat, joiden päätöstä ei vielä löytynyt, eivät ole mukana luvuissa. <a href="/tietoa/">Miten tiedot kerätään?</a></p></article>')
    title = "Hiihtoloma 2027: milloin on hiihtoloma? Viikot kunnittain ja maakunnittain"
    desc = f"Hiihtoloma 2027 on kunnasta riippuen viikolla {_join(main)}. Katso oman kuntasi viikko – tiedot {n_src} kunnan omista päätöksistä."
    path = "/artikkelit/hiihtoloma-2027/"
    write(path, page(f"{title} | Koululomat", desc, body, path, _schema(title, desc, path, BASE, today, faq), theme="talvi", top_search=False))
    out.append({"path": path, "title": "Hiihtoloma 2027: milloin on hiihtoloma?", "sub": f"Viikot {_join(main)} – maakunnittain", "k": "talvi"})

    # ---------------- Joululoma 2026 ----------------
    starts = defaultdict(list)
    ends = Counter()
    by_reg = defaultdict(Counter)
    for r in ok:
        j = r["years"][Y1]["fields"].get("joulu")
        if j:
            s = date.fromisoformat(j["start"])
            starts[s].append(r)
            by_reg[r["region"]][s] += 1
            e = date.fromisoformat(j["end"]) + timedelta(1)
            while e.weekday() >= 5:
                e += timedelta(1)
            ends[e] += 1
    sd = sorted(starts)
    shade = {s: DAY_SHADE[min(i, 2)] for i, s in enumerate(sd)}
    main_s = [s for s in sd if len(starts[s]) >= 3]
    day_txt = _join([f"{FI_WD[s.weekday()]} {s.day}.{s.month}." for s in main_s])
    back, back_n = ends.most_common(1)[0] if ends else (None, 0)
    short = f"Koulujen joululoma alkaa kunnasta riippuen {day_txt}2026."
    if back:
        short += f" Useimmissa kunnissa ({back_n}/{sum(ends.values())}) koulu jatkuu {FI_WD[back.weekday()]} {back.day}.{back.month}.{back.year}."
    rows = "".join(f'<a class="row" href="/fi/joululoma/"><div class="chip"><small>{["ma", "ti", "ke", "to", "pe", "la", "su"][s.weekday()]}</small><b style="font-size:16px">{s.day}.{s.month}.</b></div>'
                   f'<div><b class="t">Alkaa {FI_WD[s.weekday()]} {s.day}.{s.month}.</b><span>{len(starts[s])} kuntaa · esim. {_examples(starts[s])}</span></div></a>' for s in sd)
    grid, mixed = _grid(by_reg, lambda s: shade[s], lambda s: f"{s.day}.{s.month}.")
    legend = "".join(f'<span><i style="background:{shade[s][0]}"></i>alkaa {s.day}.{s.month}.</span>' for s in sd if len(starts[s]) >= 3)
    mixed_txt = (f'<p style="font-size:15px;font-weight:700;color:#5F4B3A;margin:8px 0 0">”Osa” = osalla maakunnan kunnista eri alkupäivä – tarkista oma kuntasi.</p>' if mixed else "")
    back_rows = "".join(f"<li><b>{FI_WD[e.weekday()].capitalize()} {e.day}.{e.month}.{e.year}</b> – {n} kuntaa</li>" for e, n in sorted(ends.items()))
    faq = [("Onko jouluaatto koulupäivä?", "Ei. Joululoma on alkanut jokaisessa kunnassa viimeistään jouluaattoa edeltävänä päivänä."),
           ("Miksi joululoma alkaa eri päivinä?", "Kunta päättää loma-ajat itse. Lukuvuodessa on oltava laissa säädetty määrä koulupäiviä, joten kunnat sijoittavat päiviä eri tavoin syys- ja kevätlukukaudelle."),
           ("Onko esikoululla sama joululoma?", "Yleensä kyllä, mutta esiopetuksen päivät voivat poiketa. Varhaiskasvatuksella (päiväkoti) ei ole koulujen lomia."),
           ("Mistä näen oman kuntani päivät?", "Kirjoita kuntasi nimi hakuun. Kuntasivulla on joululoman lisäksi syys-, hiihto- ja kesäloma, lähde ja lähtölaskuri.")]
    body = (f'<article class="art" style="--c2:#0E5A2B"><div class="kick">Artikkeli · Joululoma</div>'
            f'<h1>Joululoma 2026: milloin koulujen joululoma alkaa?</h1>{meta}'
            f'<section class="ans"><div class="lbl">{icon("joulu", 20, "currentColor")} Lyhyt vastaus</div><p class="short">{short}</p>{rows}</section>'
            f'<h2 style="font-size:19px;margin:22px 0 8px">Milloin joululoma alkaa sinun kunnassasi?</h2>{search_form("q2", "Kirjoita kuntasi", big=True)}'
            f'<h2>Joululoman alku maakunnittain</h2><p>Ruudussa on maakunnan yleisin alkupäivä.</p>{grid}<div class="leg">{legend}</div>{mixed_txt}'
            f'<h2>Milloin koulu alkaa joululoman jälkeen?</h2><ul>{back_rows}</ul>'
            f'<h2>Usein kysyttyä</h2>{_faq(faq)}'
            f'<div class="btns"><a class="btn" href="/fi/joululoma/">Kaikki kunnat alkupäivittäin</a></div>'
            f'<p class="src">Lähteet: {n_src} kunnan omat päätökset koulujen työ- ja loma-ajoista (perusopetus), tarkistettu {upd}. '
            f'Kunnat, joiden päätöstä ei vielä löytynyt, eivät ole mukana luvuissa. <a href="/tietoa/">Miten tiedot kerätään?</a></p></article>')
    title = "Joululoma 2026: milloin koulujen joululoma alkaa ja loppuu?"
    desc = f"Koulujen joululoma 2026 alkaa kunnasta riippuen {day_txt} Katso oman kuntasi päivät – tiedot {n_src} kunnan omista päätöksistä."
    path = "/artikkelit/joululoma-2026/"
    write(path, page(f"{title} | Koululomat", desc, body, path, _schema(title, desc, path, BASE, today, faq), theme="joulu", top_search=False))
    out.append({"path": path, "title": "Joululoma 2026: milloin koulujen joululoma alkaa?", "sub": f"Alkaa {sd[0].day}.–{sd[-1].day}.{sd[-1].month}. – alueittain" if sd else "Alueittain", "k": "joulu"})
    return out
