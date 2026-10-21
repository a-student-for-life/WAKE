import csv,re,collections,sys
r=list(csv.DictReader(open(sys.argv[1],encoding='utf-8',errors='replace')))
pref=re.compile(r"\b(M/V|F/V|T/V|M/T|S/V|P/V|R/V|OSV|Tug|Tugboat|Towboat|M/Y|Barge|Fishing Vessel|Tank Vessel|Tank Barge|Cargo Vessel|Container Ship|Vessel)\s+[\"'“]?([A-Z][A-Za-z0-9\-\.' ]{2,30})",re.I)
def hits(x):
    s=x['name']+' . '+x['description'][:1500]
    return pref.findall(s)
out=collections.Counter(); outT=collections.Counter()
for x in r:
    y=x['open_date'][:4]
    h=hits(x)
    if h:
        out[y]+=1
        if 'Pipeline' not in x['tags'] and 'Hurricane' not in x['tags']: outT[y]+=1
for y in sorted(out):
    if y>='2015': print(y,out[y],outT[y])
print('2018-24',sum(out[str(y)] for y in range(2018,2025)),sum(outT[str(y)] for y in range(2018,2025)))
print('2015-17',sum(out[str(y)] for y in range(2015,2018)),'2025',out['2025'],'2026',out['2026'])
