"""Koululomat: julkaisun jälkeinen simulaatio (savutesti).

Ajetaan GitHub Actionsissa jokaisen julkaisun jälkeen (.github/workflows/smoke.yml) ja käsin:
    python tests/smoke.py https://koululomat.fi [--axe node_modules/axe-core/axe.min.js]

Tarkistaa: kaikki sivukartan sivut ja sisäiset linkit, otsikot, canonical ja hreflang, vaakavieritys 360 px leveydellä,
JavaScript-virheet, käyttäjäpolut (haku ja kirjoitusvirheet, välilehdet, vertailu, ruotsi, ilmoituslomake siepattuna),
laskuri tulevina päivinä (aikahyppy), saavutettavuus (axe) ja lomadatan järkevyys. Virhe -> exit 1.
Ei lähetä mitään palvelimelle (ilmoituslomake siepataan selaimessa).
"""
import asyncio
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "https://koululomat.fi").rstrip("/")
AXE = sys.argv[sys.argv.index("--axe") + 1] if "--axe" in sys.argv else None
QUICK = "--quick" in sys.argv  # vain otos sivuista (paikallinen kokeilu)
FAIL, WARN, OK = [], [], []


def fail(area, msg):
    FAIL.append((area, msg)); print("  ✗", area, msg, flush=True)


def warn(area, msg):
    WARN.append((area, msg)); print("  !", area, msg, flush=True)


def ok(area, msg):
    OK.append((area, msg)); print("  ✓", area, msg, flush=True)


# ---------------------------------------------------------------- 1. indeksointi
async def crawl():
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, headers={"user-agent": "koululomat-smoke"}) as c:
        sm = (await c.get(BASE + "/sitemap.xml")).text
        urls = [u.replace("https://koululomat.fi", "") for u in re.findall(r"<loc>([^<]+)", sm)]
        sem = asyncio.Semaphore(12)

        async def get(u):
            async with sem:
                for i in range(3):
                    try:
                        r = await c.get(BASE + u)
                        return u, r.status_code, r.text
                    except httpx.HTTPError:
                        await asyncio.sleep(2)
                return u, 0, ""
        pages = {u: (s, t) for u, s, t in await asyncio.gather(*[get(u) for u in urls])}
        links = defaultdict(set)
        for u, (s, t) in pages.items():
            for a in re.findall(r'(?:href|src)="([^"#]+)', t):
                if a.startswith("http") and not a.startswith("https://koululomat.fi"):
                    continue
                links[urlparse(urljoin(BASE + u, a.replace("https://koululomat.fi", BASE))).path].add(u)
        extra = await asyncio.gather(*[get(p) for p in links if p not in pages])
    return urls, pages, links, {u: s for u, s, _ in extra}


def check_pages(urls, pages, links, extra):
    area = "sivut"
    bad = {u: s for u, (s, _) in pages.items() if s != 200}
    fail(area, f"{len(bad)} sivukartan sivua ei vastaa 200: {list(bad.items())[:5]}") if bad else ok(area, f"{len(urls)} sivua vastaa 200")
    broken = {p: s for p, s in extra.items() if s >= 400 or s == 0}
    if broken:
        fail(area, f"{len(broken)} rikkinäistä sisäistä linkkiä: " + "; ".join(f"{p} ({s}) ← {sorted(links[p])[0]}" for p, s in list(broken.items())[:5]))
    else:
        ok(area, f"{len(links)} sisäistä linkkiä toimii")
    titles, alts, issues = defaultdict(list), {}, defaultdict(list)
    for u, (s, t) in pages.items():
        m = re.search(r"<title>(.*?)</title>", t)
        title = unescape(m.group(1)) if m else ""
        titles[title].append(u)
        if not title or len(title) > 65:
            issues["otsikko puuttuu tai > 65 merkkiä"].append(u)
        can = re.search(r'rel="canonical" href="([^"]+)"', t)
        if not can or not can.group(1).endswith(u):
            issues["canonical"].append(u)
        if t.count("<h1") != 1:
            issues["h1-otsikoita ≠ 1"].append(u)
        if "noindex" in t:
            issues["noindex julkisella sivulla"].append(u)
        lang = (re.search(r'<html lang="(\w+)"', t) or [None, ""])[1]
        if u.startswith("/sv/") != (lang == "sv"):
            issues["väärä lang-attribuutti"].append(u)
        al = dict(re.findall(r'hreflang="([a-z]+)" href="https://koululomat\.fi([^"]+)"', t))
        if al:
            alts[u] = al
    for u, al in alts.items():
        for lg, p in al.items():
            if p not in pages:
                issues["hreflang-kohde puuttuu"].append(f"{u}→{p}")
            elif u not in alts.get(p, {}).values():
                issues["hreflang ei ole molempiin suuntiin"].append(f"{u}→{p}")
    dup = {k: v for k, v in titles.items() if len(v) > 1}
    if dup:
        issues["sama otsikko usealla sivulla"] += [f"{k[:40]}: {v[:2]}" for k, v in list(dup.items())[:3]]
    for k, v in issues.items():
        fail("SEO", f"{k}: {len(v)} kpl, esim. {v[:3]}")
    if not issues:
        ok("SEO", f"otsikot, canonical, h1, lang ja hreflang ({len(alts)} sivua) kunnossa")


# ---------------------------------------------------------------- 2. data
def check_data():
    area = "data"
    L = httpx.get(BASE + "/lomat.json", timeout=30).json()
    D = lambda s: dt.date.fromisoformat(s)
    probs = []
    for slug, r in L.items():
        for var, ys in (("fi", r["y"]), ("sv", r.get("sv") or {})):
            for y, e in ys.items():
                y0 = int(y[:4])
                for k, lo, hi in (("syys", 3, 9), ("talvi", 3, 9), ("joulu", 5, 21)):
                    if k in e:
                        n = (D(e[k][1]) - D(e[k][0])).days + 1
                        if not lo <= n <= hi:
                            probs.append(f"{slug} {var} {y} {k} kestää {n} pv")
                if "syys" in e and not 39 <= D(e["syys"][0]).isocalendar()[1] <= 44:
                    probs.append(f"{slug} {var} {y} syysloma vk {D(e['syys'][0]).isocalendar()[1]}")
                if "talvi" in e and not 7 <= D(e["talvi"][0]).isocalendar()[1] <= 11:
                    probs.append(f"{slug} {var} {y} talviloma vk {D(e['talvi'][0]).isocalendar()[1]}")
                if "joulu" in e and not dt.date(y0, 12, 17) <= D(e["joulu"][0]) <= dt.date(y0, 12, 28):
                    probs.append(f"{slug} {var} {y} joululoma alkaa {e['joulu'][0]}")
                if "kesa" in e and not dt.date(y0 + 1, 5, 25) <= D(e["kesa"]) <= dt.date(y0 + 1, 6, 12):
                    probs.append(f"{slug} {var} {y} koulu loppuu {e['kesa']}")
                seq = [D(e[k][0]) for k in ("syys", "joulu", "talvi") if k in e] + ([D(e["kesa"])] if "kesa" in e else [])
                if seq != sorted(seq):
                    probs.append(f"{slug} {var} {y} lomat väärässä järjestyksessä")
    fail(area, f"{len(probs)} epäjärkevää lomaa: {probs[:6]}") if probs else ok(area, f"{len(L)} kunnan lomat järkeviä (fi + sv)")
    c = sum(1 for r in L.values() if (r["y"].get("2026-2027") or {}).get("c") not in (None, "arvio"))
    (ok if c >= 260 else fail)(area, f"kunnan oma lähde 2026–27: {c}/{len(L)} kuntaa")


# ---------------------------------------------------------------- 3. selain
def browser_checks(urls):
    with sync_playwright() as p:
        # 3a. vaakavieritys + JS-virheet kaikilla sivuilla (pienin yleinen puhelin 360 px)
        br = p.chromium.launch()
        pg = br.new_page(viewport={"width": 360, "height": 800})
        errs = defaultdict(list)
        cur = {"u": ""}
        pg.on("pageerror", lambda e: errs[cur["u"]].append(str(e)[:120]))
        overflow = []
        sample = urls if not QUICK else urls[::25]
        for u in sample:
            cur["u"] = u
            try:
                pg.goto(BASE + u, wait_until="load", timeout=30000)
            except Exception as e:  # noqa: BLE001
                fail("selain", f"{u} ei latautunut: {str(e)[:80]}")
                continue
            if pg.evaluate("document.documentElement.scrollWidth > innerWidth + 1"):
                el = pg.evaluate("""(()=>{const e=[...document.querySelectorAll('body *')].find(e=>e.getBoundingClientRect().right>innerWidth+1&&!e.closest('[style*="overflow-x"]'));return e?e.tagName+' '+(e.textContent||'').slice(0,40):''})()""")
                overflow.append(f"{u} ({el})")
        fail("mobiili", f"vaakavieritys 360 px: {len(overflow)} sivua, esim. {overflow[:4]}") if overflow else ok("mobiili", f"{len(sample)} sivua mahtuu 360 px näytölle")
        fail("JS", f"JavaScript-virheitä {len(errs)} sivulla: {dict(list(errs.items())[:3])}") if errs else ok("JS", "ei JavaScript-virheitä")
        br.close()

        # 3b. käyttäjäpolut iPhonella (Safari/WebKit) ja Androidilla (Chrome)
        for engine, dev in ((p.webkit, p.devices["iPhone 13"]), (p.chromium, p.devices["Pixel 7"])):
            who = "iPhone" if engine.name == "webkit" else "Android"
            br = engine.launch()
            pg = br.new_context(**dev, locale="fi-FI").new_page()
            for q, want in [("ylojarvi", "/fi/ylojarvi/"), ("Helsnki", "/fi/helsinki/"), ("jyvaskyla", "/fi/jyvaskyla/"), ("ii", "/fi/ii/"),
                            ("mariehamn", "/fi/maarianhamina-mariehamn/"), ("tavastkyro", "/fi/hameenkyro/")]:
                pg.goto(BASE + "/"); pg.fill("#q2", q); pg.wait_for_timeout(400); pg.press("#q2", "Enter"); pg.wait_for_timeout(800)
                got = pg.url.replace(BASE, "")
                if got != want:
                    fail(who, f"haku '{q}' -> {got} (odotettu {want})")
            pg.goto(BASE + "/fi/ylojarvi/")
            cd = pg.locator(".hero").inner_text()
            if not re.search(r"\d+\s*\n?\s*yö|nyt!", cd):
                fail(who, f"kuntasivun laskuri outo: {cd[:60]!r}")
            pg.click("#t-lukio")
            if not (pg.locator("#p-lukio").is_visible() and not pg.locator("#p-perus").is_visible()):
                fail(who, "välilehdet eivät vaihdu")
            pg.goto(BASE + "/vertaa/"); pg.fill("#qa", "ylöjär"); pg.wait_for_timeout(400); pg.press("#qa", "Enter")
            pg.fill("#qb", "oulu"); pg.wait_for_timeout(400); pg.press("#qb", "Enter"); pg.wait_for_timeout(800)
            if "Syysloma" not in pg.locator("#cmp").inner_text():
                fail(who, "vertailu ei näytä tulosta")
            pg.goto(BASE + "/sv/"); pg.fill("#q2", "vanda"); pg.wait_for_timeout(400); pg.press("#q2", "Enter"); pg.wait_for_timeout(800)
            if not pg.url.endswith("/sv/vanda/"):
                fail(who, f"ruotsinkielinen haku 'vanda' -> {pg.url}")
            pg.goto(BASE + "/fi/ylojarvi/")
            sent = []
            pg.route("**/api/report", lambda rt: (sent.append(rt.request.post_data or ""), rt.fulfill(status=200, body="ok", content_type="text/html")))
            pg.click("details summary"); pg.fill("textarea", "testi"); pg.click("details button[type=submit]"); pg.wait_for_timeout(800)
            if not sent or "back=%2Ffi%2Fylojarvi%2F" not in sent[0]:
                fail(who, f"ilmoituslomake ei lähde oikein: {sent[:1]}")
            r = pg.goto(BASE + "/fi/eiolemassa-xyz/")
            if r.status != 404:
                fail(who, f"puuttuva sivu palauttaa {r.status}, ei 404")
            if not any(a == who for a, _ in FAIL):
                ok(who, "haku (myös kirjoitusvirheet), laskuri, välilehdet, vertailu, ruotsi, lomake, 404")
            br.close()

        # 3c. aikahyppy: laskuri ja kortit oikein tulevina päivinä ilman uutta rakennusta
        br = p.chromium.launch()
        L = httpx.get(BASE + "/lomat.json", timeout=30).json()
        probs = []
        for slug in ("ylojarvi", "helsinki", "oulu", "rovaniemi"):
            y = (L.get(slug) or {}).get("y", {}).get("2026-2027") or {}
            if "joulu" not in y:
                continue
            a, b = dt.date.fromisoformat(y["joulu"][0]), dt.date.fromisoformat(y["joulu"][1])
            for day, expect in ((a - dt.timedelta(1), "1 yö"), (a, "nyt"), (a + dt.timedelta(3), "nyt"), (b + dt.timedelta(1), "lomaan")):
                ctx = br.new_context(viewport={"width": 390, "height": 844})
                pg = ctx.new_page()
                pg.clock.set_fixed_time(dt.datetime.combine(day, dt.time(9)))
                pg.goto(f"{BASE}/fi/{slug}/"); pg.wait_for_timeout(300)
                hero = " ".join(pg.locator(".hero").inner_text().split())
                good = {"1 yö": "Joululomaan on 1 yö" in hero, "nyt": "Joululoma on nyt" in hero,
                        "lomaan": "Joululoma" not in hero and ("lomaan on" in hero or "on nyt" in hero)}[expect]
                if not good:
                    probs.append(f"{slug} {day}: {hero[:50]!r}")
                ctx.close()
        fail("aikahyppy", f"laskuri väärin tulevina päivinä: {probs[:4]}") if probs else ok("aikahyppy", "laskuri oikein ennen joululomaa, sen aikana ja jälkeen")
        br.close()

        # 3d. saavutettavuus
        if AXE:
            axe = open(AXE).read()
            br = p.chromium.launch()
            pg = br.new_page(viewport={"width": 390, "height": 844})
            agg = defaultdict(list)
            for u in ["/", "/fi/ylojarvi/", "/fi/hiihtoloma-2027/", "/fi/joululoma/", "/artikkelit/hiihtoloma-2027/",
                      "/artikkelit/koulu-loppuu-ennen-joulua-2026/", "/vertaa/?a=ylojarvi&b=oulu", "/haku/", "/sv/", "/sv/vanda/",
                      "/sv/sportlov-2027/", "/sv/artiklar/jullov-2026/"]:
                pg.goto(BASE + u); pg.wait_for_timeout(300); pg.add_script_tag(content=axe)
                for v in pg.evaluate("axe.run(document,{runOnly:['wcag2a','wcag2aa','best-practice']}).then(r=>r.violations.map(v=>[v.id,v.impact,v.nodes[0].target.join(' ')]))"):
                    agg[(v[0], v[1])].append(f"{u} {v[2]}")
            serious = {k: v for k, v in agg.items() if k[1] in ("serious", "critical")}
            for (rule, imp), v in serious.items():
                fail("saavutettavuus", f"{rule} ({imp}): {v[:3]}")
            for (rule, imp), v in agg.items():
                if (rule, imp) not in serious:
                    warn("saavutettavuus", f"{rule} ({imp}): {v[:2]}")
            if not agg:
                ok("saavutettavuus", "axe: ei rikkeitä (WCAG 2 A/AA + hyvät käytännöt)")
            br.close()


def main():
    print(f"== Koululomat-savutesti {BASE}")
    urls, pages, links, extra = asyncio.run(crawl())
    check_pages(urls, pages, links, extra)
    check_data()
    browser_checks(urls)
    lines = [f"## Koululomat – julkaisun tarkistus {'❌' if FAIL else '✅'}", "",
             f"{len(OK)} ok · {len(WARN)} huomautusta · {len(FAIL)} virhettä", ""]
    lines += [f"- ❌ **{a}**: {m}" for a, m in FAIL] + [f"- ⚠️ {a}: {m}" for a, m in WARN] + [f"- ✅ {a}: {m}" for a, m in OK]
    summary = "\n".join(lines)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(summary + "\n")
    with open("smoke_report.md", "w") as f:
        f.write(summary + "\n")
    print("\n" + summary)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
