import json,sys,re
from engine import fetch; from engine.adapters import read
for mid in sys.argv[1:]:
    r=json.load(open(f'out/{mid}.json'))
    prim={v['primary'] for v in r['years'].values() if v}
    for u in prim:
        t=read(fetch.get(u))['text']
        lines=[l.strip() for l in t.split('\n') if re.search(r'loma|lukukau|alka|päätty|lov|termin|lauantai|työpäiv|vapaa|lukuvuo',l,re.I) and re.search(r'\d',l) and len(l.strip())<160]
        print('#####',r['name'],u[8:90]); print('   '+'\n   '.join(lines[:24]))
