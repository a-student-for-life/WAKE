import json, math, pandas as pd, numpy as np
from shapely.geometry import shape, box, mapping, Point
from shapely.ops import unary_union
D='demo/'
def load(f):
    g=json.load(open(D+f)); return [shape(x['geometry']) for x in g['features']]
land10=load('land10.geojson'); land50=load('ne_50m_land.geojson'); rivers=load('ne_10m_rivers_lake_centerlines.geojson'); lakes=load('ne_10m_lakes.geojson')
def hav(a,b,c,d):
    R=6371.0; p1,p2=math.radians(a),math.radians(c); dp=p2-p1; dl=math.radians(d-b)
    h=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2; return 2*R*math.asin(math.sqrt(h))
cases=[
 dict(id='robert-t', day='2023-04-07', mmsi=366989990, name='ROBERT T.', tz=-5, tzname='CDT',
      rtime='2023-04-07 02:10', rtype='Tow boat', rlen_ft=107, flag='United States',
      place='Mississippi River, near Columbus, Kentucky', ref=(36.761,-89.104), ref_exact=False, ref_label='Columbus, KY (town; no exact position in report)',
      what='About 20 gallons of diesel overflowed from a mid tank into the Mississippi River. Boom deployed, clean-up under way. Cause unknown.',
      spill='Diesel, about 20 gal, reached water', aground='No',
      seq=1364173, others=[('ROBERT T',367540560,36.838,-76.254,'Norfolk, Virginia')],
      verdict='Yes', why='Same name, a tow boat in AIS too, length 32 m against 107 ft (33 m) in the report, and it was working this stretch of the Mississippi next to Columbus. The other ROBERT T that day was at Norfolk, Virginia, about 1,000 km away, so it can be ruled out. Its AIS only starts about 2 h after the report time, which is common on rivers and doesn\'t count against it.'),
 dict(id='miss-kara', day='2023-08-05', mmsi=367706440, name='MISS KARA', tz=-4, tzname='EDT',
      rtime='2023-08-05 13:00', rtype='Fishing vessel', rlen_ft=55, flag='Not given',
      place='Nantucket Sound, 8 nautical miles east of Nantucket Island, Massachusetts', ref=(41.284,-69.923), ref_exact=False, ref_label='8 nm east of Nantucket town, as reported',
      what='A blue fishing vessel was found sinking with some sheen on the water. Three people on board were rescued by the Coast Guard. Diesel, amount unknown.',
      spill='Diesel, amount unknown, reached water', aground='No',
      seq=1375316, others=[],
      verdict='Unsure (leaning yes)', why='Name, type and length all fit: a fishing vessel, 16 m against 55 ft (17 m). It was in Nantucket Sound that morning. But its AIS stops about 9 hours before the report, around 20 km from the reported spot, and the report\'s location is itself muddled (Nantucket Sound lies north of the island, not east). A sinking boat often loses AIS, so this is plausible, but the track can\'t confirm it. I\'d mark it unsure; it would go into the sensitivity analysis, not the main one.'),
 dict(id='supreme-valor', day='2023-09-03', mmsi=636022008, name='SUPREME VALOR', tz=-5, tzname='CDT',
      rtime='2023-09-03 07:20', rtype='Bulk carrier (dry bulk)', rlen_ft=650, flag='Liberia',
      place='Sabine Pass, Texas (at a terminal, Port City Partners)', ref=(29.728,-93.870), ref_exact=False, ref_label='Sabine Pass, TX (town; no exact position in report)',
      what='The vessel ran aground because the terminal gave it the wrong depth. Possible release of ballast water or diesel. 57,000 tons of dry concrete on board, not expected to spill.',
      spill='Diesel and ballast water, amounts unknown, reached water', aground='Yes',
      seq=1378035, others=[],
      verdict='Yes', why='Same name, a cargo ship of 197 m against 650 ft (198 m) in the report, and the track runs in from the Gulf to Sabine Pass and stops there around the report time, which fits a grounding on arrival.'),
 dict(id='cricket', day='2023-10-04', mmsi=338150633, name='CRICKET', tz=-7, tzname='PDT',
      rtime='2023-10-04 08:00', rtype='Fishing vessel', rlen_ft=None, flag='Not given',
      place='Johnson Pier work dock, Half Moon Bay, California', ref=(37.502,-122.482), ref_exact=False, ref_label='Johnson Pier, Half Moon Bay, CA',
      what='Oil discharging from the engine room of a vessel that had already sunk at the pier. Linked to two earlier reports. The owner has not taken responsibility.',
      spill='Unknown oil, amount unknown, reached water', aground='No',
      seq=1380862, others=[],
      verdict='No', why='The only CRICKET in AIS that day sat all day on the New Jersey coast, about 4,100 km from Half Moon Bay. Same name, wrong vessel. In the real check a candidate this far away would be dropped automatically; it is here to show what a clear no looks like.'),
 dict(id='blue-dolphin', day='2023-10-04', mmsi=369552000, name='BLUE DOLPHIN', tz=-5, tzname='CDT',
      rtime='2023-10-04 15:00', rtype='Offshore supply vessel', rlen_ft=280, flag='United States',
      place='Gulf of Mexico, offshore Louisiana (exact position given)', ref=(27+21/60+42/3600, -(90+44/60+48/3600)), ref_exact=True, ref_label='Position given in the report',
      what='About 25 gallons of hydraulic oil leaked from the vessel\'s swing-down thruster into the Gulf of Mexico. Cause under investigation.',
      spill='Hydraulic oil, about 25 gal, reached water', aground='No',
      seq=1380898, others=[],
      verdict='Yes', why='The report gives an exact position, and the AIS BLUE DOLPHIN, 91 m against 280 ft (85 m), was holding position about 6–9 km from it all morning, as supply vessels do beside a platform. AIS goes quiet 12 hours before the report, which is normal this far offshore where coastal receivers can\'t hear it, so the gap doesn\'t count against it.'),
]
W,H,PAD=640,420,28
out=[]
for c in cases:
    t=pd.read_csv(D+c['day']+'.tracks.csv'); t['BaseDateTime']=pd.to_datetime(t.BaseDateTime)
    g=t[t.MMSI==c['mmsi']].sort_values('BaseDateTime').reset_index(drop=True)
    rt_local=pd.Timestamp(c['rtime']); rt_utc=rt_local-pd.Timedelta(hours=c['tz'])
    lats=list(g.LAT)+[c['ref'][0]]; lons=list(g.LON)+[c['ref'][1]]
    for o in c['others']: pass
    la0,la1,lo0,lo1=min(lats),max(lats),min(lons),max(lons)
    span=max(la1-la0,(lo1-lo0)*math.cos(math.radians((la0+la1)/2)),0.06)
    m=span*0.25+0.02
    la0-=m;la1+=m;lo0-=m/math.cos(math.radians(la0));lo1+=m/math.cos(math.radians(la0))
    latc=(la0+la1)/2; k=math.cos(math.radians(latc))
    sx=(W-2*PAD)/((lo1-lo0)*k); sy=(H-2*PAD)/(la1-la0); s=min(sx,sy)
    cx=(lo0+lo1)/2; cy=latc
    def P(lon,lat): return (round(W/2+(lon-cx)*k*s,1), round(H/2-(lat-cy)*s,1))
    vw=(W/2)/(k*s); vh=(H/2)/s
    bb=box(cx-vw,cy-vh,cx+vw,cy+vh)
    big=(lo1-lo0)>8
    L=land50 if big else land10
    tol=(2*vw)/W*0.8
    polys=[p.intersection(bb) for p in L if p.intersects(bb)]
    def pathof(geom):
        segs=[]
        gs=[geom] if geom.geom_type in('Polygon','LineString') else list(getattr(geom,'geoms',[]))
        for x in gs:
            x=x.simplify(tol)
            if x.is_empty: continue
            if x.geom_type=='Polygon':
                for ring in [x.exterior]+list(x.interiors):
                    pts=[P(a,b) for a,b in ring.coords]
                    segs.append('M'+'L'.join(f'{p[0]},{p[1]}' for p in pts)+'Z')
            elif x.geom_type=='LineString':
                pts=[P(a,b) for a,b in x.coords]
                if len(pts)>1: segs.append('M'+'L'.join(f'{p[0]},{p[1]}' for p in pts))
            elif hasattr(x,'geoms'):
                segs.append(pathof(x))
        return ''.join(segs)
    land=''.join(pathof(p) for p in polys)
    lake=''.join(pathof(p.intersection(bb)) for p in lakes if p.intersects(bb)) if not big else ''
    riv=''.join(pathof(p.intersection(bb)) for p in rivers if p.intersects(bb)) if not big else ''
    # track downsample
    step=max(1,len(g)//350); gg=g.iloc[::step]
    t0=pd.Timestamp(c['day']); 
    trk=[dict(x=P(r.LON,r.LAT)[0],y=P(r.LON,r.LAT)[1],h=round((r.BaseDateTime-t0).total_seconds()/3600,2),sog=r.SOG) for r in gg.itertuples()]
    # facts
    first,last=g.BaseDateTime.min(),g.BaseDateTime.max()
    if first<=rt_utc<=last:
        i=(g.BaseDateTime-rt_utc).abs().idxmin(); r=g.loc[i]; gap=0
        dist=hav(r.LAT,r.LON,*c['ref']); timenote=f"AIS is reporting at the report time"
        atpt=P(r.LON,r.LAT)
    else:
        r=g.iloc[-1] if rt_utc>last else g.iloc[0]
        gaph=abs((rt_utc-(last if rt_utc>last else first)).total_seconds())/3600
        dist=hav(r.LAT,r.LON,*c['ref'])
        timenote=(f"AIS stops {gaph:.0f} h before the report time" if rt_utc>last else f"AIS starts {gaph:.0f} h after the report time")
        atpt=P(r.LON,r.LAT)
    mind=min(hav(a,b,*c['ref']) for a,b in zip(g.LAT,g.LON))
    others=[dict(name=o[0],mmsi=o[1],place=o[4],km=round(hav(o[2],o[3],*c['ref']))) for o in c['others']]
    # scale bar
    nice=[0.5,1,2,5,10,20,50,100,200,500,1000,2000]
    kmpx=1/(s/111.32*1)  # km per px approx (lat)
    target=W*0.18*kmpx; sb=max([n for n in nice if n<=target] or [nice[0]])
    rec=dict(id=c['id'],name=c['name'],rtime_local=rt_local.strftime('%-d %b %Y, %H:%M'),tzname=c['tzname'],tz=c['tz'],
      rtype=c['rtype'],rlen=(f"{c['rlen_ft']} ft ({c['rlen_ft']*0.3048:.0f} m)" if c['rlen_ft'] else 'Not given'),flag=c['flag'],
      place=c['place'],what=c['what'],spill=c['spill'],aground=c['aground'],seq=c['seq'],
      ais=dict(name=g.VesselName.iloc[0],mmsi=int(c['mmsi']),type_code=int(g.VesselType.iloc[0]) if not pd.isna(g.VesselType.iloc[0]) else None,
               length=(f"{g.Length.iloc[0]:.0f} m" if not pd.isna(g.Length.iloc[0]) else 'Not broadcast'),
               first=(first+pd.Timedelta(hours=c['tz'])).strftime('%H:%M'),last=(last+pd.Timedelta(hours=c['tz'])).strftime('%H:%M'),n=len(g),maxsog=float(g.SOG.max())),
      dist_at=round(dist,1),dist_min=round(mind,1),timenote=timenote,others=others,
      ref=dict(xy=P(c['ref'][1],c['ref'][0]),label=c['ref_label'],exact=c['ref_exact']),atpt=atpt,
      rt_h=round((rt_utc-t0).total_seconds()/3600,2),
      map=dict(w=W,h=H,land=land,lake=lake,river=riv,sb_km=sb,sb_px=round(sb/kmpx,1)),track=trk,verdict=c['verdict'],why=c['why'])
    out.append(rec)
    print(c['id'],'| pts',len(g),'| at report',rec['dist_at'],'km | min',rec['dist_min'],'km |',timenote,'| AIS local',rec['ais']['first'],'-',rec['ais']['last'],'| land chars',len(land),'riv',len(riv),'| sb',sb,'km')
json.dump(out,open(D+'cases.json','w'))
import os; print(os.path.getsize(D+'cases.json'))
