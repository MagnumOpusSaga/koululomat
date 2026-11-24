"""Vianetsintä: miten kuntien kotisivut vastaavat botille. Käyttö: python3 scripts/diag_home.py 545 893 ..."""
import json, re, sys
sys.path.insert(0, ".")
from engine import fetch
from engine.discover import URL_HIT, homepage
muns = {m["id"]: m for m in json.load(open("fi_municipalities.json"))}
for i in sys.argv[1:]:
    m = muns[i]
    r = fetch.get(m.get("website") or "", max_age_h=0) if m.get("website") else {}
    hits = []
    if r.get("path") and r.get("status") == 200:
        html = open(r["path"], errors="ignore").read()
        hits = sorted(set(u for u in re.findall(r'href="([^"]+)"', html) if URL_HIT.search(u)))[:6]
    print(i, m["fi"], m.get("website"), "->", r.get("status"), r.get("final_url"), r.get("error"), "| homepage():", homepage(m), "| osumat:", hits, flush=True)
