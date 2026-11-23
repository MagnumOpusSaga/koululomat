import json,sys
from collections import Counter
def ev(sample, outdir, label):
    S=json.load(open(sample)); tot_pop=sum(m['pop'] for m in S)
    res={}
    for y in ('2026-2027','2027-2028'):
        found=[];days_ok=[];conf=Counter()
        for m in S:
            try: r=json.load(open(f"{outdir}/{m['id']}.json"))
            except: r={'years':{}}
            v=r['years'].get(y)
            comp = bool(v) and all(k in v['fields'] for k in ('start','syys','joulu','talvi','end'))
            conf[v['confidence'] if v and comp else 'ei löytynyt']+=1
            if comp: found.append(m); 
            if comp and v['checks']['days_ok']: days_ok.append(m)
        res[y]=dict(kunnat=f"{len(found)}/{len(S)} ({len(found)/len(S):.0%})",
                    vaesto=f"{sum(m['pop'] for m in found)/tot_pop:.1%}",
                    laskenta_ok=f"{len(days_ok)}/{len(found)}",
                    luottamus=dict(conf))
    print(label, json.dumps(res,ensure_ascii=False,indent=1))
ev('pilot_fi.json','out','PILOTTI (säännöt viritetty näillä)')
ev('holdout_fi.json','out_hold','KONTROLLI (ei viritystä)')
