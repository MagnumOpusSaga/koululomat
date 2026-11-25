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


def _extra(f):
    """Lisätiedot artikkeleille ja kuntasivulle: lukukausien rajat, lauantaikoulupäivät, vapaapäivät, pääsiäinen."""
    def d(x, k):
        return x.get(k) if isinstance(x, dict) else None
    e = {"term1_end": d(f.get("term1"), "end") or d(f.get("term1_end"), "start"),
         "term2_start": d(f.get("term2"), "start") or d(f.get("term2_start"), "start"),
         "saturdays": sorted({x["start"] for x in (f.get("saturday") or []) if isinstance(x, dict) and x.get("start")}),
         "free": sorted({x["start"] for x in (f.get("free") or []) if isinstance(x, dict) and x.get("start")}),
         "paasiainen": [d(f.get("paasiainen"), "start"), d(f.get("paasiainen"), "end")] if f.get("paasiainen") else None}
    return {k: v for k, v in e.items() if v}


def _sane(f):
    """Kieliversiolle tiukempi: lomat vähintään 3 (syys/talvi) tai 5 (joulu) päivää, muuten luettu väärin (Turku sv)."""
    from datetime import date as _d
    ln = lambda k: (_d.fromisoformat(f[k]["end"]) - _d.fromisoformat(f[k]["start"])).days + 1
    return ln("syys") >= 3 and ln("talvi") >= 3 and ln("joulu") >= 5


def _accept(v, m, y, review, now, strict=False):
    if v and v["checks"].get("plausibility"):
        issues = v["checks"]["plausibility"]
        if review is not None:
            review.append({"id": m["id"], "name": m["fi"], "year": y, "issues": issues, "source": v.get("primary")})
        if len(issues) == 1 and SOFT.match(issues[0]):
            # lievä poikkeama (esim. päättyy torstaina): näytetään, mutta enintään "yksi lähde"
            if v["confidence"] == "varmistettu":
                v = dict(v, confidence="yksi_lähde")
        else:
            return None  # selvä järkevyyspoikkeama: ei näytetä luettuna, vaan arviona kunnes tarkistettu
    if v and v["confidence"] == "varmistettu" and any(str(x.get("quote", "")).startswith("[vaihdettu]") for x in v["fields"].values() if isinstance(x, dict)):
        v = dict(v, confidence="yksi_lähde")  # syys/talvi vaihdettu ruudukon palstoista -> ei koskaan varmistettu
    if not (v and all(f in v["fields"] for f in ("syys", "joulu", "talvi"))):
        return None
    f = v["fields"]
    if strict and not _sane(f):
        return None
    return {"status": v["status"], "confidence": v["confidence"],
            "days_calc": v["checks"]["calc_days"], "days_expected": v["checks"]["expected_days"],
            "source": v["primary"], "updated": now,
            "fields": {k: {"start": f[k]["start"], "end": f[k]["end"], "quote": f[k].get("quote", "")[:160],
                           "sources": f[k].get("sources", [])} for k in FIELDS if k in f},
            "extra": _extra(f)}


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
            yr = _accept(((r or {}).get("years") or {}).get(y), m, y, review, now)
            if yr:
                rec["years"][y] = yr
        # kaksikieliset: toisen kieliversion päivät (esim. Vantaan ruotsinkieliset koulut: höstlov 14.–16.10.)
        rec["variant"] = (r or {}).get("variant") or "fi"
        for lg, ys in ((r or {}).get("variants") or {}).items():
            alt = {y: a for y in YEARS if (a := _accept((ys or {}).get(y), m, y, None, now, strict=True))}
            if alt:
                rec.setdefault("alt", {})[lg] = alt
        forms = (r or {}).get("forms") or {}
        if forms:
            rec["forms"] = {F: {y: {k: {kk: x[kk] for kk in ("start", "end", "quote", "sources", "conflict") if kk in x}
                                    for k, x in fy.items()} for y, fy in ys.items() if y in YEARS}
                            for F, ys in forms.items()}
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
