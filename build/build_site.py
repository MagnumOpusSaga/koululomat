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


def slug(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ä", "a").replace("ö", "o").replace("å", "a"))
    return re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if not unicodedata.combining(c))).strip("-")


def d(s):
    return date.fromisoformat(s)


def fmt(a, b=None, year=True):
    a = d(a)
    if not b or b == a.isoformat():
        return f"{WD[a.weekday()]} {a.day}.{a.month}." + (f"{a.year}" if year else "")
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


CSS = """@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-wght-normal.woff2) format("woff2");font-weight:200 1000;font-display:swap;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215}
@font-face{font-family:Nunito;src:url(/fonts/nunito-latin-ext-wght-normal.woff2) format("woff2");font-weight:200 1000;font-display:swap;unicode-range:U+0100-02AF,U+1E00-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:17px/1.55 Nunito,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#2A1B0F;background:var(--tint,#FFF6E5);font-variant-numeric:tabular-nums}
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
.search.big{max-width:none;margin:0;flex:none;width:100%}.search.big input{height:60px;font-size:19px;padding:0 24px}
.hh{font-size:36px;line-height:1.1;margin:10px 0 4px}.sub{font-size:19px;font-weight:700;color:#5F4B3A;margin:0 0 16px}
.trust{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:14px;font-weight:800;color:#6B5847;margin:14px 0 28px}
.tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.tile{display:flex;flex-direction:column;gap:4px;min-height:132px;padding:16px;border-radius:26px;text-decoration:none;color:#2A1B0F;background:var(--bg);box-shadow:0 5px 0 var(--c)}
.tile:hover{color:#2A1B0F;transform:translateY(-2px)}.tile b{font-size:20px;font-weight:900;margin-top:6px}.tile span{font-size:15px;font-weight:900;color:var(--c)}
.tile .ic{background:#fff}.tile.past{opacity:.7}
.letters{display:flex;flex-wrap:wrap;gap:8px}.letters a{width:46px;height:46px;border-radius:14px;background:#fff;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:18px;text-decoration:none;color:#2A1B0F;box-shadow:0 3px 0 #F0D9B5}
.letters a:hover{background:var(--hero,#E8741E);color:var(--ht,#fff)}
a.card{text-decoration:none;color:#2A1B0F}a.card:hover{transform:translateY(-2px)}
.grp{display:flex;flex-direction:column;gap:14px}.gh{display:flex;align-items:center;gap:14px}
.wkb{width:62px;height:62px;border-radius:18px;background:var(--bg);color:var(--c);display:flex;flex-direction:column;align-items:center;justify-content:center;flex:none;line-height:1}
.wkb small{font-size:12px;font-weight:800}.wkb b{font-size:24px;font-weight:900}
.az{scroll-margin-top:16px}
.sr{position:absolute;left:-9999px}
h1{font-size:30px;line-height:1.15;font-weight:900;margin:8px 0 16px}
h2{font-size:22px;font-weight:900;margin:0 0 10px}
.hero{background:var(--hero,#E8741E);color:var(--ht,#fff);border-radius:36px;padding:28px 22px 24px;text-align:center;box-shadow:0 7px 0 var(--hs,#B4530F);display:flex;flex-direction:column;align-items:center;gap:2px;height:100%;justify-content:center}
.hero.est{background:#9B6B45;box-shadow:0 7px 0 #6E4A2F;color:#fff}
.hero .lead{font-size:20px;font-weight:800;margin:6px 0 0}
.hero .big{font-size:120px;line-height:.95;font-weight:900;letter-spacing:-.03em}
.hero .unit{font-size:30px;font-weight:900;margin:0}
.hero .when{font-size:19px;font-weight:800;margin:8px 0 0}
.bar{width:100%;max-width:420px;margin-top:14px}.bar>div{height:18px;border-radius:99px;background:var(--track,rgba(255,255,255,.3));overflow:hidden}
.bar i{display:block;height:100%;border-radius:99px;background:var(--bar,#FFE08A)}.bar p{margin:6px 0 0;font-size:19px;font-weight:800}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.card{background:#fff;border-radius:26px;padding:16px;box-shadow:0 4px 0 #F0D9B5;display:flex;flex-direction:column;gap:2px}
.card.now{outline:3px solid var(--c);box-shadow:0 4px 0 var(--c)}.card.past{opacity:.75}
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
@media(min-width:900px){.tiles{grid-template-columns:repeat(4,minmax(0,1fr))}.hh{font-size:48px}h1{font-size:40px}.hero .big{font-size:160px}.hero{padding:36px}}
@media(max-width:420px){.hero .big{font-size:104px}.card{padding:14px}}"""



def search_form(fid, placeholder="Mikä on sinun kuntasi?", big=False, prefix=None, main=False):
    pre = f' data-prefix="{prefix}"' if prefix else ""
    return (f'<form class="search{" big" if big else ""}" action="/haku/" role="search"{pre}{" data-main" if main else ""}>'
            f'<label class="sr" for="{fid}">Hae kuntaa</label><div class="ac"><input id="{fid}" name="q" type="search" placeholder="{placeholder}" '
            f'role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="{fid}-l" autocomplete="off" autocapitalize="words" spellcheck="false">'
            f'<div class="acl" id="{fid}-l" role="listbox" hidden></div></div></form>')


def theme_style(t):
    h, hs, ht, tint, bar, track = THEME[t]
    return f"--hero:{h};--hs:{hs};--ht:{ht};--tint:{tint};--bar:{bar};--track:{track}"


def page(title, desc, body, path, schema=None, theme="brand", top_search=True):
    robots = '<meta name="robots" content="noindex,nofollow">' if PREVIEW else ""
    pv = '<div class="pv">Esikatselu – tietoja tarkistetaan vielä. Sivu ei näy hakukoneissa.</div>' if PREVIEW else ""
    sd = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f"""<!doctype html><html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{robots}
<link rel="canonical" href="{BASE}{path}"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/logo.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/icon-180.png"><link rel="manifest" href="/site.webmanifest"><meta name="theme-color" content="{THEME[theme][0]}">
<link rel="preload" href="/fonts/nunito-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}</style>{sd}<script src="/ac.js" defer></script></head><body style="{theme_style(theme)}">{pv}
<div class="wrap"><header class="top"><a class="brand" href="/">{LOGO.format(s=40)}<b>Koulu<span>lomat</span></b></a>
{search_form("q") if top_search else ""}</header>
<main>{body}</main>
<footer class="bot">Tiedot kunnan omasta lähteestä · Ei evästeitä, ei seurantaa · <a href="/tietoa/">Tietoa</a> · <a href="/tietosuoja/">Tietosuoja</a><br>© {date.today().year} {OWNER}</footer></div>
</body></html>"""


def badge(conf):
    t, c, tip = CONF[conf]
    return f'<span class="b {c}" title="{html.escape(tip)}">{t}</span>'


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


def hero(rec, today):
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
            bar = f'<div class="bar"><div><i style="width:{pct}%"></i></div><p>Lomasta lomaan: matkaa takana {pct} %</p></div>'
    name = HOL[k]["name"]
    when = (f"alkaa {fmt(a.isoformat())}" if k == "kesa" else fmt(a.isoformat(), b.isoformat())) + \
           (f" · viikko {week(a.isoformat())}" if k in ("syys", "talvi") else "")
    if ongoing:
        body = f'<p class="lead">{name} on nyt!</p><div class="big" aria-hidden="true">🎉</div>'
    else:
        body = (f'<p class="lead">{name}an on</p><div class="big" id="cd" data-d="{a.isoformat()}">{n}</div>'
                f'<p class="unit">{yo(n)}!</p>')
    est = conf == "arvio"
    return (f'<section class="hero{" est" if est else ""}" aria-label="Lähtölaskuri">{icon(k, 64, "currentColor")}{body}'
            f'<p class="when">{when}{" (arvio)" if est else ""}</p><p style="margin:6px 0 0">{badge(conf)}</p>{bar}</section>')


def next_kind(rec, today):
    nx = [h for h in holidays_of(rec) if h[2] >= today]
    return (nx[0][0], nx[0][1]) if nx else (None, None)


def cards(rec, today, year):
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
            dt = f"alkaa {a.day}.{a.month}."
        else:
            if k not in f:
                continue
            a, b = d(f[k]["start"]), d(f[k]["end"])
            dt = fmt(f[k]["start"], f[k]["end"], year=False) + (f" · vk {week(f[k]['start'])}" if k in ("syys", "talvi") else "")
        past = b < today
        if past:
            n = "Ohi jo!"
        elif a <= today:
            n = "Nyt lomalla!"
        else:
            nn = nights(a, today)
            n = f"{nn} {yo(nn)}"
        now = bool(nxt and nxt[0] == k and nxt[3] == year)
        h = HOL[k]
        cls = " now" if now else (" past" if past else "")
        items.append(f'<a class="card{cls}" href="{HPAGE[k][0]}" style="--c:{h["c"]}"><div class="ic" style="background:{h["bg"]}">{icon(k, 26)}</div>'
                     f'<b>{h["name"]}</b><span class="dt">{dt}</span><span class="n" style="color:{"#6B5847" if past else h["c"]}">{n}</span></a>')
    return f'<div class="grid">{"".join(items)}</div>'


def adult_table(rec):
    years = sorted(rec["years"].items())
    if not years:
        return ""
    rows = [("Koulu alkaa", "start"), ("Syysloma", "syys"), ("Joululoma", "joulu"), ("Talviloma (hiihtoloma)", "talvi"), ("Koulu päättyy", "end")]
    head = "".join(f"<th>{y.replace('-', '–')}<br>{badge(v['confidence'])}</th>" for y, v in years)
    body = ""
    for label, k in rows:
        cells = ""
        for y, v in years:
            x = v["fields"].get(k)
            if not x:
                cells += "<td>–</td>"
            elif k in ("start", "end"):
                cells += f"<td>{fmt(x['start'])}</td>"
            else:
                cells += f"<td>{fmt(x['start'], x['end'])}" + (f" <small>(vk {week(x['start'])})</small>" if k in ("syys", "talvi") else "") + "</td>"
        body += f"<tr><th scope='row'>{label}</th>{cells}</tr>"
    srcs = []
    for y, v in years:
        yy = y.replace("-", "–")
        if v.get("source"):
            s = re.sub(r"^https?://(www\.)?", "", v["source"])[:70]
            extra = (f" · koulupäiviä laskettu {v['days_calc']}" + (f" (laki {v['days_expected']})" if v.get("days_expected") else "")) if v.get("days_calc") else ""
            srcs.append(f'{yy}: <a href="{html.escape(v["source"])}" rel="nofollow">{html.escape(s)}</a>{extra}')
        else:
            srcs.append(f"{yy}: arvio – kunnan päätöstä ei vielä löytynyt, tarkista koululta")
    upd = d(max(v["updated"] for _, v in years))
    return (f'<section class="box"><h2>Aikuisille: tarkat päivät</h2><div style="overflow-x:auto"><table><thead><tr><th>Perusopetus</th>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div><p class="src">Lomapäivät ovat arkipäiviä, viikonloput tulevat lisäksi. Esiopetuksen, lukion ja yksittäisten koulujen päivät voivat poiketa.<br>'
            f'Lähteet – {" · ".join(srcs)}. Päivitetty {upd.day}.{upd.month}.{upd.year}.</p></section>')


def ics(rec):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Koululomat//FI", "CALSCALE:GREGORIAN",
             f"X-WR-CALNAME:Koululomat – {rec['name']}", "X-PUBLISHED-TTL:P1W"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for y, v in rec["years"].items():
        for k in ("syys", "joulu", "talvi"):
            x = v["fields"].get(k)
            if not x:
                continue
            a, b = d(x["start"]), d(x["end"])
            while (b + timedelta(1)).weekday() >= 5:
                b += timedelta(1)
            tag = "" if v["confidence"] in ("varmistettu", "yksi_lähde") else f" ({CONF[v['confidence']][0].lower()})"
            lines += ["BEGIN:VEVENT", f"UID:{rec['id']}-{y}-{k}@koululomat.fi", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{a.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(b + timedelta(1)).strftime('%Y%m%d')}",
                      f"SUMMARY:{HOL[k]['name']} – {rec['name']}{tag}", f"URL:{BASE}/fi/{slug(rec['name'])}/", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


REPORT_FORM = """<details><summary>Ilmoita oikea päivä tai virhe</summary>
<form method="post" action="/api/report"><input type="hidden" name="municipality" value="{id}">
<label for="m{id}">Mikä on väärin tai puuttuu?</label><textarea id="m{id}" name="message" rows="3" maxlength="600" required></textarea>
<label for="s{id}">Linkki kunnan tai koulun lähteeseen (jos on)</label><input id="s{id}" name="source_url" type="url" maxlength="300">
<input class="hp" name="website" tabindex="-1" autocomplete="off" aria-hidden="true"><p><button class="btn" type="submit">Lähetä</button></p>
<p class="src">Emme tallenna nimeä, sähköpostia emmekä IP-osoitetta. Luemme linkin ja tarkistamme tiedon.</p></form></details>"""

# laskuri päivittyy selaimessa, vaikka sivu olisi rakennettu aiemmin
COUNTDOWN_JS = """<script>(function(){var e=document.getElementById('cd');if(!e)return;var t=new Date(e.dataset.d+'T00:00:00'),n=new Date();n.setHours(0,0,0,0);
var x=Math.round((t-n)/864e5);if(x>=0){e.textContent=x;var u=e.nextElementSibling;if(u)u.textContent=(x==1?'yö':'yötä')+'!';}})();</script>"""


def build(data_path, out_dir):
    data = json.loads(Path(data_path).read_text())
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
    for rec in data:
        s = slug(rec["name"])
        sv = f" ({rec['name_sv']})" if rec.get("name_sv") and rec["name_sv"] != rec["name"] else ""
        nk, nd = next_kind(rec, today) if rec["years"] else (None, None)
        if rec["years"]:
            top = f'<div class="layout"><div>{hero(rec, today)}</div><div>{cards(rec, today, y1)}</div></div>'
        else:
            top = '<section class="box"><p>Tämän kunnan lomia ei vielä löytynyt. Jos tiedät lähteen, ilmoita se alla – luemme sen.</p></section>'
        cmp_url = HPAGE[nk][0] if nk else "/fi/hiihtoloma-2027/"
        body = (f'<h1>{rec["name"]}{sv}: koulujen lomat</h1>{top}'
                f'<div class="btns"><a class="btn" href="/fi/{s}/lomat.ics">Lisää lomat kalenteriin</a>'
                f'<a class="btn alt" href="{cmp_url}">Vertaa muihin kuntiin</a></div>'
                f'{adult_table(rec)}{REPORT_FORM.format(id=rec["id"])}{COUNTDOWN_JS}')
        tal = (rec["years"].get(y1) or {}).get("fields", {}).get("talvi")
        desc = (f"{rec['name']}: syysloma, joululoma ja hiihtoloma" + (f" (vk {week(tal['start'])})" if tal else "")
                + " sekä koulun alku ja loppu. Lähtölaskuri ja lähteet.")
        schema = {"@context": "https://schema.org", "@type": "WebPage", "name": f"Koulujen lomat {rec['name']}",
                  "about": {"@type": "City", "name": rec["name"]}}
        th = "brand" if not nk or rec["years"].get(y1, {}).get("confidence") == "arvio" else nk
        write(f"/fi/{s}/", page(f"{rec['name']}: koulujen lomat 2026–2027 – syysloma, joululoma, hiihtoloma | Koululomat", desc, body, f"/fi/{s}/", schema, theme=th))
        (out / "fi" / s / "lomat.ics").write_text(ics(rec), encoding="utf-8")
        urls.append(f"/fi/{s}/")
        ac.append({"n": rec["name"], "sv": rec.get("name_sv") or "", "s": s, "r": rec["region"],
                   "h": HOL[nk]["name"].lower() if nk else "", "d": nd.isoformat() if nd else "", "t": bool(tal)})
        if tal:
            yv = rec["years"][y1]
            n = nights(d(tal["start"]), today)
            est = yv["confidence"] == "arvio"
            hb = (f'<h1>Hiihtoloma 2027 – {rec["name"]}</h1><section class="hero{" est" if est else ""}">{icon("talvi", 64, "currentColor")}'
                  f'<p class="lead">Hiihtolomaan on</p><div class="big" id="cd" data-d="{tal["start"]}">{n}</div><p class="unit">{yo(n)}!</p>'
                  f'<p class="when">{fmt(tal["start"], tal["end"])} · viikko {week(tal["start"])}{" (arvio)" if est else ""}</p>'
                  f'<p style="margin:6px 0 0">{badge(yv["confidence"])}</p></section>'
                  f'<div class="btns"><a class="btn" href="/fi/{s}/lomat.ics">Lisää kalenteriin</a><a class="btn alt" href="/fi/{s}/">Kaikki lomat: {rec["name"]}</a>'
                  f'<a class="btn alt" href="/fi/hiihtoloma-2027/">Muut kunnat</a></div>{adult_table(rec)}{COUNTDOWN_JS}')
            write(f"/fi/hiihtoloma-2027/{s}/", page(f"Hiihtoloma 2027 {rec['name']} – viikko {week(tal['start'])} | Koululomat",
                                                     f"{rec['name']}: hiihtoloma 2027 on {fmt(tal['start'], tal['end'])} (viikko {week(tal['start'])}). Lähtölaskuri ja lähde.",
                                                     hb, f"/fi/hiihtoloma-2027/{s}/", theme="talvi"))
            urls.append(f"/fi/hiihtoloma-2027/{s}/")
    (out / "kunnat.json").write_text(json.dumps(sorted(ac, key=lambda x: x["n"]), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

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
                badge_html = f'<div class="wkb" style="--bg:{h["bg"]};--c:{h["c"]}"><small>vk</small><b>{key}</b></div>'
                title = f"{mon.day}.{mon.month}.–{fri.day}.{fri.month}.{fri.year}"
            else:
                badge_html = f'<div class="wkb" style="--bg:{h["bg"]};--c:{h["c"]}"><small>{WD[key.weekday()]}</small><b>{key.day}.{key.month}.</b></div>'
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
        write(path, page(f"{label} kunnittain – kaikki Suomen kunnat | Koululomat",
                         f"{label}: koulujen loma-ajat kaikissa Suomen kunnissa. Tiedot kuntien omista lähteistä.", hb, path, theme=k, top_search=False))
        urls.append(path)

    # etusivu (E1: haku ensin + lomat värillisinä valintoina)
    n_ok = sum(1 for r in data if (r["years"].get(y1) or {}).get("confidence") in ("varmistettu", "yksi_lähde"))
    tiles = "".join(f'<a class="tile{" past" if summary[k][1] else ""}" href="{HPAGE[k][0]}" style="--bg:{HOL[k]["bg"]};--c:{HOL[k]["c"]}">'
                    f'<div class="ic">{icon(k, 26)}</div><b>{HOL[k]["name"]}</b><span>{summary[k][0]}</span></a>'
                    for k in ("syys", "joulu", "talvi", "kesa"))
    letters_set = sorted({r["name"][0].upper() for r in data}, key=lambda c: "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ".find(c))
    letters = "".join(f'<a href="/haku/#{c}">{c}</a>' for c in letters_set)
    body = (f'<h1 class="hh">Montako yötä lomaan?</h1><p class="sub">Kirjoita kuntasi.</p>'
            f'{search_form("q2", big=True)}'
            f'<p class="trust"><span class="b ok">✓ Kunnan oma lähde</span>{n_ok}/{len(data)} kuntaa</p>'
            f'<h2>Tai katso loma kerrallaan</h2><div class="tiles">{tiles}</div>'
            f'<h2 style="margin-top:30px">Kaikki kunnat</h2><div class="letters">{letters}</div>')
    write("/", page("Koulujen lomat kunnittain 2026–2027 – syysloma, joululoma, hiihtoloma | Koululomat",
                    "Montako yötä lomaan? Koulujen syys-, joulu- ja hiihtolomat jokaisessa Suomen kunnassa. Tiedot kuntien omista lähteistä.",
                    body, "/", {"@context": "https://schema.org", "@type": "WebSite", "name": "Koululomat", "url": BASE + "/",
                                "publisher": {"@type": "Organization", "name": "BR Entertainment", "logo": BASE + "/icon-512.png"}},
                    top_search=False))
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
    hdr += "/fi/*/lomat.ics\n  Content-Type: text/calendar; charset=utf-8\n/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n"
    (out / "_headers").write_text(hdr)
    (out / "404.html").write_text(page("Sivua ei löytynyt | Koululomat", "Sivua ei löytynyt.",
                                       f"<h1>Hups, tätä sivua ei löytynyt</h1>{datalist}<section class=\"box\"><p>Kirjoita kuntasi nimi ylähakuun tai palaa <a href=\"/\">etusivulle</a>.</p></section>", "/404"))
    print(f"{len(urls)} sivua, {len(data)} kuntaa -> {out}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
