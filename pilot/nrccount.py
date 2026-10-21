import pandas as pd, sys
for f in sys.argv[1:]:
    V=pd.read_excel(f,'VESSELS_DETAIL'); I=pd.read_excel(f,'INCIDENT_COMMONS'); M=pd.read_excel(f,'MATERIAL_INVOLVED')
    V['N']=V.VESSEL_NAME.astype(str).str.strip().str.upper()
    V=V[~(V.N.isin(['NAN','UNKNOWN','UNK','N/A','NONE','','NA'])|V.N.str.contains('UNKNOWN'))]
    V=V[~V.VESSEL_TYPE.isin(['PLEASURE CRAFT','MILITARY','UNKNOWN','OTHER','BARGE','MODU (MOBILE OFFSHORE DRILLING UNIT)'])]
    oil=M.NAME_OF_MATERIAL.astype(str).str.upper().str.contains('OIL|DIESEL|FUEL|GASOLINE|HYDRAULIC|LUBE|BUNKER|PETROLEUM|CRUDE') & M.IF_REACHED_WATER.astype(str).str.upper().str.startswith('Y')
    d=V[V.SEQNOS.isin(set(M[oil].SEQNOS))].merge(I[['SEQNOS','DESCRIPTION_OF_INCIDENT']],on='SEQNOS').drop_duplicates('SEQNOS')
    s=d.DESCRIPTION_OF_INCIDENT.astype(str).str.upper()
    mv=s.str.contains('AGROUND|GROUND|COLLI|ALLISION|UNDERWAY|UNDER WAY|TRANSIT|STRUCK|SANK|SINK|CAPSIZ') & ~s.str.contains('MOORED|PIER|DOCK|BERTH|MARINA|SHIPYARD|REFUEL|FUELING')
    print(f.split('/')[-1], 'commercial named oil->water', len(d), ' non-berth candidates', int(mv.sum()))
