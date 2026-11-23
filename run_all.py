"""Koko maa: python3 run_all.py fi  -> out_all/<kunta>.json, muutosvalvonta state/monitor.json"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path
from engine.pipeline import process
from engine.checks import ALAND, ChangeMonitor
OUT = Path("out_all"); OUT.mkdir(exist_ok=True)
def one(m):
    t = time.time()
    try:
        r = process(m, country="ax" if m["id"] in ALAND else "fi")
    except Exception as e:  # noqa: BLE001
        r = {"municipality": m["id"], "name": m["fi"], "error": repr(e), "years": {}, "sources": []}
    r["secs"] = round(time.time() - t)
    (OUT / f"{m['id']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    return m["fi"], r["secs"], [s for s in r.get("sources", []) if s.get("hash")]
if __name__ == "__main__":
    muns = json.load(open("fi_municipalities.json"))
    only = set(sys.argv[2:])
    todo = [m for m in muns if not only or m["id"] in only]
    Path("state").mkdir(exist_ok=True)
    mon = ChangeMonitor("state/monitor.json")
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    changed = []
    with Pool(8) as p:
        for name, secs, srcs in p.imap_unordered(one, todo):
            for s in srcs:
                st = mon.check(s["url"], s["hash"], now)
                if st == "muuttunut":
                    changed.append((name, s["url"]))
            print(name, secs, flush=True)
    mon.save()
    Path("state/changed.json").write_text(json.dumps(changed, ensure_ascii=False, indent=0))
    print("muuttuneita lähteitä:", len(changed))
