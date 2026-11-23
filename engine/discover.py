"""Löytäminen: kunnan sivusto -> ehdokasdokumentit (sivut, päätökset, liitteet).

1. Kotisivu (arvaus + varmistus)  2. sitemap.xml  3. rajattu ryömintä opetuksen sivuille
4. hakurajapinta (Brave Search API, jos BRAVE_API_KEY)  5. liitteiden ja Dynasty-sisarten seuraaminen
"""
import os
import re
import unicodedata
from collections import deque
from urllib.parse import urlparse

from . import fetch
from .adapters import read, same_site

URL_HIT = re.compile(r"lukukaudet|lukukausi-?ja|loma-?aj|tyo-?ja-?vapaa|työ-?ja-?vapaa|tyopaivat|työpäivät|lukuvuositiedote|tyo-?ja-?loma|työ-?ja-?loma|lukuvuo\w*-?(tyo|työ|aj|lom)|koulujen-?loma|"
                     r"lukuvuosi|lukuvuoden|tyoajat|loma-ajat|arbets-?och-?(lov|ledighet)|lasarstider|läsårstider|"
                     r"lasarets|skollov|lov-?och|lasar-?\d|lukuvuosi-?\d", re.I)
NAV_HIT = re.compile(r"kasvatus|opetus|koulu|perusopetus|oppilaitokset|lukuvuo|loma|utbildning|skol|"
                     r"bildning|sivistys|lapset|perheet|education|school", re.I)
SKIP = re.compile(r"\.(jpg|jpeg|png|gif|svg|css|js|zip|mp4|mp3|ics|xml)(\?|$)|/(en|ru|uk|ar|so)/|"
                  r"tapahtum|readspeaker|uutiset/\d{4}/0|kirjasto|liikunta|rekry|tyopaikat|mailto:", re.I)
CONTENT_KW = re.compile(r"syysloma|joululoma|talviloma|hiihtoloma|höstlov|jullov|sportlov|"
                        r"syyslukukau|kevätlukukau|hösttermin|vårtermin", re.I)

DOMAIN_OVERRIDES = {"091": "https://www.hel.fi/fi", "092": "https://www.vantaa.fi/fi",
                    "049": "https://www.espoo.fi/fi", "853": "https://www.turku.fi",
                    "598": "https://www.pietarsaari.fi", "564": "https://www.ouka.fi", "536": "https://www.nokiankaupunki.fi"}


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.lower().replace("ä", "a").replace("ö", "o").replace("å", "a"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def homepage(mun: dict) -> str | None:
    if mun["id"] in DOMAIN_OVERRIDES:
        return DOMAIN_OVERRIDES[mun["id"]]
    if mun.get("website"):  # virallinen verkkosivu (Wikidata P856, kuntanumero P1203)
        m = fetch.get(mun["website"])
        if m.get("status") == 200:
            return m["final_url"]
    s = slug(mun["fi"])
    tlds = [".fi", ".ax"]
    cands = []
    for name in dict.fromkeys([s, slug(mun.get("sv") or s)]):
        for tld in tlds:
            cands += [f"https://www.{name}{tld}", f"https://{name}{tld}"]
    for c in cands:
        m = fetch.get(c)
        if m.get("status") == 200:
            head = open(m["path"], "rb").read(60000).decode("utf8", "ignore")
            title = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
            if title and re.search(r"yliopisto|university|korkeakoulu|\boy\b|\boyj\b", title.group(1), re.I):
                continue  # esim. oulu.fi = Oulun yliopisto, nokia.fi = yhtiö
            return m["final_url"]
    return None


def _sitemap_urls(home: str, limit_maps=40) -> list:
    p = urlparse(home)
    base = f"{p.scheme}://{p.netloc}"
    maps = []
    r = fetch.get(base + "/robots.txt")
    if r.get("path") and r.get("status") == 200:
        maps += re.findall(r"(?im)^sitemap:\s*(\S+)", open(r["path"], errors="ignore").read())
    maps += [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/wp-sitemap.xml"]
    seen, urls = set(), []
    q = deque(dict.fromkeys(maps))
    while q and len(seen) < limit_maps:
        sm = q.popleft()
        if sm in seen:
            continue
        seen.add(sm)
        m = fetch.get(sm)
        if m.get("status") != 200 or not m.get("path"):
            continue
        xml = open(m["path"], "rb").read()
        if xml[:2] == b"\x1f\x8b":
            import gzip
            xml = gzip.decompress(xml)
        locs = re.findall(rb"<loc>\s*([^<\s]+)\s*</loc>", xml)
        for loc in locs:
            u = loc.decode("utf8", "ignore").replace("&amp;", "&")
            if re.search(r"sitemap[^/]*\.xml", u, re.I) and u not in seen:
                q.append(u)
            else:
                urls.append(u)
    return urls


def search_api(query: str, n=10) -> list:
    """Brave Search API (ilmainen taso). Avain ympäristömuuttujasta, ei koskaan koodiin."""
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        return []
    import requests
    r = requests.get("https://api.search.brave.com/res/v1/web/search",
                     params={"q": query, "count": n, "country": "FI", "search_lang": "fi"},
                     headers={"X-Subscription-Token": key, "Accept": "application/json"}, timeout=20)
    if r.status_code != 200:
        return []
    return [x["url"] for x in r.json().get("web", {}).get("results", [])]


def queries_fi(mun: dict, years=("2026-2027", "2027-2028")) -> list:
    n = mun["fi"]
    qs = [f"työ- ja loma-ajat {y} {n}" for y in years] + [f"{n} lukuvuoden työajat koulujen loma-ajat"]
    if mun.get("sv") and mun["sv"] != n:
        qs.append(f"läsårstider {years[0]} {mun['sv']}")
    return qs


def discover(mun: dict, max_pages=45, log=None) -> dict:
    log = log if log is not None else []
    home = homepage(mun)
    res = {"home": home, "candidates": [], "pages_crawled": 0, "sitemap_hits": 0}
    if not home:
        log.append("kotisivua ei löytynyt")
        return res
    scored = {}

    def add(u, score, why):
        if SKIP.search(u):
            return
        if u not in scored or scored[u][0] < score:
            scored[u] = (score, why)

    # 1. sitemap
    for u in _sitemap_urls(home):
        if URL_HIT.search(u):
            add(u, 5, "sitemap")
            res["sitemap_hits"] += 1
    # 3. ryömintä
    q = deque([(home, 0)])
    seen = set()
    while q and len(seen) < max_pages:
        u, depth = q.popleft()
        if u in seen:
            continue
        seen.add(u)
        m = fetch.get(u)
        doc = read(m)
        if doc.get("format") != "html":
            continue
        hits = len(CONTENT_KW.findall(doc["text"]))
        if hits >= 2:
            add(u, 3 + min(hits, 6), "ryömintä")
        for href, txt in doc["links"]:
            if SKIP.search(href):
                continue
            onsite = same_site(href, home)
            school_channel = re.search(r"peda\.net/" + re.escape(slug(mun["fi"])) + r"|" + re.escape(slug(mun["fi"])) + r"\.inschool\.fi", href, re.I)
            if school_channel and depth < 2:
                q.append((href, depth + 1))  # koulun omat kanavat (Peda.net, Wilman julkiset tiedotteet)
            if URL_HIT.search(href) or re.search(r"loma-?aj|työ- ja loma|työ- ja vapaa|lukukaudet ja lomat|lukuvuo|läsårstid|arbets- och lov|arbetstider|skollov|lov och|lovdagar", txt, re.I):
                add(href, 7, "linkki:" + txt[:40])
                if onsite:
                    q.appendleft((href, depth + 1))
            elif (onsite or school_channel) and depth < 3 and NAV_HIT.search(href + " " + txt):
                q.append((href, depth + 1))
    # 4. hakurajapinta vain, jos ryömintä ei löytänyt vahvaa ehdokasta (Brave: ~5 $/1000 hakua, 5 $ kuukausikrediitti)
    if not any(sc >= 7 for sc, _ in scored.values()):
        for q in queries_fi(mun)[:2]:
            for u in search_api(q):
                add(u, 6, "haku")
        res["searched"] = bool(os.environ.get("BRAVE_API_KEY"))
    res["pages_crawled"] = len(seen)
    res["candidates"] = sorted(([u, s, w] for u, (s, w) in scored.items()), key=lambda x: -x[1])
    return res
