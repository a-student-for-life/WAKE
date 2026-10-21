import csv,re,collections,sys
r=list(csv.DictReader(open(sys.argv[1],encoding='utf-8',errors='replace')))
yrs=collections.Counter(x['open_date'][:4] for x in r)
print({y:yrs[y] for y in sorted(yrs) if y>='2012'})
tags=collections.Counter(t.strip() for x in r for t in x['tags'].split(',') if t.strip())
print(tags.most_common(30))
print(collections.Counter(x['threat'] for x in r).most_common())
