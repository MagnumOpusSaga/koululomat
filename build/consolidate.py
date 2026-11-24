"""Yhdistää moottorin tulokset (out*/<kunta>.json) sivuston dataksi data/fi.json.

Puuttuvat kunnat/lukuvuodet saavat ARVION (maakunnan yleisin varmistettu arvo), selvästi merkittynä.
Arviota ei koskaan esitetä varmana.

Käyttö: python3 build/consolidate.py out out_hold ... > data/fi.json
"""
import re
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOFT = re.compile(r"^(loppu ei pe/la|alku viikolla (30|35))$")  # vain yksittäinen lievä poikkeama
YEARS = ("2026-2027", "2027-2028")
FIELDS = ("start", "syys", "joulu", "talvi", "end")


def main(dirs):
    muns = json.loads((ROOT / "fi_municipalities.json").read_text())
    res = {}
    for d in dirs:
        for p in Path(d).glob("*.json"):
            r = json.loads(p.read_text())
            res[r["municipality"]] = r
    now = datetime.now(timezone.utc).date().isoformat()
    out = []
    review = []
    for m in muns:
        r = res.get(m["id"])
        rec = {"id": m["id"], "name": m["fi"], "name_sv": m.get("sv"), "region": m["region"],
               "pop": m["pop"], "home": (r or {}).get("home"), "years": {}}
        for y in YEARS:
            v = ((r or {}).get("years") or {}).get(y)
            if v and v["checks"].get("plausibility"):
                issues = v["checks"]["plausibility"]
                review.append({"id": m["id"], "name": m["fi"], "year": y, "issues": issues, "source": v.get("primary")})
                if len(issues) == 1 and SOFT.match(issues[0]):
                    # lievä poikkeama (esim. päättyy torstaina): näytetään, mutta enintään "yksi lähde"
                    if v["confidence"] == "varmistettu":
                        v = dict(v, confidence="yksi_lähde")
                else:
                    v = None  # selvä järkevyyspoikkeama: ei näytetä luettuna, vaan arviona kunnes tarkistettu
            if v and v["confidence"] == "varmistettu" and any(str(x.get("quote", "")).startswith("[vaihdettu]") for x in v["fields"].values() if isinstance(x, dict)):
                v = dict(v, confidence="yksi_lähde")  # syys/talvi vaihdettu ruudukon palstoista -> ei koskaan varmistettu
            if v and all(f in v["fields"] for f in ("syys", "joulu", "talvi")):
                f = v["fields"]
                rec["years"][y] = {
                    "status": v["status"], "confidence": v["confidence"],
                    "days_calc": v["checks"]["calc_days"], "days_expected": v["checks"]["expected_days"],
                    "source": v["primary"], "updated": now,
                    "fields": {k: {"start": f[k]["start"], "end": f[k]["end"], "quote": f[k].get("quote", "")[:160],
                                   "sources": f[k].get("sources", [])} for k in FIELDS if k in f},
                }
        out.append(rec)
    # arviot: maakunnan yleisin arvo varmistetuista
    for y in YEARS:
        by_region = {}
        for rec in out:
            v = rec["years"].get(y)
            if v and v["confidence"] in ("varmistettu", "yksi_lähde"):
                for k, x in v["fields"].items():
                    by_region.setdefault((rec["region"], k), Counter())[(x["start"], x["end"])] += 1
        for rec in out:
            if y in rec["years"]:
                continue
            est = {}
            for k in FIELDS:
                c = by_region.get((rec["region"], k))
                if c:
                    (a, b), n = c.most_common(1)[0]
                    est[k] = {"start": a, "end": b, "quote": "", "sources": [], "basis": f"{n} kuntaa maakunnassa"}
            if est:
                rec["years"][y] = {"status": "arvio", "confidence": "arvio", "source": None,
                                   "updated": now, "fields": est}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "review_queue.json").write_text(json.dumps(review, ensure_ascii=False, indent=1))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main(sys.argv[1:] or [str(ROOT / "out")])
