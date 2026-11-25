"""Staattinen sivusto (design C "Leikki", valittu 24.11.2026): data/fi.json -> site/ (Cloudflare Pages).

Ei seurantaa, ei evästeitä, ei ulkoisia skriptejä eikä fontteja (Nunito omalta palvelimelta).
PREVIEW=1 (oletus) -> noindex + robots Disallow + keltainen palkki.
Käyttö: PREVIEW=1 python3 build/build_site.py data/fi.json site
"""
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import articles
import sv_pages  # noqa: E402

PREVIEW = os.environ.get("PREVIEW", "1") == "1"
BASE = os.environ.get("SITE_URL", "https://koululomat.fi")
OWNER = "BR Entertainment (Y-tunnus 3183394-5)"
WD = ["ma", "ti", "ke", "to", "pe", "la", "su"]
STATIC = Path(__file__).resolve().parent / "static"

# lomakohtainen väri + ikoni + nimi (väri ei koskaan ainoa merkityksen kantaja)
HOL = {
    "syys": {"name": "Syysloma", "c": "#C2410C", "bg": "#FBE4D8",
             "icon": '<path d="M5 19c8 0 14-6 14-14C11 5 5 11 5 19z"/><path d="M5 19l8-8"/>'},
    "joulu": {"name": "Joululoma", "c": "#15803D", "bg": "#DCF2E3",
              "icon": '<path d="M12 2l5 7h-3l4 6h-4l3 5H7l3-5H6l4-6H7z"/>'},
    "talvi": {"name": "Hiihtoloma", "c": "#1D6FB8", "bg": "#DDEAF7",
              "icon": '<path d="M12 2v20M4 6l16 12M20 6L4 18"/>'},
    "kesa": {"name": "Kesäloma", "c": "#8A5A00", "bg": "#FFF0C7",
             "icon": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19"/>'},
}
# väriprofiilit: (hero, varjo, teksti, sivun sävy, palkki, palkin pohja) – kontrasti tarkistettu (valkoinen ≥ 5:1, kesä tumma teksti 9,5:1)
THEME = {"brand": ("#E8741E", "#B4530F", "#fff", "#FFF6E5", "#FFE08A", "rgba(255,255,255,.3)"),
         "syys": ("#C2410C", "#8A2E08", "#fff", "#FFF3EC", "#FFE08A", "rgba(255,255,255,.3)"),
         "joulu": ("#15803D", "#0E5A2B", "#fff", "#EFF8F1", "#FFE08A", "rgba(255,255,255,.3)"),
         "talvi": ("#1D6FB8", "#0F4A80", "#fff", "#EEF4FB", "#FFE08A", "rgba(255,255,255,.3)"),
         "kesa": ("#FFB627", "#C98A0B", "#2A1B0F", "#FFF8E1", "#2A1B0F", "rgba(42,27,15,.15)")}
DARK = {"syys": "#8A2E08", "joulu": "#0E5A2B", "talvi": "#0F4A80", "kesa": "#7A4F00"}  # lomavärin tumma sävy tekstiin vaalealla pohjalla (≥ 7:1)
HPAGE = {"syys": ("/fi/syysloma/", "Syysloma 2026"), "joulu": ("/fi/joululoma/", "Joululoma 2026–2027"),
         "talvi": ("/fi/hiihtoloma-2027/", "Hiihtoloma 2027"), "kesa": ("/fi/kesaloma/", "Kesäloma 2027")}
CONF = {"varmistettu": ("Varmistettu", "ok", "Kunnan oma lähde, ja koulupäivien laskenta täsmää lakiin."),
        "yksi_lähde": ("Yksi lähde", "one", "Kunnan oma lähde, toista vahvistusta ei vielä ole."),
        "ehdotus": ("Ehdotus", "prop", "Päätösehdotus – ei vielä lopullinen."),
        "arvio": ("Arvio", "est", "Kunnan päätöstä ei löytynyt. Arvio maakunnan muiden kuntien perusteella – tarkista koululta.")}
LOGO = ('<svg width="{s}" height="{s}" viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" rx="112" fill="#E8741E"/>'
        '<rect x="96" y="132" width="320" height="284" rx="40" fill="#FFF8EE"/><rect x="96" y="132" width="320" height="84" rx="40" fill="#1B1F24"/>'
        '<rect x="96" y="180" width="320" height="36" fill="#1B1F24"/><rect x="160" y="92" width="36" height="84" rx="18" fill="#FFF8EE"/>'
        '<rect x="316" y="92" width="36" height="84" rx="18" fill="#FFF8EE"/><circle cx="256" cy="316" r="58" fill="#FFB627"/></svg>')


# ruotsinkieliset sivut (/sv/): kaksikieliset kunnat (VNa 1385/2022, voimassa 2023–2032) ja Ahvenanmaa
SV_MUNS = {"Espoo", "Hanko", "Helsinki", "Kauniainen", "Kirkkonummi", "Lapinjärvi", "Lohja", "Loviisa", "Myrskylä", "Porvoo",
           "Sipoo", "Siuntio", "Vantaa", "Inkoo", "Raasepori", "Turku", "Kemiönsaari", "Parainen", "Pyhtää", "Kaskinen", "Vaasa",
           "Korsnäs", "Kristiinankaupunki", "Kruunupyy", "Luoto", "Maalahti", "Mustasaari", "Närpiö", "Pedersören kunta",
           "Pietarsaari", "Uusikaarlepyy", "Vöyri", "Kokkola"}
T = {"fi": {"wd": WD, "hol": {k: v["name"] for k, v in HOL.items()}, "week": "viikko", "wk": "vk",
            "night": lambda n: "yö" if n == 1 else "yötä", "to": lambda k: T["fi"]["hol"][k] + "an on",
            "now": lambda k: f"{T['fi']['hol'][k]} on nyt!", "starts": "alkaa", "est": "arvio", "past": "Ohi jo!", "onhol": "Nyt lomalla!",
            "share": "Jaa kaverille", "search": "Hae kuntaa", "ph": "Mikä on sinun kuntasi?",
            "conf": {"varmistettu": "Varmistettu", "yksi_lähde": "Yksi lähde", "ehdotus": "Ehdotus", "arvio": "Arvio"},
            "tip": {k: v[2] for k, v in CONF.items()}, "bar": "Lomasta lomaan: matkaa takana",
            "adult": "Aikuisille: tarkat päivät", "rows": ["Koulu alkaa", "Syysloma", "Joululoma", "Talviloma (hiihtoloma)", "Koulu päättyy"],
            "perus": "Perusopetus", "tabs": ["Peruskoulu", "Esikoulu", "Lukio"], "tabl": "Koulumuoto", "full": ["Esiopetus", "Lukio"],
            "note": "Lomapäivät ovat arkipäiviä, viikonloput tulevat lisäksi. Yksittäisten koulujen päivät voivat poiketa.",
            "src": "Lähteet", "upd": "Päivitetty", "calc": "koulupäiviä laskettu", "docd": "koulupäiviä kunnan ilmoituksen mukaan", "law": "laki",
            "noyear": "arvio – kunnan päätöstä ei vielä löytynyt, tarkista koululta",
            "frows": ["Lukukausi alkaa", "Syysloma", "Syyslukukausi päättyy", "Joululoma", "Kevätlukukausi alkaa", "Talviloma (hiihtoloma)", "Lukukausi päättyy"],
            "fnone": lambda full, F: (f"Kunnan lähteestä ei löytynyt erikseen ilmoitettuja päiviä ({full.lower()}). "
                                      + ("Esiopetus noudattaa usein peruskoulun lomia, mutta alku- ja loppupäivä voivat poiketa. Tarkista päiväkodista tai koululta."
                                         if F == "esi" else "Lukion lomat ovat usein samat kuin peruskoulussa, mutta lukukauden alku ja loppu voivat poiketa. Tarkista lukiolta.")),
            "fsrc": "Luettu kunnan omasta asiakirjasta; ei vielä varmistettu toisesta lähteestä. Puuttuvat rivit eivät ole lähteessä erikseen.",
            "pv": "Esikatselu – tietoja tarkistetaan vielä. Sivu ei näy hakukoneissa.",
            "foot": 'Tiedot kunnan omasta lähteestä · Ei evästeitä, ei seurantaa · <a href="/tietoa/">Tietoa</a> · <a href="/tietosuoja/">Tietosuoja</a>',
            "home": "/"},
     "sv": {"wd": ["må", "ti", "on", "to", "fr", "lö", "sö"], "hol": {"syys": "Höstlov", "joulu": "Jullov", "talvi": "Sportlov", "kesa": "Sommarlov"},
            "week": "vecka", "wk": "v.", "night": lambda n: "natt" if n == 1 else "nätter",
            "to": lambda k: "Till " + T["sv"]["hol"][k].lower() + "et är det", "now": lambda k: f"{T['sv']['hol'][k]} nu!",
            "starts": "börjar", "est": "uppskattning", "past": "Redan över!", "onhol": "Lov nu!",
            "share": "Dela med en kompis", "search": "Sök kommun", "ph": "Vilken är din kommun?",
            "conf": {"varmistettu": "Bekräftad", "yksi_lähde": "En källa", "ehdotus": "Förslag", "arvio": "Uppskattning"},
            "tip": {"varmistettu": "Kommunens egen källa, och antalet skoldagar stämmer med lagen.",
                    "yksi_lähde": "Kommunens egen källa, ännu inte bekräftad av en annan källa.",
                    "ehdotus": "Beslutsförslag – inte slutligt.",
                    "arvio": "Kommunens beslut hittades inte. Uppskattning utgående från andra kommuner i landskapet – kontrollera med skolan."},
            "bar": "Från lov till lov: avklarat",
            "adult": "Exakta datum för vuxna", "rows": ["Skolan börjar", "Höstlov", "Jullov", "Sportlov (vinterlov)", "Skolan slutar"],
            "perus": "Grundskola", "tabs": ["Grundskola", "Förskola", "Gymnasium"], "tabl": "Skolform", "full": ["Förskoleundervisning", "Gymnasium"],
            "note": "Lovdagarna är vardagar, veckosluten kommer till. Enskilda skolor kan ha avvikande dagar.",
            "src": "Källor", "upd": "Uppdaterad", "calc": "skoldagar beräknade", "docd": "skoldagar enligt kommunen", "law": "lag",
            "noyear": "uppskattning – kommunens beslut har inte hittats ännu, kontrollera med skolan",
            "frows": ["Terminen börjar", "Höstlov", "Höstterminen slutar", "Jullov", "Vårterminen börjar", "Sportlov (vinterlov)", "Terminen slutar"],
            "fnone": lambda full, F: ("Kommunens källa anger inga separata datum för " + ("förskoleundervisningen. Förskolan följer ofta grundskolans lov, men start och slut kan avvika. Kontrollera med daghemmet eller skolan."
                                      if F == "esi" else "gymnasiet. Gymnasiets lov är ofta desamma som grundskolans, men terminens start och slut kan avvika. Kontrollera med gymnasiet.")),
            "fsrc": "Läst ur kommunens eget dokument; ännu inte bekräftat av en annan källa. Rader som saknas anges inte separat i källan.",
            "pv": "Förhandsvisning – uppgifterna kontrolleras ännu.",
            "foot": 'Uppgifter från kommunens egen källa · Inga kakor, ingen spårning · <a href="/tietoa/">Om tjänsten (på finska)</a> · <a href="/tietosuoja/">Dataskydd (på finska)</a>',
            "home": "/sv/"}}


def view(rec, lang):
    """Sivun kielen koulujen päivät. Kaksikielisissä kunnissa fi- ja sv-koulujen lomat voivat erota (Vantaa: höstlov 14.–16.10.).
    -> (tietue, huomautus): huomautus kertoo, jos päivät koskevat toisenkielisiä kouluja."""
    if rec.get("variant", "fi") == lang or not rec["years"]:
        return rec, None
    alt = (rec.get("alt") or {}).get(lang)
    if alt:
        yrs = dict(alt)
        other = [y for y in rec["years"] if y not in alt]
        for y in other:
            yrs[y] = rec["years"][y]
        return dict(rec, years=dict(sorted(yrs.items())), forms={}), ("mixed", other) if other else None
    if rec["region"] == "Ahvenanmaa":
        return rec, None
    return dict(rec, forms={}), ("other", list(rec["years"]))


LANG_NOTE = {"fi": "Päivät koskevat kunnan ruotsinkielisiä kouluja – suomenkielisten koulujen päiviä ei löytynyt erikseen. Suomenkielisten koulujen lomat voivat poiketa, tarkista koululta.",
             "sv": "Uppgifterna gäller kommunens finskspråkiga skolor – de svenskspråkiga skolornas lov hittades inte separat. Svenska skolor kan ha avvikande lov, kontrollera med skolan.",
             "fi_mixed": "Lukuvuosi {y}: päivät koskevat ruotsinkielisiä kouluja (suomenkielisten päiviä ei vielä löytynyt).",
             "sv_mixed": "Läsåret {y}: uppgifterna gäller de finskspråkiga skolorna (de svenskspråkigas lov hittades inte ännu)."}


def lang_note(note, lang):
    if not note:
        return ""
    kind, ys = note
    t = LANG_NOTE[lang] if kind == "other" else " ".join(LANG_NOTE[lang + "_mixed"].format(y=y.replace("-", "–")) for y in ys)
    return f'<p class="lnote">ⓘ {t}</p>'


def slug(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ä", "a").replace("ö", "o").replace("å", "a"))
    return re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if not unicodedata.combining(c))).strip("-")


def d(s):
    return date.fromisoformat(s)


def fmt(a, b=None, year=True, lang="fi"):
    a = d(a)
    if not b or b == a.isoformat():
        return f"{T[lang]['wd'][a.weekday()]} {a.day}.{a.month}." + (f"{a.year}" if year else "")
    b = d(b)
    if a.year == b.year:
        return f"{a.day}.{a.month}.–{b.day}.{b.month}." + (f"{b.year}" if year else "")
    if not year:
        return f"{a.day}.{a.month}.–{b.day}.{b.month}."
    return f"{a.day}.{a.month}.{a.year}–{b.day}.{b.month}.{b.year}"


def week(s):
    return d(s).isocalendar()[1]


def icon(kind, size=24, color=None):
    h = HOL[kind]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color or h["c"]}" stroke-width="2.4" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{h["icon"]}</svg>')


# staattiset painot (ei variable-fonttia: iOS Safari piirsi variable-fontin lihavat kirjaimet päällekkäin dynaamisessa listassa)
CSS = """@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-400-normal.woff2) format("woff2");font-weight:400;font-style:normal;font-display:swap;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-ext-400-normal.woff2) format("woff2");font-weight:400;font-style:normal;font-display:swap;unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-700-normal.woff2) format("woff2");font-weight:700;font-style:normal;font-display:swap;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-ext-700-normal.woff2) format("woff2");font-weight:700;font-style:normal;font-display:swap;unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-800-normal.woff2) format("woff2");font-weight:800;font-style:normal;font-display:swap;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-ext-800-normal.woff2) format("woff2");font-weight:800;font-style:normal;font-display:swap;unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-900-normal.woff2) format("woff2");font-weight:900;font-style:normal;font-display:swap;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-ext-900-normal.woff2) format("woff2");font-weight:900;font-style:normal;font-display:swap;unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:17px/1.55 Nunito,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;font-synthesis:none;color:#2A1B0F;background:var(--tint,#FFF6E5);font-variant-numeric:tabular-nums}
a{color:#9A3D06}a:hover{color:#7A3005}:focus-visible{outline:3px solid #1D6FB8;outline-offset:2px}
.wrap{max-width:1160px;margin:0 auto;padding:0 20px}
.pv{background:#FFE08A;padding:8px 20px;font-size:14px;font-weight:700;text-align:center}
header.top{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:16px 0}
.brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:#2A1B0F;font-weight:900;font-size:22px}
.brand span{color:#C2410C}
.search{flex:1 1 260px;max-width:440px;margin-left:auto}
.search input{display:block;width:100%;height:52px;border:0;border-radius:99px;padding:0 22px;font:700 17px Nunito,system-ui;background:#fff;box-shadow:0 4px 0 #F0D9B5;color:#2A1B0F}
.search input:focus{outline:3px solid var(--hero,#E8741E)}
.ac{position:relative}.acl{position:absolute;left:0;right:0;top:calc(100% + 8px);background:#fff;border-radius:22px;padding:8px;box-shadow:0 10px 30px rgba(42,27,15,.2);z-index:20;text-align:left}
.aco{display:flex;flex-direction:column;justify-content:center;min-height:56px;padding:6px 16px;border-radius:16px;text-decoration:none;color:#2A1B0F}
.aco b{font-size:18px;font-weight:800}.aco b small{font-weight:700;color:#6B5847}.aco span{font-size:14px;font-weight:700;color:#6B5847}.aco mark{background:none;color:inherit;font-weight:900;text-decoration:underline;text-decoration-color:#E8741E;text-decoration-thickness:3px}
.aco.on,.aco:hover{background:#FFF0D6;color:#2A1B0F}.acn{padding:12px 16px;font-weight:700;color:#6B5847}
.search.lg{max-width:none;margin:0;flex:none;width:100%}.search.lg input{height:60px;font-size:19px;padding:0 24px}
.hh{font-size:36px;line-height:1.1;margin:10px 0 4px}.sub{font-size:19px;font-weight:700;color:#5F4B3A;margin:0 0 16px}
.trust{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:14px;font-weight:800;color:#6B5847;margin:14px 0 28px}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.tile{display:flex;flex-direction:column;gap:4px;min-height:132px;padding:16px;border-radius:26px;text-decoration:none;color:#2A1B0F;background:var(--bg);box-shadow:0 5px 0 var(--c)}
.tile:hover{color:#2A1B0F;transform:translateY(-2px)}.tile b{font-size:20px;font-weight:900;margin-top:6px}.tile span{font-size:15px;font-weight:900;color:var(--ct,var(--c))}
.tile .ic{background:#fff}.tile.past{background:#F1ECE4;box-shadow:0 5px 0 #CFC4B5}.tile.past span{color:#5E4E3F}.tile.past .ic{filter:grayscale(1)}
.letters{display:flex;flex-wrap:wrap;gap:8px}.letters a{width:46px;height:46px;border-radius:14px;background:#fff;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;text-decoration:none;color:#2A1B0F;box-shadow:0 3px 0 #F0D9B5}
.letters a:hover{background:var(--hero,#E8741E);color:var(--ht,#fff)}
a.card{text-decoration:none;color:#2A1B0F}a.card:hover{transform:translateY(-2px)}
.grp{display:flex;flex-direction:column;gap:14px}.gh{display:flex;align-items:center;gap:14px}
.wkb{width:62px;height:62px;border-radius:18px;background:var(--bg);color:var(--c);display:flex;flex-direction:column;align-items:center;justify-content:center;flex:none;line-height:1}
.wkb small{font-size:12px;font-weight:800}.wkb b{font-size:24px;font-weight:900}
.az{scroll-margin-top:16px}
.src,.src a,td a{overflow-wrap:anywhere}
.lnote{background:#FFF0C7;border-radius:14px;padding:10px 14px;font-size:15px;font-weight:700;margin:0 0 14px}
.lng{margin:0 0 -6px;text-align:right;font-size:14px;font-weight:800}.lng a{color:#6B5847}
.tabs{display:flex;gap:6px;margin:0 0 12px;flex-wrap:wrap}.tabs button{font:inherit;font-weight:800;font-size:15px;padding:9px 16px;border-radius:999px;border:2px solid #E8D9C4;background:#fff;color:#2A1B0F;cursor:pointer}
.tabs button[aria-selected=true]{background:#2A1B0F;border-color:#2A1B0F;color:#fff}.tabs button:focus-visible{outline:3px solid #E8741E;outline-offset:2px}
@media print{@page{margin:14mm}body{background:#fff;font-size:12pt}.pv,header.top,footer.bot,.btns,details,.share,.bar,form,#cd+.unit+button{display:none!important}
.hero,.grid{display:none!important}.layout{display:block}.box{padding:0;box-shadow:none;border:0}table{font-size:12pt}
a{color:#000;text-decoration:none}h1{font-size:22pt;margin:0 0 8px}main::after{content:"koululomat.fi – tiedot kunnan omasta lähteestä";display:block;margin-top:12px;font-size:10pt}}
.cmpr{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px solid #F2E6D3;font-size:16px}.cmpr span{font-weight:700;color:#5F4B3A}.cmpr b{text-align:right}
.sr{position:absolute;left:-9999px}
h1{font-size:30px;line-height:1.15;font-weight:900;margin:8px 0 16px}
h2{font-size:22px;font-weight:900;margin:0 0 10px}
.hero{background:var(--hero,#E8741E);color:var(--ht,#fff);border-radius:36px;padding:28px 22px 24px;text-align:center;box-shadow:0 7px 0 var(--hs,#B4530F);display:flex;flex-direction:column;align-items:center;gap:2px;height:100%;justify-content:center}
.hero.est{background:#9B6B45;box-shadow:0 7px 0 #6E4A2F;color:#fff}
.hero .lead{font-size:20px;font-weight:800;margin:6px 0 0}
.hero .big{font-size:120px;line-height:.95;font-weight:900;letter-spacing:-.03em}
.hero .unit{font-size:30px;font-weight:900;margin:0}
.share{display:inline-flex;align-items:center;gap:8px;min-height:48px;margin:12px 0 4px;padding:0 20px;border-radius:99px;border:2px solid currentColor;background:rgba(0,0,0,.2);color:inherit;font:900 17px Nunito,system-ui;cursor:pointer}.share:hover{background:rgba(0,0,0,.3)}.share[hidden]{display:none}
.hero .when{font-size:19px;font-weight:800;margin:8px 0 0}
.bar{width:100%;max-width:420px;margin-top:14px}.bar>div{height:18px;border-radius:99px;background:var(--track,rgba(255,255,255,.3));overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px;background:var(--bar,#FFE08A)}.bar p{margin:6px 0 0;font-size:19px;font-weight:800}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.card{background:#fff;border-radius:26px;padding:16px;box-shadow:0 4px 0 #F0D9B5;display:flex;flex-direction:column;gap:2px}
.card.now{outline:3px solid var(--c);box-shadow:0 4px 0 var(--c)}.card.card.past{background:#FAF7F2}.card.past .ic{filter:grayscale(1)}.card.past .dt{color:#5E4E3F}
.ic{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;margin-bottom:8px}
.card b{font-size:18px;font-weight:900}.card .dt{font-weight:700;color:#5F4B3A}.card .n{font-size:15px;font-weight:900;margin-top:4px}
.btns{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:54px;padding:0 24px;border-radius:99px;background:#2A1B0F;color:#fff;text-decoration:none;font-weight:900;font-size:17px;box-shadow:0 4px 0 #000;flex:1 1 220px;border:0;cursor:pointer;font-family:inherit}
.btn:hover{color:#fff;filter:brightness(1.2)}
.btn.alt{background:#fff;color:#2A1B0F;box-shadow:0 4px 0 #F0D9B5}.btn.alt:hover{color:#2A1B0F}
.box{background:#fff;border-radius:26px;padding:20px 22px;margin:18px 0}
table{width:100%;border-collapse:collapse;font-size:16px}th,td{text-align:left;padding:10px 6px;border-top:1px solid #F2E6D3;vertical-align:top}
th{font-weight:700;color:#5F4B3A}thead th{border-top:0;font-size:14px}
.b{display:inline-block;font-size:12px;font-weight:900;padding:3px 10px;border-radius:99px;white-space:nowrap}
.ok{background:#DFF3E4;color:#17602E}.one{background:#E1ECFA;color:#1D4F91}.prop{background:#FFF0D6;color:#8A5300}.est{background:#FDE2E1;color:#9B1C1C}
.src{font-size:14px;color:#6B5847}
.layout{display:flex;flex-wrap:wrap;gap:24px;align-items:stretch}.layout>div{flex:1 1 400px}.layout .grid{height:100%;grid-auto-rows:1fr}.layout .card .n{margin-top:auto;font-size:21px}
details{background:#fff;border-radius:26px;padding:16px 22px;margin:18px 0}summary{cursor:pointer;font-weight:900;min-height:30px}
form label{display:block;font-size:15px;font-weight:700;margin:10px 0 4px}
form textarea,details input{width:100%;padding:10px 12px;border:2px solid #F0D9B5;border-radius:14px;font:16px Nunito,system-ui}
.hp{position:absolute;left:-5000px}
.list{columns:3 210px;column-gap:20px;padding:0;list-style:none;margin:0}.list li{break-inside:avoid;padding:4px 0}
.list a{text-decoration:none;font-weight:700;color:#2A1B0F;display:inline-block;min-height:28px}.list a:hover{color:#9A3D06}
.wk{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
footer.bot{padding:26px 0 40px;font-size:14px;color:#6B5847;text-align:center}
""" + articles.CSS + """
@media(min-width:900px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}.hh{font-size:48px}h1{font-size:40px}.hero .big{font-size:160px}.hero{padding:36px}}
@media(max-width:420px){.hero .big{font-size:104px}.card{padding:14px}}"""



def search_form(fid, placeholder=None, big=False, prefix=None, main=False, pick=None, lang="fi"):
    placeholder = placeholder or T[lang]["ph"]
    pre = (f' data-prefix="{prefix}"' if prefix else "") + (f' data-pick="{pick}"' if pick else "")
    return (f'<form class="search{" lg" if big else ""}" action="{"/sv/" if lang == "sv" else "/haku/"}" role="search" aria-label="{html.escape(placeholder)}"{pre}{" data-main" if main else ""}>'
            f'<label class="sr" for="{fid}">{T[lang]["search"]}</label><div class="ac"><input id="{fid}" name="q" type="search" placeholder="{placeholder}" '
            f'role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="{fid}-l" autocomplete="off" autocapitalize="words" spellcheck="false">'
            f'<div class="acl" id="{fid}-l" role="listbox" hidden></div></div></form>')


def theme_style(t):
    h, hs, ht, tint, bar, track = THEME[t]
    return f"--hero:{h};--hs:{hs};--ht:{ht};--tint:{tint};--bar:{bar};--track:{track}"


def fit(*cands, n=62):
    """Ensimmäinen otsikkovaihtoehto, joka mahtuu Googlen hakutulokseen (~60 merkkiä)."""
    return next((c for c in cands if len(c) <= n), cands[-1])


def short_title(t, n=62):
    if len(t) <= n:
        return t
    if t.endswith(" | Koululomat"):
        t = t[:-13]
    if len(t) > n:  # katkaise luontevasta kohdasta ("…2026? Joulujuhla…" -> "…2026?")
        cut = [i + 1 for i, c in enumerate(t) if c in "?:" and 25 < i < n] + [i for i in range(25, min(n, len(t))) if t[i:i + 3] == " – "]
        if cut:
            t = t[:max(cut)].rstrip(" –:")
    return t


# fi <-> sv -vastinesivut (hreflang)
ALT = {"/fi/syysloma/": "/sv/hostlov/", "/fi/joululoma/": "/sv/jullov/", "/fi/hiihtoloma-2027/": "/sv/sportlov-2027/",
       "/fi/kesaloma/": "/sv/sommarlov/", "/artikkelit/hiihtoloma-2027/": "/sv/artiklar/sportlov-2027/",
       "/artikkelit/joululoma-2026/": "/sv/artiklar/jullov-2026/", "/": "/sv/"}
ALT_REV = {v: k for k, v in ALT.items()}


def page(title, desc, body, path, schema=None, theme="brand", top_search=True, lang="fi", alt=None):
    title = short_title(title)
    if not alt and (path in ALT or path in ALT_REV):
        alt = {"fi": ALT_REV.get(path, path), "sv": ALT.get(path, path)}
    robots = '<meta name="robots" content="noindex,nofollow">' if PREVIEW else ""
    pv = f'<div class="pv">{T[lang]["pv"]}</div>' if PREVIEW else ""
    hl = "".join(f'<link rel="alternate" hreflang="{lg}" href="{BASE}{p}">' for lg, p in (alt or {}).items())
    sd = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{robots}
<link rel="canonical" href="{BASE}{path}">{hl}<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/logo.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon-180.png"><link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="{THEME[theme][0]}">
<link rel="preload" href="/fonts/nunito-latin-900-normal.woff2" as="font" type="font/woff2" crossorigin><link rel="preload" href="/fonts/nunito-latin-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}</style>{sd}<script src="/ac.js" defer></script></head><body style="{theme_style(theme)}">{pv}
<div class="wrap"><header class="top"><a class="brand" href="{T[lang]["home"]}">{LOGO.format(s=40)}<b>Koulu<span>lomat</span></b></a>
{search_form("q", lang=lang) if top_search else ""}</header>
<main>{body}</main>
<footer class="bot">{T[lang]["foot"]}<br>© {date.today().year} {OWNER}</footer></div>
</body></html>"""


def badge(conf, lang="fi"):
    c = CONF[conf][1]
    return f'<span class="b {c}" title="{html.escape(T[lang]["tip"][conf])}">{T[lang]["conf"][conf]}</span>'


def nights(target, today):
    return max((target - today).days, 0)


def yo(n):
    return "yö" if n == 1 else "yötä"


def holidays_of(rec):
    """Lomat aikajärjestyksessä: (avain, alku, loppu, lukuvuosi, tila)."""
    out = []
    for y, v in sorted(rec["years"].items()):
        f = v["fields"]
        for k in ("syys", "joulu", "talvi"):
            if k in f:
                out.append((k, d(f[k]["start"]), d(f[k]["end"]), y, v["confidence"]))
        if "end" in f:
            e = d(f["end"]["start"])
            out.append(("kesa", e + timedelta(1), date(e.year, 8, 1), y, v["confidence"]))
    return sorted(out, key=lambda h: h[1])


SHARE_SVG = ('<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" '
             'stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>'
             '<path d="M8.6 13.5l6.8 4M15.4 6.5l-6.8 4"/></svg>')


def share_btn(name, hol=None, text=None, lang="fi"):
    attrs = f' data-name="{html.escape(name)}"' + (f' data-hol="{hol}"' if hol else "") + (f' data-text="{html.escape(text)}"' if text else "")
    return f'<button class="share" type="button" hidden{attrs}>{SHARE_SVG}<span>{T[lang]["share"]}</span></button>'


def hero(rec, today, lang="fi"):
    L = T[lang]
    nm = rec["name"] if lang == "fi" else (rec.get("name_sv") or rec["name"])
    allh = holidays_of(rec)
    nxt = [h for h in allh if h[2] >= today]
    if not nxt:
        return ""
    k, a, b, y, conf = nxt[0]
    ongoing = a <= today <= b
    n = nights(a, today)
    # edistymispalkki: edellisen loman lopusta (tai koulun alusta) tämän loman alkuun
    cands = [h[2] + timedelta(1) for h in allh if h[2] < a]
    ts = rec["years"].get(y, {}).get("fields", {}).get("start")
    if ts:
        cands.append(d(ts["start"]))
    cands = [c for c in cands if c < a]
    bar = ""
    if cands and not ongoing:
        s0 = max(cands)
        if s0 <= today:
            pct = max(0, min(100, round(100 * (today - s0).days / max(1, (a - s0).days))))
            bar = f'<div class="bar"><div><i style="width:{pct}%"></i></div><p>{L["bar"]} {pct} %</p></div>'
    name = L["hol"][k]
    when = (f"{L['starts']} {fmt(a.isoformat(), lang=lang)}" if k == "kesa" else fmt(a.isoformat(), b.isoformat())) + \
           (f" · {L['week']} {week(a.isoformat())}" if k in ("syys", "talvi") else "")
    if ongoing:
        body = f'<p class="lead">{L["now"](k)}</p><div class="big" aria-hidden="true">🎉</div>{share_btn(nm, text=f"{nm}: {L["now"](k)}", lang=lang)}'
    else:
        hv = name.lower() if lang == "fi" else name.lower() + "et"
        body = (f'<p class="lead">{L["to"](k)}</p><div class="big" id="cd" data-d="{a.isoformat()}">{n}</div>'
                f'<p class="unit">{L["night"](n)}!</p>{share_btn(nm, hol=hv, lang=lang)}')
    est = conf == "arvio"
    return (f'<section class="hero{" est" if est else ""}" data-live aria-label="{"Lähtölaskuri" if lang == "fi" else "Nedräkning"}">{icon(k, 64, "currentColor")}{body}'
            f'<p class="when">{when}{f" ({L["est"]})" if est else ""}</p><p style="margin:6px 0 0">{badge(conf, lang)}</p>{bar}</section>')


def next_kind(rec, today):
    nx = [h for h in holidays_of(rec) if h[2] >= today]
    return (nx[0][0], nx[0][1]) if nx else (None, None)


def cards(rec, today, year, lang="fi"):
    L = T[lang]
    v = rec["years"].get(year)
    if not v:
        return ""
    f = v["fields"]
    allh = holidays_of(rec)
    nxt = next((h for h in allh if h[2] >= today), None)
    items = []
    for k in ("syys", "joulu", "talvi", "kesa"):
        if k == "kesa":
            if "end" not in f:
                continue
            a = d(f["end"]["start"]) + timedelta(1)
            b = date(a.year, 8, 1)
            dt = f"{L['starts']} {a.day}.{a.month}."
        else:
            if k not in f:
                continue
            a, b = d(f[k]["start"]), d(f[k]["end"])
            dt = fmt(f[k]["start"], f[k]["end"], year=False) + (f" · {L['wk']} {week(f[k]['start'])}" if k in ("syys", "talvi") else "")
        past = b < today
        if past:
            n = L["past"]
        elif a <= today:
            n = L["onhol"]
        else:
            nn = nights(a, today)
            n = f"{nn} {L['night'](nn)}"
        now = bool(nxt and nxt[0] == k and nxt[3] == year)
        h = HOL[k]
        cls = " now" if now else (" past" if past else "")
        tag = (f'a href="{HPAGE[k][0]}"' if lang == "fi" else f'a href="{sv_pages.HPAGE_SV[k][0]}"') + f' data-k="{k}" data-a="{a.isoformat()}" data-b="{b.isoformat()}"'
        items.append(f'<{tag} class="card{cls}" style="--c:{h["c"]}"><div class="ic" style="background:{h["bg"]}">{icon(k, 26)}</div>'
                     f'<b>{L["hol"][k]}</b><span class="dt">{dt}</span><span class="n" style="color:{"#6B5847" if past else h["c"]}">{n}</span></{tag.split()[0]}>')
    return f'<div class="grid">{"".join(items)}</div>'


def adult_table(rec, lang="fi"):
    L = T[lang]
    years = sorted(rec["years"].items())
    if not years:
        return ""
    rows = list(zip(L["rows"], ("start", "syys", "joulu", "talvi", "end")))
    head = "".join(f"<th>{y.replace('-', '–')}<br>{badge(v['confidence'], lang)}</th>" for y, v in years)
    body = ""
    for label, k in rows:
        cells = ""
        for y, v in years:
            x = v["fields"].get(k)
            if not x:
                cells += "<td>–</td>"
            elif k in ("start", "end"):
                cells += f"<td>{fmt(x['start'], lang=lang)}</td>"
            else:
                cells += f"<td>{fmt(x['start'], x['end'])}" + (f" <small>({L['wk']} {week(x['start'])})</small>" if k in ("syys", "talvi") else "") + "</td>"
        body += f"<tr><th scope='row'>{label}</th>{cells}</tr>"
    srcs = []
    for y, v in years:
        yy = y.replace("-", "–")
        if v.get("source"):
            s = re.sub(r"^https?://(www\.)?", "", v["source"])[:70]
            if v.get("days_doc") and v.get("days_doc") == v.get("days_expected") and v.get("days_calc") != v.get("days_doc"):
                extra = f" · {L['docd']} {v['days_doc']} ({L['law']} {v['days_expected']})"
            else:
                extra = (f" · {L['calc']} {v['days_calc']}" + (f" ({L['law']} {v['days_expected']})" if v.get("days_expected") else "")) if v.get("days_calc") else ""
            srcs.append(f'{yy}: <a href="{html.escape(v["source"])}" rel="nofollow">{html.escape(s)}</a>{extra}')
        else:
            srcs.append(f"{yy}: {L['noyear']}")
    upd = d(max(v["updated"] for _, v in years))
    perus = (f'<div style="overflow-x:auto"><table><thead><tr><th>{L["perus"]}</th>{head}</tr></thead>'
             f'<tbody>{body}</tbody></table></div><p class="src">{L["note"]}<br>'
             f'{L["src"]} – {" · ".join(srcs)}. {L["upd"]} {upd.day}.{upd.month}.{upd.year}.</p>')
    tabs = [("perus", L["tabs"][0], perus)]
    for F, nm, full in (("esi", L["tabs"][1], L["full"][0]), ("lukio", L["tabs"][2], L["full"][1])):
        tabs.append((F, nm, form_table(rec, F, full, upd, lang)))
    btns = "".join(f'<button type="button" role="tab" id="t-{F}" aria-controls="p-{F}" aria-selected="{"true" if i == 0 else "false"}"'
                   f'{"" if i == 0 else " tabindex=-1"}>{nm}</button>' for i, (F, nm, _) in enumerate(tabs))
    panels = "".join(f'<div role="tabpanel" id="p-{F}" aria-labelledby="t-{F}" class="tp">{c}</div>' for F, _, c in tabs)
    return (f'<section class="box"><h2>{L["adult"]}</h2><div class="tabs" role="tablist" aria-label="{L["tabl"]}" hidden>{btns}</div>'
            f'{panels}</section>')


FORM_KEYS = ("start", "syys", "term1_end", "joulu", "term2_start", "talvi", "end")


def form_table(rec, F, full, upd, lang="fi"):
    L = T[lang]
    fy = (rec.get("forms") or {}).get(F) or {}
    years = sorted(fy.items())
    if not years:
        return f'<p class="src" style="font-size:15px">{L["fnone"](full, F)}</p>'
    head = "".join(f"<th>{y.replace('-', '–')}<br>{badge('yksi_lähde', lang)}</th>" for y, _ in years)
    body = ""
    for label, k in zip(L["frows"], FORM_KEYS):
        if not any(k in r for _, r in years):
            continue
        cells = ""
        for _, r in years:
            x = r.get(k)
            if not x:
                cells += "<td>–</td>"
            elif k in ("syys", "joulu", "talvi"):
                cells += f"<td>{fmt(x['start'], x['end'])}" + (f" <small>({L['wk']} {week(x['start'])})</small>" if k in ("syys", "talvi") else "") + "</td>"
            else:
                cells += f"<td>{fmt(x['start'], lang=lang)}</td>"
        body += f"<tr><th scope='row'>{label}</th>{cells}</tr>"
    srcs = sorted({u for _, r in years for x in r.values() for u in x.get("sources", [])})
    sl = " · ".join(f'<a href="{html.escape(u)}" rel="nofollow">{html.escape(re.sub(r"^https?://(www[.])?", "", u)[:70])}</a>' for u in srcs[:3])
    return (f'<div style="overflow-x:auto"><table><thead><tr><th>{full}</th>{head}</tr></thead><tbody>{body}</tbody></table></div>'
            f'<p class="src">{L["fsrc"]}<br>{L["src"]} – {sl}. {L["upd"]} {upd.day}.{upd.month}.{upd.year}.</p>')


def live(rec, lang, year):
    """Selaimen laskuri (live.js): lomat + valmiit palat, jotta laskuri ja kortit ovat oikein rakennusten välilläkin."""
    nm = rec["name"] if lang == "fi" else (rec.get("name_sv") or rec["name"])
    blob = {"h": [[k, a.isoformat(), b.isoformat(), y, c] for k, a, b, y, c in holidays_of(rec)],
            "s": {y: v["fields"]["start"]["start"] for y, v in rec["years"].items() if "start" in v["fields"]},
            "i": {k: icon(k, 64, "currentColor") for k in HOL}, "n": nm, "cy": year,
            "sh": f'{SHARE_SVG}<span>{T[lang]["share"]}</span>', "bd": {c: badge(c, lang) for c in CONF},
            "th": {t: theme_style(t) for t in THEME}}
    js = json.dumps(blob, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="hd">{js}</script><script src="/live.js"></script>'


def ics(rec, lang="fi", url=None):
    nm = rec["name"] if lang == "fi" else (rec.get("name_sv") or rec["name"])
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//Koululomat//{lang.upper()}", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:Koululomat – {nm}", "X-PUBLISHED-TTL:P1W"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for y, v in rec["years"].items():
        for k in ("syys", "joulu", "talvi"):
            x = v["fields"].get(k)
            if not x:
                continue
            a, b = d(x["start"]), d(x["end"])
            while (b + timedelta(1)).weekday() >= 5:
                b += timedelta(1)
            tag = "" if v["confidence"] in ("varmistettu", "yksi_lähde") else f" ({T[lang]['conf'][v['confidence']].lower()})"
            lines += ["BEGIN:VEVENT", f"UID:{rec['id']}-{y}-{k}{'' if lang == 'fi' else '-' + lang}@koululomat.fi", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{a.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(b + timedelta(1)).strftime('%Y%m%d')}",
                      f"SUMMARY:{T[lang]['hol'][k]} – {nm}{tag}", f"URL:{url or BASE + '/fi/' + slug(rec['name']) + '/'}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


REPORT_FORM = """<details><summary>Ilmoita oikea päivä tai virhe</summary>
<form method="post" action="/api/report"><input type="hidden" name="municipality" value="{id}"><input type="hidden" name="back" value="{back}"><input type="hidden" name="lang" value="fi">
<label for="m{id}">Mikä on väärin tai puuttuu?</label><textarea id="m{id}" name="message" rows="3" maxlength="600" required></textarea>
<label for="s{id}">Linkki kunnan tai koulun lähteeseen (jos on)</label><input id="s{id}" name="source_url" type="url" maxlength="300">
<input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true"><p><button class="btn" type="submit">Lähetä</button></p>
<p class="src">Emme tallenna nimeä, sähköpostia emmekä IP-osoitetta. Luemme linkin ja tarkistamme tiedon.</p></form></details>"""

REPORT_FORM_SV = """<details><summary>Meddela rätt datum eller ett fel</summary>
<form method="post" action="/api/report"><input type="hidden" name="municipality" value="{id}"><input type="hidden" name="back" value="{back}"><input type="hidden" name="lang" value="sv">
<label for="m{id}">Vad är fel eller saknas?</label><textarea id="m{id}" name="message" rows="3" maxlength="600" required></textarea>
<label for="s{id}">Länk till kommunens eller skolans källa (om du har)</label><input id="s{id}" name="source_url" type="url" maxlength="300">
<input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true"><p><button class="btn" type="submit">Skicka</button></p>
<p class="src">Vi sparar inte namn, e-post eller IP-adress. Vi läser länken och kontrollerar uppgiften.</p></form></details>"""

# laskuri päivittyy selaimessa, vaikka sivu olisi rakennettu aiemmin
COUNTDOWN_JS = """<script>(function(){var e=document.getElementById('cd');if(!e)return;var t=new Date(e.dataset.d+'T00:00:00'),n=new Date();n.setHours(0,0,0,0);
var x=Math.round((t-n)/864e5),sv=document.documentElement.lang=='sv';if(x>=0){e.textContent=x;var u=e.nextElementSibling;if(u)u.textContent=(x==1?(sv?'natt':'yö'):(sv?'nätter':'yötä'))+'!';}})();</script>"""


def build(data_path, out_dir):
    raw = json.loads(Path(data_path).read_text())
    data, fi_note = [], {}
    for r in raw:
        v, note = view(r, "fi")
        data.append(v)
        fi_note[r["id"]] = note
    raw_by_id = {r["id"]: r for r in raw}
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    today = date.today()
    urls = ["/"]
    datalist = ""  # korvattu omalla ennakoivalla haulla (ac.js + kunnat.json)

    def write(path, content):
        p = out / path.lstrip("/")
        if path.endswith("/"):
            p = p / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    y1 = "2026-2027"
    ac = []
    sv_recs = [r for r in data if r["name"] in SV_MUNS or r["region"] == "Ahvenanmaa" or r["name"].startswith("Maarianhamina")]
    sv_slug = {r["id"]: slug(r.get("name_sv") or r["name"]) for r in sv_recs}
    assert len(set(sv_slug.values())) == len(sv_slug)
    for rec in data:
        s = slug(rec["name"])
        alt = {"fi": f"/fi/{s}/", "sv": f"/sv/{sv_slug[rec['id']]}/"} if rec["id"] in sv_slug else None
        sv = f" ({rec['name_sv']})" if rec.get("name_sv") and rec["name_sv"] != rec["name"] else ""
        nk, nd = next_kind(rec, today) if rec["years"] else (None, None)
        if rec["years"]:
            top = f'<div class="layout"><div>{hero(rec, today)}</div><div>{cards(rec, today, y1)}</div></div>'
        else:
            top = '<section class="box"><p>Tämän kunnan lomia ei vielä löytynyt. Jos tiedät lähteen, ilmoita se alla – luemme sen.</p></section>'
        cmp_url = HPAGE[nk][0] if nk else "/fi/hiihtoloma-2027/"
        body = ((f'<p class="lng"><a href="{alt["sv"]}" hreflang="sv" lang="sv">På svenska</a></p>' if alt else "")
                + f'<h1>{rec["name"]}{sv}: koulujen lomat</h1>{lang_note(fi_note[rec["id"]], "fi")}{top}'
                f'<div class="btns"><a class="btn" href="/fi/{s}/lomat.ics">Lisää lomat kalenteriin</a>'
                f'<a class="btn alt" href="/vertaa/?a={s}">Vertaa toiseen kuntaan</a>'
                f'<button class="btn alt" id="kuva" type="button" hidden data-s="{s}" data-y="{y1}"><span>Tallenna kuvana</span></button>'
                f'<button class="btn alt" id="tulosta" type="button" hidden><span>Tulosta</span></button></div>'
                f'<script src="/kuva.js" defer></script>'
                f'{adult_table(rec)}{REPORT_FORM.format(id=rec["id"], back=f"/fi/{s}/")}{live(rec, "fi", y1) if rec["years"] else ""}')
        tal = (rec["years"].get(y1) or {}).get("fields", {}).get("talvi")
        desc = (f"{rec['name']}: syysloma, joululoma ja hiihtoloma" + (f" (vk {week(tal['start'])})" if tal else "")
                + " sekä koulun alku ja loppu. Lähtölaskuri ja lähteet.")
        schema = {"@context": "https://schema.org", "@type": "WebPage", "name": f"Koulujen lomat {rec['name']}",
                  "about": {"@type": "City", "name": rec["name"]}}
        th = "brand" if not nk or rec["years"].get(y1, {}).get("confidence") == "arvio" else nk
        nm0 = rec["name"].split(" - ")[0]
        ttl = fit(*([f"{nm0}: koulujen lomat 2026–27, hiihtoloma vk {week(tal['start'])} | Koululomat",
                     f"{nm0}: koululomat 2026–27, hiihtoloma vk {week(tal['start'])}"] if tal and rec["years"][y1]["confidence"] != "arvio" else []),
                  f"{nm0}: koulujen lomat 2026–2027 | Koululomat", f"{nm0}: koulujen lomat 2026–2027")
        write(f"/fi/{s}/", page(ttl, desc, body, f"/fi/{s}/", schema, theme=th, alt=alt))
        (out / "fi" / s / "lomat.ics").write_text(ics(rec), encoding="utf-8")
        urls.append(f"/fi/{s}/")
        ac.append({"n": rec["name"], "sv": rec.get("name_sv") or "", "s": s, "r": rec["region"],
                   "u": [[k, a.isoformat(), b.isoformat()] for k, a, b, _, _ in holidays_of(rec) if b >= today], "t": bool(tal),
                   **({"ss": sv_slug[rec["id"]]} if rec["id"] in sv_slug else {})})
        if tal:
            yv = rec["years"][y1]
            n = nights(d(tal["start"]), today)
            est = yv["confidence"] == "arvio"
            hb = (f'<h1>Hiihtoloma 2027 – {rec["name"]}</h1><section class="hero{" est" if est else ""}">{icon("talvi", 64, "currentColor")}'
                  f'<p class="lead">Hiihtolomaan on</p><div class="big" id="cd" data-d="{tal["start"]}" data-e="{tal["end"]}" data-k="talvi">{n}</div><p class="unit">{yo(n)}!</p>{share_btn(rec["name"], hol="hiihtoloma")}'
                  f'<p class="when">{fmt(tal["start"], tal["end"])} · viikko {week(tal["start"])}{" (arvio)" if est else ""}</p>'
                  f'<p style="margin:6px 0 0">{badge(yv["confidence"])}</p></section>'
                  f'<div class="btns"><a class="btn" href="/fi/{s}/lomat.ics">Lisää kalenteriin</a><a class="btn alt" href="/fi/{s}/">Kaikki lomat: {rec["name"]}</a>'
                  f'<a class="btn alt" href="/fi/hiihtoloma-2027/">Muut kunnat</a></div>{adult_table(rec)}<script src="/live.js"></script>')
            write(f"/fi/hiihtoloma-2027/{s}/", page(f"Hiihtoloma 2027 {rec['name']} – viikko {week(tal['start'])} | Koululomat",
                                                     f"{rec['name']}: hiihtoloma 2027 on {fmt(tal['start'], tal['end'])} (viikko {week(tal['start'])}). Lähtölaskuri ja lähde.",
                                                     hb, f"/fi/hiihtoloma-2027/{s}/", theme="talvi"))
            urls.append(f"/fi/hiihtoloma-2027/{s}/")
    lomat = {}
    for rec in data:
        yy = {}
        for y, v in rec["years"].items():
            f = v["fields"]
            e = {"c": v["confidence"]}
            for k in ("syys", "joulu", "talvi"):
                if k in f:
                    e[k] = [f[k]["start"], f[k]["end"]]
            if "end" in f:
                e["kesa"] = f["end"]["start"]
            yy[y] = e
        lomat[slug(rec["name"])] = {"n": rec["name"], "y": yy}
    (out / "lomat.json").write_text(json.dumps(lomat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write("/vertaa/", page("Vertaa kahden kunnan koululomia | Koululomat",
                           "Vertaa kahden kunnan syys-, joulu-, hiihto- ja kesälomia. Näet heti, onko lomaa yhtä aikaa.",
                           f'<h1>Vertaa kahta kuntaa</h1><p class="sub">Esimerkiksi oma kunta ja mummola tai serkkujen kunta: onko lomaa yhtä aikaa?</p>'
                           f'<div class="layout" style="gap:12px">{search_form("qa", "Ensimmäinen kunta", big=True, pick="a")}{search_form("qb", "Toinen kunta", big=True, pick="b")}</div>'
                           f'<div id="cmp" data-year="2026-2027"></div><noscript><p class="box">Vertailu tarvitsee JavaScriptin. Voit katsoa kuntien lomat myös <a href="/haku/">kuntalistasta</a>.</p></noscript><script src="/vertaa.js" defer></script>', "/vertaa/", top_search=False))
    urls.append("/vertaa/")
    (out / "kunnat.json").write_text(json.dumps(sorted(ac, key=lambda x: x["n"]), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # svenska: tvåspråkiga kommuner och Åland
    L = T["sv"]
    sv_items = []
    sv_lomat, sv_views = {}, []
    for rec0 in sorted(sv_recs, key=lambda r: slug(r.get("name_sv") or r["name"])):
        rec, note = view(raw_by_id[rec0["id"]], "sv")
        s, ss = slug(rec["name"]), sv_slug[rec["id"]]
        nm = rec.get("name_sv") or rec["name"]
        fi_nm = rec["name"].split(" - ")[0]
        alt = {"fi": f"/fi/{s}/", "sv": f"/sv/{ss}/"}
        nk, nd = next_kind(rec, today) if rec["years"] else (None, None)
        if rec["years"]:
            top = f'<div class="layout"><div>{hero(rec, today, "sv")}</div><div>{cards(rec, today, y1, "sv")}</div></div>'
        else:
            top = '<section class="box"><p>Kommunens lov har inte hittats ännu. Om du känner till källan, meddela den nedan – vi läser den.</p></section>'
        body = (f'<p class="lng"><a href="/fi/{s}/" hreflang="fi" lang="fi">Suomeksi</a></p>'
                f'<h1>{nm}{f" ({fi_nm})" if fi_nm != nm else ""}: skolornas lov</h1>{lang_note(note, "sv")}{top}'
                f'<div class="btns"><a class="btn" href="/sv/{ss}/lov.ics">Lägg till i kalendern</a>'
                f'<button class="btn alt" id="kuva" type="button" hidden data-s="{s}" data-y="{y1}" data-n="{html.escape(nm)}" data-l="sv"><span>Spara som bild</span></button>'
                f'<button class="btn alt" id="tulosta" type="button" hidden><span>Skriv ut</span></button></div>'
                f'<script src="/kuva.js" defer></script>{adult_table(rec, "sv")}{REPORT_FORM_SV.format(id=rec["id"], back=f"/sv/{ss}/")}{live(rec, "sv", y1) if rec["years"] else ""}')
        tal = (rec["years"].get(y1) or {}).get("fields", {}).get("talvi")
        desc = (f"{nm}: höstlov, jullov och sportlov" + (f" (vecka {week(tal['start'])})" if tal else "") + " samt skolans start och slut. Nedräkning och källor.")
        th = "brand" if not nk or rec["years"].get(y1, {}).get("confidence") == "arvio" else nk
        write(f"/sv/{ss}/", page(fit(*([f"{nm}: skolornas lov 2026–27, sportlov v. {week(tal['start'])} | Koululomat"] if tal and rec["years"][y1]["confidence"] != "arvio" else []),
                                     f"{nm}: skolornas lov 2026–2027 | Koululomat", f"{nm}: skolornas lov 2026–2027"), desc, body, f"/sv/{ss}/",
                                 {"@context": "https://schema.org", "@type": "WebPage", "name": f"Skolornas lov {nm}", "inLanguage": "sv",
                                  "about": {"@type": "City", "name": nm}}, theme=th, lang="sv", alt=alt))
        urls.append(f"/sv/{ss}/")
        sv_views.append((rec, ss, nm))
        (out / "sv" / ss / "lov.ics").write_text(ics(rec, "sv", f"{BASE}/sv/{ss}/"), encoding="utf-8")
        sv_lomat[s] = {y: {"c": v["confidence"], **{k: [v["fields"][k]["start"], v["fields"][k]["end"]] for k in ("syys", "joulu", "talvi") if k in v["fields"]},
                           **({"kesa": v["fields"]["end"]["start"]} if "end" in v["fields"] else {})} for y, v in rec["years"].items()}
        nxt = ""
        if nk:
            nn = nights(nd, today)
            nxt = f"{L['hol'][nk]} om {nn} {L['night'](nn)}" if nn > 0 else f"{L['hol'][nk]} nu"
        sv_items.append(f'<li><a href="/sv/{ss}/">{nm}</a></li>')
    for s_, ys_ in sv_lomat.items():
        if s_ in lomat:
            lomat[s_]["sv"] = ys_
    (out / "lomat.json").write_text(json.dumps(lomat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sv_arts, sv_urls = sv_pages.build(sv_views, today, write, {"page": page, "search_form": search_form, "icon": icon, "HOL": HOL, "DARK": DARK,
                                                               "HPAGE": HPAGE, "BASE": BASE, "schema": articles._schema, "faq": articles._faq})
    urls += sv_urls
    sv_tiles = "".join(f'<a class="tile" href="{sv_pages.HPAGE_SV[k][0]}" style="--bg:{HOL[k]["bg"]};--c:{HOL[k]["c"]};--ct:{DARK[k]}">'
                       f'<div class="ic">{icon(k, 26)}</div><b>{T["sv"]["hol"][k]}</b><span>{sv_pages.HPAGE_SV[k][1]}</span></a>' for k in ("syys", "joulu", "talvi", "kesa"))
    sv_acards = "".join(f'<a class="acard" href="{a["path"]}" style="--c:{HOL[a["k"]]["c"]}"><div class="ic" style="background:{HOL[a["k"]]["bg"]};flex:none">{icon(a["k"], 26)}</div>'
                        f'<div><b>{a["title"]}</b><span>{a["sub"]}</span></div></a>' for a in sv_arts)
    sv_body = (f'<p class="lng"><a href="/" hreflang="fi" lang="fi">Suomeksi</a></p><h1 class="hh">Hur många nätter till lovet?</h1>'
               f'<p class="sub">Skriv din kommun.</p>{search_form("q2", big=True, lang="sv")}'
               f'<p class="trust"><span class="b ok">✓ Kommunens egen källa</span>Höstlov, jullov, sportlov och sommarlov 2026–2027</p>'
               f'<h2>Eller se ett lov i taget</h2><div class="tiles">{sv_tiles}</div>'
               + (f'<h2 style="margin-top:30px">Aktuellt</h2><div class="acards">{sv_acards}</div>' if sv_acards else "") +
               f'<h2 style="margin-top:30px">Tvåspråkiga kommuner och Åland</h2><section class="box"><ul class="list" style="columns:2 220px">{"".join(sv_items)}</ul></section>'
               f'<p class="src">Övriga kommuner finns <a href="/haku/" lang="fi">på finska</a>. Uppgifterna kommer från varje kommuns eget beslut om skolornas arbets- och lovtider.</p>')
    write("/sv/", page("Skolornas lov per kommun 2026–2027 | Koululomat",
                       "Hur många nätter till lovet? Skolornas höst-, jul- och sportlov i tvåspråkiga kommuner och på Åland. Uppgifter från kommunernas egna källor.",
                       sv_body, "/sv/", {"@context": "https://schema.org", "@type": "WebSite", "name": "Koululomat", "url": BASE + "/sv/", "inLanguage": "sv"},
                       top_search=False, lang="sv", alt={"fi": "/", "sv": "/sv/"}))
    urls.append("/sv/")

    # lomasivut (väriprofiili loman mukaan)
    def hol_dates(k, rec):
        v = rec["years"].get(y1)
        if not v:
            return None
        f = v["fields"]
        if k == "kesa":
            if "end" not in f:
                return None
            a = d(f["end"]["start"])  # viimeinen koulupäivä
            return a, a, v["confidence"]
        if k not in f:
            return None
        return d(f[k]["start"]), d(f[k]["end"]), v["confidence"]

    arts = articles.build_articles(data, today, write, {"page": page, "search_form": search_form, "icon": icon, "share_btn": share_btn, "HOL": HOL, "BASE": BASE})
    urls += [a["path"] for a in arts]
    acards = "".join(f'<a class="acard" href="{a["path"]}" style="--c:{HOL[a["k"]]["c"]}"><div class="ic" style="background:{HOL[a["k"]]["bg"]};flex:none">{icon(a["k"], 26)}</div>'
                     f'<div><b>{a["title"]}</b><span>{a["sub"]}</span></div></a>' for a in arts)
    ART_LINK = {a["k"]: f'<h2 style="margin-top:30px">Lue myös</h2><div class="acards">{acards.split("</a>")[i]}</a></div>' for i, a in enumerate(arts)}

    summary = {}
    for k in ("syys", "joulu", "talvi", "kesa"):
        groups = defaultdict(list)
        for rec in data:
            x = hol_dates(k, rec)
            if x:
                key = week(x[0].isoformat()) if k in ("syys", "talvi") else x[0]
                groups[key].append((rec, x))
        ok = [x for rs in groups.values() for _, x in rs if x[2] != "arvio"]
        past = bool(ok) and all(x[1] < today for x in ok)
        if k in ("syys", "talvi"):
            ws = sorted({week(x[0].isoformat()) for x in ok})
            line = "vk " + (", ".join(map(str, ws[:-1])) + " tai " + str(ws[-1]) if len(ws) > 1 else str(ws[0])) if ws else ""
        else:
            st = sorted({x[0] for x in ok})
            a, b = (st[0], st[-1]) if st else (None, None)
            verb = "koulu loppuu" if k == "kesa" else "alkaa"
            line = (f"{verb} {a.day}.–{b.day}.{b.month}." if a and a.month == b.month and a != b else f"{verb} {a.day}.{a.month}." if a else "")
        summary[k] = (line + (" · ohi jo" if past else ""), past)
        h = HOL[k]
        path, label = HPAGE[k]
        cols = ""
        for key, rs in sorted(groups.items()):
            n_ok = sum(1 for _, x in rs if x[2] != "arvio")
            if k in ("syys", "talvi"):
                yr = 2026 if k == "syys" else 2027
                mon = date.fromisocalendar(yr, key, 1)
                fri = mon + timedelta(4)
                badge_html = f'<div class="wkb" style="--bg:{h["bg"]};--c:{DARK[k]}"><small>vk</small><b>{key}</b></div>'
                title = f"{mon.day}.{mon.month}.–{fri.day}.{fri.month}.{fri.year}"
            else:
                badge_html = f'<div class="wkb" style="--bg:{h["bg"]};--c:{DARK[k]}"><small>{WD[key.weekday()]}</small><b>{key.day}.{key.month}.</b></div>'
                title = (f"Koulu loppuu {WD[key.weekday()]} {key.day}.{key.month}.{key.year}" if k == "kesa"
                         else f"Alkaa {WD[key.weekday()]} {key.day}.{key.month}.{key.year}")
            link = (lambda r: f"/fi/hiihtoloma-2027/{slug(r['name'])}/") if k == "talvi" else (lambda r: f"/fi/{slug(r['name'])}/")
            li = "".join(f'<li><a href="{link(r)}">{r["name"]}</a>' + (' <span class="b est">arvio</span>' if x[2] == "arvio" else "") + "</li>"
                         for r, x in sorted(rs, key=lambda t: t[0]["name"]))
            cols += (f'<div class="card"><div class="gh">{badge_html}<div><b>{title}</b><div class="dt">{len(rs)} kuntaa'
                     + (f" ({len(rs) - n_ok} arviota)" if n_ok < len(rs) else "") + f'</div></div></div>'
                     f'<ul class="list" style="columns:2 140px;margin-top:12px">{li}</ul></div>')
        intro = {"syys": "Syysloma oli viikolla 41, 42 tai 43 kunnasta riippuen.",
                 "joulu": "Joululoma alkaa kunnasta riippuen 21.–23.12. Mikä on sinun kuntasi?",
                 "talvi": "Hiihtoloman viikko riippuu kunnasta. Mikä on sinun?",
                 "kesa": "Koulu loppuu useimmissa kunnissa lauantaina 5.6.2027. Mikä on sinun kuntasi?"}[k]
        hb = (f'<section class="hero" style="height:auto;text-align:left;align-items:stretch">'
              f'<div style="display:flex;align-items:center;gap:12px">{icon(k, 44, "currentColor")}<h1 style="margin:0;color:inherit">{label} kunnittain</h1></div>'
              f'<p class="lead" style="margin:10px 0 16px">{intro}</p>{search_form("q2", "Kirjoita kuntasi", big=True, prefix="/fi/hiihtoloma-2027/" if k == "talvi" else None)}</section>'
              f'<div class="wk" style="margin-top:22px">{cols}</div>')
        if k in ART_LINK:
            hb += ART_LINK[k]
        write(path, page(f"{label} kunnittain – kaikki kunnat | Koululomat",
                         f"{label}: koulujen loma-ajat kaikissa Suomen kunnissa. Tiedot kuntien omista lähteistä.", hb, path, theme=k, top_search=False))
        urls.append(path)

    # etusivu (E1: haku ensin + lomat värillisinä valintoina)
    n_ok = sum(1 for r in data if (r["years"].get(y1) or {}).get("confidence") in ("varmistettu", "yksi_lähde"))
    tiles = "".join(f'<a class="tile{" past" if summary[k][1] else ""}" href="{HPAGE[k][0]}" style="--bg:{HOL[k]["bg"]};--c:{HOL[k]["c"]};--ct:{DARK[k]}">'
                    f'<div class="ic">{icon(k, 26)}</div><b>{HOL[k]["name"]}</b><span>{summary[k][0]}</span></a>'
                    for k in ("syys", "joulu", "talvi", "kesa"))
    letters_set = sorted({r["name"][0].upper() for r in data}, key=lambda c: "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ".find(c))
    letters = "".join(f'<a href="/haku/#{c}">{c}</a>' for c in letters_set)
    body = (f'<h1 class="hh">Montako yötä lomaan?</h1><p class="sub">Kirjoita kuntasi.</p>'
            f'{search_form("q2", big=True)}'
            f'<p class="trust"><span class="b ok">✓ Kunnan oma lähde</span>{n_ok}/{len(data)} kuntaa</p>'
            f'<h2>Tai katso loma kerrallaan</h2><div class="tiles">{tiles}</div>'
            f'<div class="btns"><a class="btn alt" href="/vertaa/">Vertaa kahta kuntaa – esim. oma kunta ja mummola</a></div>'
            f'<h2 style="margin-top:30px">Ajankohtaista</h2><div class="acards">{acards}</div>'
            f'<h2 style="margin-top:30px">Kaikki kunnat</h2><div class="letters">{letters}</div>')
    body = '<p class="lng"><a href="/sv/" hreflang="sv" lang="sv">På svenska</a></p>' + body
    write("/", page("Koululomat 2026–2027 kunnittain – montako yötä lomaan?",
                    "Montako yötä lomaan? Koulujen syys-, joulu- ja hiihtolomat jokaisessa Suomen kunnassa. Tiedot kuntien omista lähteistä.",
                    body, "/", {"@context": "https://schema.org", "@type": "WebSite", "name": "Koululomat", "url": BASE + "/",
                                "publisher": {"@type": "Organization", "name": "BR Entertainment", "logo": BASE + "/icon-512.png"}},
                    top_search=False, alt={"fi": "/", "sv": "/sv/"}))
    # kaikki kunnat A–Ö (+ haku ilman JavaScriptiä)
    by_letter = defaultdict(list)
    for r in data:
        by_letter[r["name"][0].upper()].append(r)
    az = "".join(f'<section class="box az" id="{c}"><h2>{c}</h2><ul class="list">' + "".join(
        f'<li><a href="/fi/{slug(r["name"])}/">{r["name"]}</a></li>' for r in sorted(by_letter[c], key=lambda r: r["name"])) + "</ul></section>"
        for c in letters_set)
    write("/haku/", page("Kaikki kunnat A–Ö | Koululomat", "Koulujen lomat kaikissa Suomen kunnissa aakkosjärjestyksessä.",
                         f'<h1>Kaikki kunnat</h1>{search_form("q2", big=True, main=True)}<div class="letters" style="margin:20px 0">{letters}</div>{az}',
                         "/haku/", top_search=False))
    urls.append("/haku/")

    write("/tietoa/", page("Tietoa palvelusta | Koululomat", "Miten koulujen lomatiedot kerätään ja tarkistetaan.",
                           f"""<h1>Tietoa palvelusta</h1><section class="box"><p>Koululomat kokoaa koulujen työ- ja loma-ajat jokaisen kunnan omasta lähteestä:
lautakunnan päätöksestä, kunnan verkkosivulta tai sen liitteestä. Muiden koostesivujen tietoja ei kopioida.</p>
<h2>Miten tiedot tarkistetaan</h2><ul><li>Koulupäivät lasketaan luetuista päivistä ja verrataan lakiin (190 päivää, joista vähennetään arkipäiville osuvat itsenäisyyspäivä, loppiainen ja vappu).</li>
<li>Järkevyyssäännöt: esim. syysloma viikoilla 41–44 ja talviloma viikoilla 7–11. Poikkeamat tarkistetaan käsin.</li>
<li>Tilat: {badge("varmistettu")} {badge("yksi_lähde")} {badge("ehdotus")} {badge("arvio")}. Arviota ei koskaan esitetä varmana.</li>
<li>Lähteet haetaan uudelleen säännöllisesti, ja muuttunut sisältö luetaan uudelleen.</li></ul>
<h2>Oikeudet</h2><p>Viranomaisen päätöksiin ei ole tekijänoikeutta (tekijänoikeuslaki 9 §). Päivämäärät ovat faktoja.</p>
<h2>Ylläpitäjä</h2><p>{OWNER}</p></section>""", "/tietoa/"))
    write("/tietosuoja/", page("Tietosuoja | Koululomat", "Koululomat ei käytä evästeitä eikä seurantaa.",
                               f"""<h1>Tietosuoja</h1><section class="box"><p>Palvelu ei käytä evästeitä, analytiikkaa, seurantaa eikä kohdennettua mainontaa.
Sivuilla ei ladata ulkopuolisia skriptejä tai fontteja. Kävijöinä on myös lapsia.</p>
<p><b>Virheilmoitukset:</b> tallennamme vain viestin, kunnan ja mahdollisen lähdelinkin. Emme tallenna nimeä, sähköpostia emmekä IP-osoitetta. Ilmoitukset poistetaan 24 kuukauden kuluttua.</p>
<p><b>Kalenteritilaus (.ics)</b> on tavallinen tiedosto, joka ei sisällä seurantaa.</p><p>Palvelua ylläpitää {OWNER}. Sivusto toimii Cloudflaren palvelimilla.</p></section>""", "/tietosuoja/"))

    for f in STATIC.iterdir():
        if f.suffix in (".svg", ".png", ".ico", ".js"):
            shutil.copy(f, out / f.name)
    shutil.copytree(STATIC / "fonts", out / "fonts")
    (out / "site.webmanifest").write_text(json.dumps({"name": "Koululomat", "short_name": "Koululomat", "lang": "fi",
        "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}],
        "theme_color": "#E8741E", "background_color": "#FFF6E5", "display": "browser", "start_url": "/"}, ensure_ascii=False))
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if PREVIEW else f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{today.isoformat()}</lastmod></url>" for u in urls) + "</urlset>\n")
    hdr = "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Permissions-Policy: interest-cohort=()\n"
    if PREVIEW:
        hdr += "  X-Robots-Tag: noindex, nofollow\n"
    hdr += "/fi/*/lomat.ics\n  Content-Type: text/calendar; charset=utf-8\n/sv/*/lov.ics\n  Content-Type: text/calendar; charset=utf-8\n/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n"
    (out / "_headers").write_text(hdr)
    (out / "404.html").write_text(page("Sivua ei löytynyt | Koululomat", "Sivua ei löytynyt.",
                                       f"<h1>Hups, tätä sivua ei löytynyt</h1>{datalist}<section class=\"box\"><p>Kirjoita kuntasi nimi ylähakuun tai palaa <a href=\"/\">etusivulle</a>.</p></section>", "/404"))
    print(f"{len(urls)} sivua, {len(data)} kuntaa -> {out}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
