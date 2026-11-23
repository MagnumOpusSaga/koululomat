"""Index Norwegian local school-calendar regulations (forskrift om skole- og feriedager)
from Lovdata public data (Norsk Lovtidend avd. II, NLOD 2.0).

Usage: python3 lovdata_index.py <extracted_dir> [<extracted_dir> ...] > index.json
"""
import json
import re
import sys
from pathlib import Path

TITLE_RE = re.compile(r"(skole|skule)[- ]?(og|og)?\s*feriedag|skolerute|skulerute|skoleruta|skuleruta", re.I)
YEAR_RE = re.compile(r"(20\d\d)\s*[–/-]\s*(20\d\d|\d\d)(?!\d)")


def field(html, cls):
    m = re.search(rf'<dd class="{cls}">(.*?)</dd>', html, re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()


def years_from(text):
    out = set()
    for a, b in YEAR_RE.findall(text or ""):
        a, b = int(a), int(b) if len(b) == 4 else 2000 + int(b)
        if b == a + 1:
            out.add(f"{a}-{b}")
        elif b > a + 1:  # range like 2026-2029 -> each school year
            for y in range(a, b):
                out.add(f"{y}-{y + 1}")
    return sorted(out)


def main():
    rows = []
    for d in sys.argv[1:]:
        for p in Path(d).rglob("*.xml"):
            html = p.read_text(encoding="utf-8", errors="replace")
            title = field(html, "title") or ""
            if not TITLE_RE.search(title):
                continue
            body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
            rows.append({
                "file": str(p),
                "dokid": field(html, "dokid"),
                "title": title,
                "applies_to": field(html, "appliesTo"),
                "in_force": field(html, "dateInForce"),
                "published": field(html, "dateOfPublication"),
                "basis": field(html, "basedOn"),
                "years_title": years_from(title),
                "years_body": years_from(body[:4000]),
                "has_table": "<table" in html,
                "repeal_or_change": bool(re.search(r"endring|oppheving|opphevelse", title, re.I)),
            })
    json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
