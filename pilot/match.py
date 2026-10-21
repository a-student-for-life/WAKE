import pandas as pd, re, os
def norm(s):
    s=str(s).upper()
    s=re.sub(r"^(M/V|MV|M/T|MT|F/V|FV|T/V|TV|TUG|OSV|S/V)\s+","",s)
    return re.sub(r"[^A-Z0-9]","",s)
p=pd.read_csv('nrc/pilot_loc.csv')
for _,r in p.iterrows():
    f=f"ais/{r.date}.csv"
    if not os.path.exists(f): print(r.VESSEL_NAME,r.date,'(not downloaded yet)'); continue
    a=pd.read_csv(f,header=None,names=['mmsi','name','type','len','lat','lon','n'],dtype={'name':str})
    a['k']=a.name.map(norm); k=norm(r.VESSEL_NAME)
    if k in ('','NAN'): print('(no name)',r.date,'skip'); continue
    ex=a[a.k==k]; lo=a[(a.k!=k)&a.k.str.contains(k,regex=False)&(a.k.str.len()<=len(k)+4)] if len(k)>=5 else a.iloc[:0]
    print(f"{r.VESSEL_NAME} [{r.VESSEL_TYPE}] {r.date} near {r.LOCATION_NEAREST_CITY}, {r.LOCATION_STATE}: exact {len(ex)}, loose {len(lo)}")
    for _,x in pd.concat([ex,lo]).head(4).iterrows(): print(f"    {x['name']} mmsi {x.mmsi} type {x.type} len {x.len} at {x.lat},{x.lon} reports {x.n}")
