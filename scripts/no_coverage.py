import json,re,sys,unicodedata
idx=json.load(open('data_no_index.json'))
kom=[x for x in json.load(open('no_kommuner.json'))['codes'] if x['level']=='1' and not x['code'].endswith('99')]
def norm(s): return unicodedata.normalize('NFC',s).lower().strip()
names={}
for k in kom:
    for n in re.split(r'\s+-\s+',k['name']):
        names.setdefault(norm(n),set()).add(k['code'])
# ambiguous names (e.g., Herøy, Våler) need fylke; map code->fylke by prefix
fylke_by_prefix={'03':'oslo','11':'rogaland','15':'møre og romsdal','18':'nordland','31':'østfold','32':'akershus','33':'buskerud','34':'innlandet','39':'vestfold','40':'telemark','42':'agder','46':'vestland','50':'trøndelag','55':'troms','56':'finnmark'}
cov={}  # code -> {year: [dokid]}
unmatched=[]
for r in idx:
    at=r['applies_to'] or ''
    parts=[p.strip() for p in at.split(',')]
    nm=norm(re.sub(r'\s+(kommune|herad|suohkan|gielda|kommune - .*)$','',parts[0],flags=re.I))
    fy=norm(parts[1]) if len(parts)>1 else ''
    codes=names.get(nm,set())
    if len(codes)>1: codes={c for c in codes if fylke_by_prefix.get(c[:2],'') in fy} or codes
    if not codes: unmatched.append(at); continue
    yrs=set(r['years_title'])|set(r['years_body'])
    for c in codes:
        for y in yrs: cov.setdefault(c,{}).setdefault(y,[]).append(r['dokid'])
for y in ['2025-2026','2026-2027','2027-2028','2028-2029']:
    n=sum(1 for c in cov if y in cov[c]); print(y, n, f"{n/len(kom):.0%}")
print('any', len(cov)); print('unmatched', len(unmatched), sorted(set(unmatched))[:15])
json.dump(cov,open('no_coverage.json','w'),ensure_ascii=False,indent=0)
