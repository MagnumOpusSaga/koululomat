"""Staattinen sivusto: data/fi.json -> site/ (Cloudflare Pages).

Ei seurantaa, ei evästeitä, ei ulkoisia skriptejä tai fontteja. PREVIEW=1 (oletus) -> noindex + robots Disallow.
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
BASE = os.environ.get("SITE_URL", "https://koululomat.pages.dev")
OWNER = "BR Entertainment (Y-tunnus 3183394-5)"
WD = ["ma", "ti", "ke", "to", "pe", "la", "su"]
LABEL = {"start": "Koulu alkaa", "syys": "Syysloma", "joulu": "Joululoma", "talvi": "Talviloma (hiihtoloma)", "end": "Koulu päättyy"}
CONF = {"varmistettu": ("Varmistettu", "ok", "Kaksi lähdettä samaa mieltä tai kunnan virallinen lähde + koulupäivien laskenta täsmää."),
        "yksi_lähde": ("Yksi lähde", "one", "Kunnan oma lähde, mutta toista vahvistusta ei vielä ole."),
        "ehdotus": ("Ehdotus", "prop", "Päätösehdotus – ei vielä lopullinen."),
        "arvio": ("Arvio", "est", "Kunnan päätöstä ei löytynyt. Arvio maakunnan muiden kuntien perusteella – tarkista koulusta.")}


def slug(s):
    s = unicodedata.normalize("NFKD", s.lower().replace("ä", "a").replace("ö", "o").replace("å", "a"))
    return re.sub(r"[^a-z0-9]+", "-", "".join(c for c in s if not unicodedata.combining(c))).strip("-")


def d(s):
    return date.fromisoformat(s)


def fmt(a, b=None):
    a = d(a)
    if not b or b == a.isoformat():
        return f"{WD[a.weekday()]} {a.day}.{a.month}.{a.year}"
    b = d(b)
    if a.year == b.year:
        return f"{WD[a.weekday()]} {a.day}.{a.month}.–{WD[b.weekday()]} {b.day}.{b.month}.{b.year}"
    return f"{WD[a.weekday()]} {a.day}.{a.month}.{a.year}–{WD[b.weekday()]} {b.day}.{b.month}.{b.year}"


def week(s):
    return d(s).isocalendar()[1]


CSS = """*{box-sizing:border-box}body{margin:0;font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1b1f24;background:#fbfaf7}
a{color:#0b5cad}header,main,footer{max-width:860px;margin:0 auto;padding:0 18px}header{padding-top:18px}
.brand{font-weight:800;font-size:20px;text-decoration:none;color:#1b1f24}.brand span{color:#d2691e}
.pv{background:#fff3c4;border-bottom:1px solid #e8d27a;padding:8px 18px;font-size:14px;text-align:center}
h1{font-size:30px;line-height:1.2;margin:18px 0 6px}h2{font-size:21px;margin:28px 0 10px}.lead{color:#4a525c;margin:0 0 14px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e3e0d8;border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #eeebe4;vertical-align:top}th{font-size:13px;color:#5b636d;font-weight:600;background:#f6f4ef}
.b{display:inline-block;font-size:12px;font-weight:700;padding:2px 8px;border-radius:99px;white-space:nowrap}
.ok{background:#dff3e4;color:#17602e}.one{background:#e6eefb;color:#1d4f91}.prop{background:#fff0d6;color:#8a5300}.est{background:#fde2e1;color:#9b1c1c}
.src{font-size:13px;color:#5b636d}.cd{background:#fff;border:1px solid #e3e0d8;border-radius:12px;padding:14px 16px;margin:14px 0;font-size:18px}
.cd b{font-size:26px;color:#d2691e}.grid{columns:3 200px;column-gap:20px;padding:0;list-style:none}.grid li{break-inside:avoid;padding:2px 0}
input[type=search]{width:100%;padding:12px 14px;font-size:17px;border:1px solid #cfcac0;border-radius:10px;margin:6px 0 14px}
.btn{display:inline-block;background:#1b1f24;color:#fff;padding:9px 14px;border-radius:9px;text-decoration:none;font-weight:600;font-size:15px;margin:4px 8px 4px 0}
.btn.alt{background:#fff;color:#1b1f24;border:1px solid #cfcac0}footer{margin-top:40px;padding:22px 18px 40px;font-size:13px;color:#5b636d;border-top:1px solid #e3e0d8}
details{background:#fff;border:1px solid #e3e0d8;border-radius:10px;padding:10px 14px;margin:14px 0}summary{cursor:pointer;font-weight:600}
form label{display:block;font-size:14px;margin:8px 0 4px}form input,form textarea{width:100%;padding:8px;border:1px solid #cfcac0;border-radius:8px;font:inherit}
.hp{position:absolute;left:-5000px}.wk{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.wk div{background:#fff;border:1px solid #e3e0d8;border-radius:10px;padding:12px}.wk h3{margin:0 0 6px;font-size:16px}
@media(max-width:560px){h1{font-size:25px}th,td{padding:8px}}"""


def page(title, desc, body, path, schema=None):
    robots = '<meta name="robots" content="noindex,nofollow">' if PREVIEW else ""
    pv = '<div class="pv">Esikatselu – tietoja tarkistetaan vielä. Sivu ei näy hakukoneissa.</div>' if PREVIEW else ""
    sd = f'<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>' if schema else ""
    return f"""<!doctype html><html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">{robots}
<link rel="canonical" href="{BASE}{path}"><style>{CSS}</style>{sd}</head><body>{pv}
<header><a class="brand" href="/">Koulu<span>lomat</span></a></header><main>{body}</main>
<footer>Tiedot haetaan aina kunnan omasta lähteestä (päätös, kunnan sivu tai liite). Jokaisella päivällä on lähde, tila ja päivityspäivä.
Arviot on merkitty erikseen – tarkista oman koulusi päivät koululta.<br>Ei evästeitä, ei seurantaa. <a href="/tietoa/">Tietoa palvelusta</a> · <a href="/tietosuoja/">Tietosuoja</a><br>© {date.today().year} {OWNER}</footer></body></html>"""


def badge(conf):
    t, c, tip = CONF[conf]
    return f'<span class="b {c}" title="{html.escape(tip)}">{t}</span>'


def year_table(y, v):
    rows = []
    for k in ("start", "syys", "joulu", "talvi", "end"):
        x = v["fields"].get(k)
        if not x:
            rows.append(f"<tr><th>{LABEL[k]}</th><td>–</td><td></td></tr>")
            continue
        when = fmt(x["start"], x["end"] if k not in ("start", "end") else None)
        wk = f' <span class="src">(vk {week(x["start"])})</span>' if k in ("syys", "talvi") else ""
        rows.append(f"<tr><th>{LABEL[k]}</th><td>{when}{wk}</td><td>{badge(v['confidence'])}</td></tr>")
    src = ""
    if v.get("source"):
        src = f'<p class="src">Lähde: <a href="{html.escape(v["source"])}" rel="nofollow">{html.escape(re.sub(r"^https?://", "", v["source"])[:90])}</a> · päivitetty {d(v["updated"]).strftime("%-d.%-m.%Y")}'
        if v.get("days_calc"):
            src += f' · koulupäiviä laskettu {v["days_calc"]}' + (f' (laki {v["days_expected"]})' if v.get("days_expected") else "")
        src += "</p>"
    else:
        src = f'<p class="src">Arvio – kunnan päätöstä ei löytynyt. Päivitetty {d(v["updated"]).strftime("%-d.%-m.%Y")}.</p>'
    note = " <small>(loma-ajat arkipäivinä; viikonloput lisäksi)</small>"
    return f"<h2>Lukuvuosi {y.replace('-', '–')}{note}</h2><table><tr><th>Mikä</th><th>Milloin</th><th>Tila</th></tr>{''.join(rows)}</table>{src}"


def next_holiday(rec, today):
    best = None
    for y, v in rec["years"].items():
        for k in ("syys", "joulu", "talvi", "end"):
            x = v["fields"].get(k)
            if x:
                s = d(x["start"]) if k != "end" else d(x["start"]) + timedelta(1)
                if s >= today and (best is None or s < best[0]):
                    best = (s, "Kesäloma" if k == "end" else LABEL[k].split(" (")[0], v["confidence"])
    return best


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
            while b.weekday() < 6 and (b + timedelta(1)).weekday() >= 5:
                b += timedelta(1)  # loma päättyy sunnuntaihin kalenterissa
            tag = "" if v["confidence"] in ("varmistettu", "yksi_lähde") else f" ({CONF[v['confidence']][0].lower()})"
            lines += ["BEGIN:VEVENT", f"UID:{rec['id']}-{y}-{k}@koululomat", f"DTSTAMP:{stamp}",
                      f"DTSTART;VALUE=DATE:{a.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(b + timedelta(1)).strftime('%Y%m%d')}",
                      f"SUMMARY:{LABEL[k].split(' (')[0]} – {rec['name']}{tag}", f"URL:{BASE}/fi/{slug(rec['name'])}/", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


REPORT_FORM = """<details><summary>Ilmoita oikea päivä tai virhe</summary>
<form method="post" action="/api/report"><input type="hidden" name="municipality" value="{id}">
<label>Mikä on väärin tai puuttuu?</label><textarea name="message" rows="3" maxlength="600" required></textarea>
<label>Linkki kunnan tai koulun lähteeseen (jos on)</label><input name="source_url" type="url" maxlength="300">
<input class="hp" name="website" tabindex="-1" autocomplete="off"><p><button class="btn" type="submit">Lähetä</button></p>
<p class="src">Emme tallenna nimeä, sähköpostia emmekä IP-osoitetta. Linkki luetaan automaattisesti ja tarkistetaan.</p></form></details>"""

COUNTDOWN_JS = """<script>(function(){var e=document.getElementById('cd');if(!e)return;var t=new Date(e.dataset.d+'T00:00:00'),n=new Date();n.setHours(0,0,0,0);
var x=Math.round((t-n)/864e5);if(x>=0)e.querySelector('b').textContent=x;})();</script>"""


def build(data_path, out_dir):
    data = json.loads(Path(data_path).read_text())
    out = Path(out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    today = date.today()
    urls = ["/"]

    def write(path, content):
        p = out / path.lstrip("/")
        if path.endswith("/"):
            p = p / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # kuntasivut
    for rec in data:
        s = slug(rec["name"])
        nh = next_holiday(rec, today)
        cd = ""
        if nh:
            cd = (f'<div class="cd" id="cd" data-d="{nh[0].isoformat()}">{nh[1]} alkaa {fmt(nh[0].isoformat())} – '
                  f'<b>{(nh[0] - today).days}</b> päivää {badge(nh[2])}</div>')
        tables = "".join(year_table(y, v) for y, v in sorted(rec["years"].items()))
        if not tables:
            tables = "<p>Tietoja ei vielä ole. Ilmoita lähde alla, niin luemme sen.</p>"
        sv = f" ({rec['name_sv']})" if rec.get("name_sv") and rec["name_sv"] != rec["name"] else ""
        body = (f"<h1>Koulujen lomat {rec['name']}{sv} 2026–2027 ja 2027–2028</h1>"
                f"<p class=\"lead\">Syysloma, joululoma, talviloma (hiihtoloma) sekä koulun alku ja loppu – {rec['region']}.</p>{cd}"
                f'<p><a class="btn" href="/fi/{s}/lomat.ics">Lisää lomat kalenteriin</a>'
                f'<a class="btn alt" href="/fi/hiihtoloma-2027/{s}/">Hiihtoloma 2027</a></p>{tables}'
                f"<p class=\"src\">Perusopetus. Esiopetuksen, lukion ja yksittäisten koulujen päivät voivat poiketa (esim. lauantaikoulupäivä).</p>"
                f"{REPORT_FORM.format(id=rec['id'])}{COUNTDOWN_JS}")
        y1 = rec["years"].get("2026-2027")
        tal = y1["fields"].get("talvi") if y1 else None
        desc = f"{rec['name']}: koulujen syysloma, joululoma ja talviloma" + (f" (hiihtoloma vk {week(tal['start'])})" if tal else "") + " lähteineen."
        schema = {"@context": "https://schema.org", "@type": "WebPage", "name": f"Koulujen lomat {rec['name']}",
                  "about": {"@type": "City", "name": rec["name"]}}
        write(f"/fi/{s}/", page(f"Koulujen lomat {rec['name']} 2026–2027 | Koululomat", desc, body, f"/fi/{s}/", schema))
        (out / "fi" / s / "lomat.ics").write_text(ics(rec), encoding="utf-8")
        urls.append(f"/fi/{s}/")

        # hiihtoloma 2027 -kuntasivu
        if tal:
            yv = rec["years"]["2026-2027"]
            body = (f"<h1>Hiihtoloma 2027 {rec['name']}</h1><p class=\"lead\">Koulujen talviloma lukuvuonna 2026–2027.</p>"
                    f'<div class="cd" id="cd" data-d="{tal["start"]}">Talviloma {fmt(tal["start"], tal["end"])} (vk {week(tal["start"])}) – '
                    f'<b>{max((d(tal["start"]) - today).days, 0)}</b> päivää {badge(yv["confidence"])}</div>'
                    f'<p><a class="btn" href="/fi/{s}/lomat.ics">Lisää kalenteriin</a><a class="btn alt" href="/fi/{s}/">Kaikki lomat</a>'
                    f'<a class="btn alt" href="/fi/hiihtoloma-2027/">Hiihtolomat koko Suomessa</a></p>'
                    + (f'<p class="src">Lähde: <a href="{html.escape(yv["source"])}" rel="nofollow">{html.escape(re.sub(r"^https?://", "", yv["source"])[:90])}</a></p>' if yv.get("source") else
                       '<p class="src">Arvio – kunnan päätöstä ei löytynyt.</p>')
                    + COUNTDOWN_JS)
            write(f"/fi/hiihtoloma-2027/{s}/", page(f"Hiihtoloma 2027 {rec['name']} – viikko {week(tal['start'])} | Koululomat",
                                                     f"{rec['name']}: hiihtoloma 2027 on {fmt(tal['start'], tal['end'])} (viikko {week(tal['start'])}).",
                                                     body, f"/fi/hiihtoloma-2027/{s}/"))
            urls.append(f"/fi/hiihtoloma-2027/{s}/")

    # hiihtoloma 2027 -koonti viikoittain
    weeks = defaultdict(list)
    for rec in data:
        v = rec["years"].get("2026-2027")
        if v and v["fields"].get("talvi"):
            weeks[week(v["fields"]["talvi"]["start"])].append(rec)
    cols = "".join(
        f"<div><h3>Viikko {w} <small>({fmt(min(r['years']['2026-2027']['fields']['talvi']['start'] for r in rs))[3:]}…)</small></h3>"
        f"<p class=\"src\">{len(rs)} kuntaa</p><ul class=\"grid\" style=\"columns:1\">"
        + "".join(f'<li><a href="/fi/hiihtoloma-2027/{slug(r["name"])}/">{r["name"]}</a>'
                  + ("" if r["years"]["2026-2027"]["confidence"] != "arvio" else ' <span class="b est">arvio</span>') + "</li>"
                  for r in sorted(rs, key=lambda r: r["name"])) + "</ul></div>"
        for w, rs in sorted(weeks.items()))
    write("/fi/hiihtoloma-2027/", page("Hiihtoloma 2027 – kaikki kunnat viikoittain | Koululomat",
                                         "Koulujen hiihtolomat 2027 kunnittain: viikot 8, 9 ja 10. Lähteet kuntien omista päätöksistä.",
                                         f"<h1>Hiihtoloma 2027 kunnittain</h1><p class=\"lead\">Talvilomat porrastetaan viikoille. "
                                         f"Valitse kunta nähdäksesi tarkat päivät ja lähteen.</p><div class=\"wk\">{cols}</div>",
                                         "/fi/hiihtoloma-2027/"))
    urls.append("/fi/hiihtoloma-2027/")

    # etusivu
    by_region = defaultdict(list)
    for rec in data:
        by_region[rec["region"]].append(rec)
    n_ok = sum(1 for r in data if (r["years"].get("2026-2027") or {}).get("confidence") in ("varmistettu", "yksi_lähde"))
    lists = "".join(f"<h2>{reg}</h2><ul class=\"grid\">" + "".join(
        f'<li data-n="{html.escape(r["name"].lower())} {html.escape((r.get("name_sv") or "").lower())}"><a href="/fi/{slug(r["name"])}/">{r["name"]}</a></li>'
        for r in sorted(rs, key=lambda r: r["name"])) + "</ul>" for reg, rs in sorted(by_region.items()))
    search_js = """<script>document.getElementById('q').addEventListener('input',function(){var q=this.value.toLowerCase().trim();
document.querySelectorAll('li[data-n]').forEach(function(li){li.style.display=!q||li.dataset.n.indexOf(q)>=0?'':'none'});});</script>"""
    body = (f"<h1>Koulujen lomat kunnittain</h1><p class=\"lead\">Syys-, joulu- ja talvilomat sekä koulun alku ja loppu jokaisessa Suomen kunnassa "
            f"lukuvuosina 2026–2027 ja 2027–2028. Tiedot kuntien omista lähteistä – {n_ok}/{len(data)} kunnalla kunnan oma lähde.</p>"
            f'<input id="q" type="search" placeholder="Hae kuntaa, esim. Tampere" aria-label="Hae kuntaa">'
            f'<p><a class="btn" href="/fi/hiihtoloma-2027/">Hiihtoloma 2027 viikoittain</a></p>{lists}{search_js}')
    write("/", page("Koulujen lomat kunnittain 2026–2027 – syysloma, joululoma, hiihtoloma | Koululomat",
                    "Koulujen loma-ajat jokaisessa Suomen kunnassa: syysloma, joululoma, talviloma ja hiihtoloma 2027. Lähteet kuntien päätöksistä.",
                    body, "/"))

    # tietoa ja tietosuoja
    write("/tietoa/", page("Tietoa palvelusta | Koululomat", "Miten koulujen lomatiedot kerätään ja tarkistetaan.",
                           f"""<h1>Tietoa palvelusta</h1><p>Koululomat kokoaa koulujen työ- ja loma-ajat jokaisen kunnan omasta lähteestä:
lautakunnan päätöksestä, kunnan verkkosivulta tai sen liitteestä. Muiden koostesivujen tietoja ei kopioida.</p>
<h2>Miten tiedot tarkistetaan</h2><ul><li>Koulupäivät lasketaan luetuista päivistä ja verrataan lakiin (190 päivää, joista vähennetään arkipäiville osuvat itsenäisyyspäivä, loppiainen ja vappu).</li>
<li>Järkevyyssäännöt: esim. syysloma viikoilla 41–44 ja talviloma viikoilla 7–11. Poikkeamat tarkistetaan käsin.</li>
<li>Kaksi riippumatonta lähdettä samaa mieltä → <span class="b ok">Varmistettu</span>. Päätösehdotukset merkitään <span class="b prop">Ehdotus</span>.</li>
<li>Lähteet haetaan uudelleen kuukausittain, ja muuttunut sisältö luetaan uudelleen.</li>
<li>Jos kunnan päätöstä ei löydy, sivulla näkyy <span class="b est">Arvio</span> – sitä ei koskaan esitetä varmana.</li></ul>
<h2>Oikeudet</h2><p>Viranomaisen päätöksiin ei ole tekijänoikeutta (tekijänoikeuslaki 9 §). Päivämäärät ovat faktoja.</p>
<h2>Ylläpitäjä</h2><p>{OWNER}</p>""", "/tietoa/"))
    write("/tietosuoja/", page("Tietosuoja | Koululomat", "Koululomat ei käytä evästeitä eikä seurantaa.",
                               f"""<h1>Tietosuoja</h1><p>Palvelu ei käytä evästeitä, analytiikkaa, seurantaa eikä kohdennettua mainontaa.
Sivuilla ei ladata ulkopuolisia skriptejä tai fontteja. Kävijöinä on myös lapsia.</p>
<p><b>Virheilmoitukset:</b> tallennamme vain viestin, kunnan ja mahdollisen lähdelinkin. Emme tallenna nimeä, sähköpostia emmekä IP-osoitetta.
Ilmoitukset poistetaan 24 kuukauden kuluttua.</p><p><b>Kalenteritilaus (.ics)</b> on tavallinen tiedosto, joka ei sisällä seurantaa.</p>
<p>Palvelua ylläpitää {OWNER}. Sivusto toimii Cloudflaren palvelimilla.</p>""", "/tietosuoja/"))

    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n" if PREVIEW else f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{today.isoformat()}</lastmod></url>" for u in urls) + "</urlset>\n")
    hdr = "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Permissions-Policy: interest-cohort=()\n"
    if PREVIEW:
        hdr += "  X-Robots-Tag: noindex, nofollow\n"
    hdr += "/fi/*/lomat.ics\n  Content-Type: text/calendar; charset=utf-8\n"
    (out / "_headers").write_text(hdr)
    print(f"{len(urls)} sivua, {len(data)} kuntaa -> {out}")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
