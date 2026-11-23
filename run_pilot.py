import json,sys,time
from multiprocessing import Pool
from engine.pipeline import process
from engine.checks import ChangeMonitor
pilot=json.load(open('pilot_fi.json'))
def one(m):
    t=time.time()
    from engine.checks import ALAND
    try: r=process(m, country='ax' if m['id'] in ALAND else 'fi')
    except Exception as e: r={'municipality':m['id'],'name':m['fi'],'error':repr(e),'years':{}}
    r['secs']=round(time.time()-t); json.dump(r,open(f"out/{m['id']}.json",'w'),ensure_ascii=False,indent=1)
    return m['fi'], r['secs']
if __name__=='__main__':
    ids=sys.argv[1:]
    todo=[m for m in pilot if not ids or m['id'] in ids]
    with Pool(8) as p:
        for name,secs in p.imap_unordered(one,todo): print(name,secs,flush=True)
