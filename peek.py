import json,sys,re
from engine import fetch; from engine.adapters import read
for mid in sys.argv[1:]:
    r=json.load(open(f'out/{mid}.json'))
    print('#####',r['name'])
    used=[s for s in r['sources'] if s.get('years')]
    for s in used[:3]:
        print(' SRC',s['kind'],s['format'],s['variant'],s['years'],s['url'][:120])
    if used:
        d=read(fetch.get(used[0]['url'])); t=d['text']
        lines=[l.strip() for l in t.split('\n') if re.search(r'loma|lukukau|alka|päätty|lov|termin|lauantai|työpäiv|vapaa',l,re.I) and re.search(r'\d',l)]
        print('   '+'\n   '.join(l[:150] for l in lines[:28]))
