"""Samankaltaisuusauditointi (spämmisuoja, claude/kirjasto/10-spamsuoja.md, sääntö 4).

Saman sivutyypin sivujen näkyvä teksti ilman ylä- ja alatunnistetta, 5 sanan jaksot (shingle):
- samankaltaisuus = parittainen Jaccard (raja: keskiarvo ≤ 0,30)
- oma teksti = osuus jaksoista, joita ei ole millään muulla otoksen sivulla (raja: jokaisella ≥ 40 %)
Vain indeksoitavat sivut (sivukartassa). Käyttö: python tests/quality.py <sivuston kansio> [otos=10]
"""
import itertools
import random
import re
import sys
from html import unescape
from pathlib import Path


def text(html):
    html = re.sub(r"(?s)<(script|style|header|footer|noscript)\b.*?</\1>", " ", html)
    html = re.sub(r"(?s)<details>.*?</details>", " ", html)  # ilmoituslomake (sama kaikilla, ei sisältöä)
    t = unescape(re.sub(r"<[^>]+>", " ", html))
    return re.findall(r"[\wåäöÅÄÖ–.:%-]+", t.lower())


def shingles(words, n=5):
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def audit(site, ptype_rx, k=10, seed=2026):
    site = Path(site)
    urls = re.findall(r"<loc>https://koululomat\.fi([^<]+)</loc>", (site / "sitemap.xml").read_text())
    cand = [u for u in urls if re.fullmatch(ptype_rx, u)]
    random.Random(seed).shuffle(cand)
    sample = cand[:k]
    S = {u: shingles(text((site / u.strip("/") / "index.html").read_text())) for u in sample}
    if len(S) < 2:
        return None
    jac = [len(S[a] & S[b]) / max(1, len(S[a] | S[b])) for a, b in itertools.combinations(S, 2)]
    own = {u: len(s - set().union(*(S[v] for v in S if v != u))) / max(1, len(s)) for u, s in S.items()}
    words = sum(len(s) for s in S.values()) / len(S)
    return {"tyyppi": ptype_rx, "sivuja": len(cand), "otos": len(S), "jaksoja_ka": round(words),
            "jaccard_ka": round(sum(jac) / len(jac), 2), "jaccard_max": round(max(jac), 2),
            "oma_ka": round(sum(own.values()) / len(own), 2), "oma_min": round(min(own.values()), 2),
            "heikoin": min(own, key=own.get)}


TYPES = {"fi-kunta": r"/fi/(?!syysloma/|joululoma/|kesaloma/|hiihtoloma-2027/)[^/]+/",
         "sv-kunta": r"/sv/(?!hostlov/|jullov/|sommarlov/|sportlov-2027/)[^/]+/",
         "lomasivut": r"/fi/(syysloma|joululoma|kesaloma|hiihtoloma-2027)/"}

if __name__ == "__main__":
    site = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    bad = False
    for name, rx in TYPES.items():
        r = audit(site, rx, k)
        if not r:
            continue
        flag = "OK" if r["jaccard_ka"] <= 0.30 and r["oma_min"] >= 0.40 else "YLI RAJAN"
        bad |= flag != "OK"
        print(f"{name:10} {r['sivuja']:4} sivua, otos {r['otos']}: samankaltaisuus ka {r['jaccard_ka']} / max {r['jaccard_max']}, "
              f"omaa tekstiä ka {int(r['oma_ka'] * 100)} % / min {int(r['oma_min'] * 100)} % ({r['heikoin']})  {flag}")
    sys.exit(1 if bad else 0)
