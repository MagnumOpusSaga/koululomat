import json,sys,time
from engine.pipeline import process
pilot={m['id']:m for m in json.load(open('pilot_fi.json'))}
for mid in sys.argv[1:]:
    t=time.time(); r=process(pilot[mid])
    print(r['name'], r['home'], 'crawled',r['pages_crawled'],'cands',r['n_candidates'], f"{time.time()-t:.0f}s")
    for s in r['sources'][:14]: print('  ', s.get('kind'), s.get('format'), s.get('years'), s['url'][:110], s.get('error') or s.get('skipped') or '')
    for y,v in r['years'].items():
        if not v: print(' ',y,'EI LÖYTYNYT'); continue
        f=v['fields']; print(' ',y,v['confidence'],v['status'],'puuttuu',v['missing'], {k:(f[k]['start'],f[k]['end']) for k in ('start','syys','joulu','talvi','end') if k in f}, 'päivät', v['checks']['calc_days'],'/',v['checks']['expected_days'], v['checks']['plausibility'])
    json.dump(r,open(f'out/{mid}.json','w'),ensure_ascii=False,indent=1)
