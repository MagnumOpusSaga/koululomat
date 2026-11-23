import json,glob
pilot=json.load(open('holdout_fi.json'))
for m in pilot:
    try: r=json.load(open(f"out_hold/{m['id']}.json"))
    except FileNotFoundError: print(m['fi'],'-- kesken'); continue
    line=[m['size'][:5],m['fi'][:11].ljust(11),(r.get('home') or 'EI KOTISIVUA')[:30].ljust(30),str(r.get('pages_crawled')).rjust(3)]
    for y in ('2026-2027','2027-2028'):
        v=r['years'].get(y)
        if not v: line.append(f"{y[:4]}: --"); continue
        f=v['fields']; c=v['checks']
        line.append(f"{y[:4]}: {v['confidence'][:5]} miss={','.join(v['missing']) or '-'} d={c['calc_days']}/{c['expected_days']} pl={len(c['plausibility'])}")
    print(' | '.join(line))
