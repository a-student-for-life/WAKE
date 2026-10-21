"""Experiment 1: build the incident table (STAGE_A_SPEC.md).

usage: python3 -I stage_a/build_incidents.py  (run from the repo root)
inputs : data/raw/nrc/CY15..CY25.xlsx, data/raw/in/incidents.csv, data/raw/geo/US.txt
outputs: data/incidents.csv, data/incidents_nrc_excluded_counts.csv, results/exp1/summary.md
"""
import math
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from names import norm_name  # noqa: E402

YEARS = range(2015, 2026)
RAW = "data/raw"

STATE_TZ = {
    "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
    "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DE": "America/New_York", "DC": "America/New_York",
    "FL": "America/New_York", "GA": "America/New_York", "HI": "Pacific/Honolulu",
    "ID": "America/Boise", "IL": "America/Chicago", "IN": "America/Indiana/Indianapolis",
    "IA": "America/Chicago", "KS": "America/Chicago", "KY": "America/New_York",
    "LA": "America/Chicago", "ME": "America/New_York", "MD": "America/New_York",
    "MA": "America/New_York", "MI": "America/Detroit", "MN": "America/Chicago",
    "MS": "America/Chicago", "MO": "America/Chicago", "MT": "America/Denver",
    "NE": "America/Chicago", "NV": "America/Los_Angeles", "NH": "America/New_York",
    "NJ": "America/New_York", "NM": "America/Denver", "NY": "America/New_York",
    "NC": "America/New_York", "ND": "America/Chicago", "OH": "America/New_York",
    "OK": "America/Chicago", "OR": "America/Los_Angeles", "PA": "America/New_York",
    "RI": "America/New_York", "SC": "America/New_York", "SD": "America/Chicago",
    "TN": "America/Chicago", "TX": "America/Chicago", "UT": "America/Denver",
    "VT": "America/New_York", "VA": "America/New_York", "WA": "America/Los_Angeles",
    "WV": "America/New_York", "WI": "America/Chicago", "WY": "America/Denver",
    "PR": "America/Puerto_Rico", "VI": "America/St_Thomas", "GU": "Pacific/Guam",
    "AS": "Pacific/Pago_Pago", "MP": "Pacific/Saipan",
}
STATE_NAMES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC",
    "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL",
    "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA",
    "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
    "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT",
    "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ",
    "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND",
    "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "PUERTO RICO": "PR",
    "U.S. VIRGIN ISLANDS": "VI", "US VIRGIN ISLANDS": "VI", "VIRGIN ISLANDS": "VI",
    "GUAM": "GU", "AMERICAN SAMOA": "AS", "NORTHERN MARIANA ISLANDS": "MP",
}

BAD_NAMES = {"NAN", "UNKNOWN", "UNK", "N/A", "NA", "NONE", "", "UNKNOWN VESSEL", "N A", "NULL"}
BAD_TYPES = {"PLEASURE CRAFT", "MILITARY", "UNKNOWN", "OTHER", "BARGE", "MODU"}
OIL = re.compile(r"OIL|DIESEL|FUEL|GASOLINE|HYDRAULIC|LUBE|BUNKER|PETROLEUM|CRUDE")
MOVING = re.compile(r"AGROUND|GROUND|COLLI|ALLISION|UNDERWAY|UNDER WAY|TRANSIT|STRUCK|SANK|SINK|CAPSIZ")
BERTH = re.compile(r"MOORED|PIER|DOCK|BERTH|MARINA|SHIPYARD|REFUEL|FUELING|DRYDOCK|SLIP")
INLAND = re.compile(r"\b(RIVERS?|BAYOUS?|CANALS?|LOCKS?|LAKES?)\b")
TYPES = [  # first match wins, in the spec's order
    ("grounding", re.compile(r"AGROUND|\bGROUND(ED|ING)\b|RAN ONTO|\bGROUNDING")),
    ("collision_allision", re.compile(r"COLLI|ALLISION|ALLIDE|\bSTRUCK\b")),
    ("sinking_capsize", re.compile(r"\bSANK\b|\bSINK|\bSUNK|CAPSIZ")),
    ("fire_explosion", re.compile(r"\bFIRE\b|EXPLO")),
    ("discharge", re.compile(r"DISCHARG|OVERBOARD|SPILL|PUMPED|OVERFLOW|RELEASED")),
    ("equipment_failure", re.compile(r"FAIL|MALFUNCTION|RUPTUR|BURST|CRACK|BROKE|LEAK")),
]
COMPASS = {d: i * 22.5 for i, d in enumerate(
    "N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW".split())}
UNIT_KM = {"MILES": 1.609344, "MILE": 1.609344, "NAUTICAL MILE": 1.852, "NAUTICAL MILES": 1.852,
           "KILOMETERS": 1.0, "KILOMETER": 1.0, "FEET": 0.0003048, "YARDS": 0.0009144}


def s(x):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else str(x).strip()


def in_us(lat, lon):
    return lat is not None and lon is not None and 17 <= lat <= 72 and -180 <= lon <= -64


def classify(text):
    t = text.upper()
    for name, rx in TYPES:
        if rx.search(t):
            return name
    return "other"


def setting(*texts):
    return "inland" if any(INLAND.search(t.upper()) for t in texts) else "sea"


def to_utc(local_dt, state):
    tz = STATE_TZ.get(state)
    if local_dt is None or tz is None:
        return "", ""
    aware = local_dt.replace(tzinfo=ZoneInfo(tz))
    return aware.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M"), tz


# ---------------------------------------------------------------- gazetteer
def place_key(x):
    x = re.sub(r"[^A-Z0-9 ]", " ", s(x).upper())
    x = re.sub(r"\bSAINT\b", "ST", x)
    x = re.sub(r"\bFORT\b", "FT", x)
    x = re.sub(r"\bMOUNT\b", "MT", x)
    return " ".join(x.split())


def load_gazetteer():
    g = pd.read_csv(f"{RAW}/geo/US.txt", sep="\t", header=None, usecols=[0, 1, 2, 4, 5, 6, 10, 14],
                    names=["gid", "name", "ascii", "lat", "lon", "fclass", "admin1", "pop"],
                    dtype={"admin1": str}, quoting=3, keep_default_na=False, low_memory=False)
    g = g[g.fclass.isin(["P", "H", "L", "S"])].copy()
    g["rank"] = g.fclass.map({"P": 0, "H": 1, "L": 2, "S": 3})
    g["pop"] = pd.to_numeric(g["pop"], errors="coerce").fillna(0)
    rows = []
    for col in ("ascii", "name"):
        t = g[["admin1", col, "lat", "lon", "rank", "pop", "gid"]].rename(columns={col: "n"})
        rows.append(t)
    t = pd.concat(rows)
    t["key"] = t.n.map(place_key)
    t = t.sort_values(["rank", "pop", "gid"], ascending=[True, False, True])
    t = t.drop_duplicates(["admin1", "key"])
    return {(a, k): (la, lo) for a, k, la, lo in zip(t.admin1, t.key, t.lat, t.lon)}


def offset(lat, lon, dist_km, bearing_deg):
    R = 6371.0
    d = dist_km / R
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def dms(deg, mn, sec):
    try:
        v = float(deg) + float(mn or 0) / 60 + float(sec or 0) / 3600
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def nrc_position(r, gaz):
    lat = dms(r.get("LAT_DEG"), r.get("LAT_MIN"), r.get("LAT_SEC"))
    lon = dms(r.get("LONG_DEG"), r.get("LONG_MIN"), r.get("LONG_SEC"))
    if lat is not None and lon is not None:
        if s(r.get("LAT_QUAD")).upper() == "S":
            lat = -lat
        lon = abs(lon) if s(r.get("LONG_QUAD")).upper() == "E" else -abs(lon)
        if in_us(lat, lon):
            return round(lat, 5), round(lon, 5), "exact"
    st = s(r.get("LOCATION_STATE")).upper()
    raw = s(r.get("LOCATION_NEAREST_CITY")).upper()
    hit = None
    for c in [raw] + re.split(r"[/&,]| AND ", raw):  # "FRANKLIN/ BALDWIN" -> try each part
        c = place_key(c)
        if c and (st, c) in gaz:
            hit = gaz[(st, c)]
            break
    if hit is None:
        return None, None, "none"
    lat, lon = hit
    dist = pd.to_numeric(s(r.get("DISTANCE_FROM_CITY")), errors="coerce")
    unit = UNIT_KM.get(s(r.get("DISTANCE_UNITS")).upper(), 1.609344)
    direc = COMPASS.get(s(r.get("DIRECTION_FROM_CITY")).upper())
    if pd.notna(dist) and dist > 0 and direc is not None:
        lat, lon = offset(lat, lon, float(dist) * unit, direc)
        return round(lat, 5), round(lon, 5), "town+offset"
    return round(lat, 5), round(lon, 5), "town"


# ---------------------------------------------------------------- NRC
def read_nrc(path):
    x = pd.read_excel(path, sheet_name=["CALLS", "INCIDENT_COMMONS", "VESSELS_DETAIL", "MATERIAL_INVOLVED"])
    return x["CALLS"], x["INCIDENT_COMMONS"], x["VESSELS_DETAIL"], x["MATERIAL_INVOLVED"]


def build_nrc(gaz):
    out, excl = [], []
    for yy in range(15, 26):
        path = f"{RAW}/nrc/CY{yy}.xlsx"
        if not os.path.exists(path):
            print("MISSING", path)
            continue
        C, I, V, M = read_nrc(path)
        for col in ("FLAG", "IS_VESSEL_AGROUND", "VESSEL_LENGTH", "VESSEL_TYPE"):
            if col not in V.columns:
                V[col] = None
        V = V.copy()
        V["name"] = V.VESSEL_NAME.map(lambda v: s(v).upper())
        V["vtype"] = V.VESSEL_TYPE.map(lambda v: s(v).upper() or "UNKNOWN")
        cnt = {"file": f"CY{yy}", "reports_with_vessel": V.SEQNOS.nunique()}
        ok = ~(V.name.isin(BAD_NAMES) | V.name.str.contains(r"\bUNKNOWN\b|^UNK\b|^N/?A$", regex=True))
        keep = set(V.SEQNOS)
        V = V[ok]
        cnt["r1_no_name"] = len(keep - set(V.SEQNOS)); keep = set(V.SEQNOS)
        badt = V.vtype.isin(BAD_TYPES) | V.vtype.str.startswith("MODU")
        V = V[~badt]
        cnt["r2_vessel_type"] = len(keep - set(V.SEQNOS)); keep = set(V.SEQNOS)
        M = M.copy()
        M["mat"] = M.NAME_OF_MATERIAL.map(lambda v: s(v).upper())
        oilw = M[M.mat.str.contains(OIL) & M.IF_REACHED_WATER.map(lambda v: s(v).upper().startswith("Y"))]
        V = V[V.SEQNOS.isin(set(oilw.SEQNOS))]
        cnt["r3_no_oil_in_water"] = len(keep - set(V.SEQNOS)); keep = set(V.SEQNOS)
        I = I.drop_duplicates("SEQNOS").set_index("SEQNOS")
        desc = I.DESCRIPTION_OF_INCIDENT.map(lambda v: s(v).upper())
        loc = I.INCIDENT_LOCATION.map(lambda v: s(v).upper())
        mv = set(desc[desc.str.contains(MOVING)].index)
        V = V[V.SEQNOS.isin(mv)]
        cnt["r4_not_moving"] = len(keep - set(V.SEQNOS)); keep = set(V.SEQNOS)
        berth = set(desc[desc.str.contains(BERTH)].index) | set(loc[loc.str.contains(BERTH)].index)
        V = V[~V.SEQNOS.isin(berth)]
        cnt["r5_berth"] = len(keep - set(V.SEQNOS)); keep = set(V.SEQNOS)
        dt = pd.to_datetime(I.INCIDENT_DATE_TIME.astype(str), errors="coerce", format="mixed")
        inyr = set(dt[dt.dt.year.isin(list(YEARS))].index)
        V = V[V.SEQNOS.isin(inyr)]
        cnt["date_outside_2015_2025"] = len(keep - set(V.SEQNOS))
        cnt["kept_reports"] = V.SEQNOS.nunique()
        cnt["kept_vessel_rows"] = len(V)
        excl.append(cnt)
        mats = oilw.groupby("SEQNOS")
        V = V.drop_duplicates(["SEQNOS", "name"])
        k = V.groupby("SEQNOS").cumcount()
        n = V.groupby("SEQNOS").SEQNOS.transform("size")
        for (_, v), kk, nn in zip(V.iterrows(), k, n):
            q = v.SEQNOS
            r = I.loc[q].to_dict()
            ldt = dt.loc[q]
            ldt = None if pd.isna(ldt) else ldt.to_pydatetime()
            st = s(r.get("LOCATION_STATE")).upper()
            tutc, tz = to_utc(ldt, st)
            lat, lon, meth = nrc_position(r, gaz)
            m = mats.get_group(q)
            d = s(r.get("DESCRIPTION_OF_INCIDENT"))
            out.append(dict(
                incident_id=f"N{q}" + (f"_{kk + 1}" if nn > 1 else ""), source="NRC", source_id=str(q),
                linked_ids="", vessel_name=v["name"], name_norm=norm_name(v["name"]),
                vessel_type_reported=v.vtype, length_ft=s(v.VESSEL_LENGTH), flag=s(v.FLAG),
                aground=s(v.IS_VESSEL_AGROUND),
                date_local=ldt.strftime("%Y-%m-%d") if ldt else "",
                time_local=ldt.strftime("%H:%M") if ldt else "", tz=tz, time_utc=tutc,
                time_assumed_local="true", state=st,
                place_text="; ".join(x for x in (s(r.get("INCIDENT_LOCATION")), s(r.get("LOCATION_NEAREST_CITY")),
                                                 s(r.get("LOCATION_COUNTY"))) if x),
                ref_lat=lat, ref_lon=lon, ref_method=meth,
                incident_type=classify(s(r.get("TYPE_OF_INCIDENT")) + " " + d),
                setting=setting(s(r.get("INCIDENT_LOCATION")), d),
                material="; ".join(m.mat), amount="; ".join(m.AMOUNT_OF_MATERIAL.map(s)),
                units="; ".join(m.UNIT_OF_MEASURE.map(s)),
                amount_in_water="; ".join(m.AMOUNT_IN_WATER.map(s)),
                units_in_water="; ".join(m.UNIT_OF_MEASURE_REACH_WATER.map(s)),
                description=re.sub(r"\s+", " ", d)))
        print(cnt, flush=True)
    return pd.DataFrame(out), pd.DataFrame(excl)


# ---------------------------------------------------------------- IncidentNews
PREFIX = (r"(?:(?i:M/V|F/V|T/V|M/T|S/V|P/V|R/V|OSV|tug(?:boat)?|towboat|tank vessel|tank barge|"
          r"cargo vessel|container ship|fishing vessel)|MV|FV)")  # MV/FV: slashless spellings
TOKEN = r"[A-Z0-9][A-Za-z0-9\.\-'&/]*"
NAME_RX = re.compile(r"\b" + PREFIX + r"\s+[\"'“‘]?(" + TOKEN + r"(?:\s+" + TOKEN + r"){0,4})")
STOP_FIRST = {"THE", "A", "AN", "IN", "ON", "AT", "AND", "WAS", "IS", "WITH", "USCG", "NOAA", "SSC", "OF"}
STOP_TAIL = {"THE", "IN", "ON", "AT", "AND", "WAS", "IS", "OF", "NEAR", "USCG", "NOAA", "SSC", "TO"}
EVENT = {"SINKING", "SINKS", "SANK", "SUNK", "GROUNDING", "GROUNDED", "AGROUND", "ALLISION", "COLLISION",
         "FIRE", "SPILL", "FRACTURE", "HULL", "DISCHARGE", "INCIDENT", "RELEASE", "CAPSIZED", "CAPSIZE",
         "CAPSIZING", "ADRIFT", "OIL", "SHEEN", "LEAK", "LEAKING", "EXPLOSION", "BREACH", "DERELICT", "WRECK",
         "SALVAGE", "RESPONSE", "TAKING", "DISABLED", "PARTIALLY", "SUNKEN", "BURNING", "STRIKE", "LOST",
         "VESSEL", "ENGINE", "FUEL", "DIESEL", "SUBMERGED", "STUCK", "ASHORE", "POTENTIAL", "FUELING",
         "DISCHARGING", "LISTING", "SHEENING", "DRIFTING", "RELEASING", "SPILLS", "LOSES", "CAPSIZED/SUNK"}
GENERIC = {"ALL", "VESSEL", "BARGE", "TUG", "TOWBOAT", "CAPTAIN", "OPERATOR", "OWNER", "COMPANY", "CREW",
           "MASTER", "SECTOR", "STATION", "UNIT", "COAST", "GUARD", "COASTGUARD", "BOAT", "SHIP"}


def extract_names(text):
    found = []
    for m in NAME_RX.finditer(text):
        toks = []
        for tk in m.group(1).split():
            if tk.endswith(".") and len(tk) > 2:  # sentence end
                toks.append(tk[:-1]); break
            toks.append(tk)
        cut = [i for i, tk in enumerate(toks) if tk.upper().strip(".,") in EVENT]
        if cut:
            toks = toks[:cut[0]]
        while toks and toks[0].upper().strip(".") in STOP_FIRST:
            toks = toks[1:]
        while toks and toks[-1].upper().strip(".,") in STOP_TAIL:
            toks = toks[:-1]
        nm = " ".join(toks).strip(".,;:'\"”’")
        nn = norm_name(nm)
        if len(nn) >= 3 and nn not in GENERIC and not nn.isdigit():
            found.append((nm, nn))
    return found


def in_state(loc, lat, lon):
    parts = [p.strip().upper() for p in re.split(r"[,;]", loc)]
    for p in reversed(parts):
        if p in STATE_NAMES:
            return STATE_NAMES[p]
        m = re.match(r"^(?:.*\s)?([A-Z]{2})(?:\s+\d{5})?$", p)
        if m and m.group(1) in STATE_TZ:
            return m.group(1)
    u = loc.upper()
    for nm, code in sorted(STATE_NAMES.items(), key=lambda t: -len(t[0])):
        if re.search(r"\b" + re.escape(nm) + r"\b", u):
            return code
    return ""


def build_in():
    r = pd.read_csv(f"{RAW}/in/incidents.csv", dtype=str, keep_default_na=False, encoding_errors="replace")
    r = r[r.open_date.str[:4].isin([str(y) for y in YEARS])]
    tags = r.tags.str.split(r"[|,]")
    bad = tags.map(lambda t: any(x.strip() in {"Pipeline", "Wellhead", "Railcar", "Hurricane"} for x in t))
    stats = {"records_2015_2025": len(r), "excluded_by_tag": int(bad.sum())}
    r = r[~bad]
    out, named = [], 0
    for _, x in r.iterrows():
        names, seen = [], set()
        for nm, nn in extract_names(x["name"] + " . " + x["description"]):
            if nn not in seen:
                seen.add(nn); names.append((nm, nn))
        if not names:
            continue
        named += 1
        lat, lon = pd.to_numeric(x.lat, errors="coerce"), pd.to_numeric(x.lon, errors="coerce")
        ok = pd.notna(lat) and pd.notna(lon) and in_us(float(lat), float(lon))
        st = in_state(x.location, lat, lon)
        d = re.sub(r"\s+", " ", x.description)
        for k, (nm, nn) in enumerate(names):
            out.append(dict(
                incident_id=f"I{x.id}" + (f"_{k + 1}" if len(names) > 1 else ""), source="IncidentNews",
                source_id=x.id, linked_ids="", vessel_name=nm.upper(), name_norm=nn,
                vessel_type_reported="", length_ft="", flag="", aground="",
                date_local=x.open_date[:10], time_local="", tz=STATE_TZ.get(st, ""), time_utc="",
                time_assumed_local="", state=st, place_text=x.location,
                ref_lat=round(float(lat), 5) if ok else None, ref_lon=round(float(lon), 5) if ok else None,
                ref_method="exact" if ok else "none",
                incident_type=classify(x.tags + " " + x["name"] + " " + d), setting=setting(x.location, x["name"], d),
                material=x.commodity, amount=x.max_ptl_release_gallons,
                units="gallons (max potential)" if x.max_ptl_release_gallons else "",
                amount_in_water="", units_in_water="", description=d[:2000]))
    stats["records_naming_vessel"] = named
    stats["name_candidates"] = len(out)
    return pd.DataFrame(out), stats


def dedupe(nrc, inc):
    nrc = nrc.copy()
    nd = pd.to_datetime(nrc.date_local, errors="coerce")
    by = {}
    for i, (nn, d) in enumerate(zip(nrc.name_norm, nd)):
        by.setdefault(nn, []).append((i, d))
    drop, links = [], {}
    for j, (nn, d) in enumerate(zip(inc.name_norm, pd.to_datetime(inc.date_local, errors="coerce"))):
        hits = [i for i, dd in by.get(nn, []) if pd.notna(dd) and pd.notna(d) and abs((dd - d).days) <= 2]
        if hits:
            drop.append(j)
            for i in hits:
                links.setdefault(i, []).append(inc.source_id.iloc[j])
    for i, ids in links.items():
        nrc.iat[i, nrc.columns.get_loc("linked_ids")] = ";".join(sorted(set(ids)))
    return nrc, inc.drop(inc.index[drop]), len(drop)


def md_table(df):
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def main():
    gaz = load_gazetteer()
    print("gazetteer keys", len(gaz), flush=True)
    nrc, excl = build_nrc(gaz)
    inc, in_stats = build_in()
    nrc, inc, ndup = dedupe(nrc, inc)
    allx = pd.concat([nrc, inc], ignore_index=True)
    allx["year"] = allx.date_local.str[:4]
    os.makedirs("results/exp1", exist_ok=True)
    allx.drop(columns="year").to_csv("data/incidents.csv", index=False)
    excl.to_csv("data/incidents_nrc_excluded_counts.csv", index=False)
    files = sorted(excl.file) if len(excl) else []
    missing = [f"CY{yy}" for yy in range(15, 26) if f"CY{yy}" not in files]
    parts = [
        "# Experiment 1: incident table summary",
        "",
        "Generated by `stage_a/build_incidents.py` from `data/incidents.csv`.",
        f"NRC annual files used: {', '.join(files)}." + (f" **Missing: {', '.join(missing)}.**" if missing else ""),
        "NRC incidents dated 2015–2025 are taken from the files of those years only; a late 2025 incident"
        " filed in CY26 is not included.",
        "",
        f"Rows: {len(allx)} ({(allx.source == 'NRC').sum()} NRC, {(allx.source == 'IncidentNews').sum()} IncidentNews)."
        f" IncidentNews rows merged into an NRC record (same normalised name within 2 days): {ndup}.",
        "",
        "IncidentNews: " + ", ".join(f"{k} {v}" for k, v in in_stats.items()) + ".",
        "",
        "## By source and year", "",
        md_table(pd.crosstab(allx.year, allx.source, margins=True, margins_name="total").reset_index()),
        "", "## By incident type", "",
        md_table(pd.crosstab(allx.incident_type, allx.source, margins=True, margins_name="total").reset_index()),
        "", "## By setting", "",
        md_table(pd.crosstab(allx.setting, allx.source, margins=True, margins_name="total").reset_index()),
        "", "## By position method", "",
        md_table(pd.crosstab(allx.ref_method, allx.source, margins=True, margins_name="total").reset_index()),
        "", "## NRC records removed by each rule (applied in order, counted in reports)", "",
        md_table(excl),
        "",
        "Notes: a missing VESSEL_TYPE is treated as UNKNOWN (rule 2). Types beginning with MODU are excluded;"
        " DRILLING RIG is not in the spec's list and is kept. IncidentNews positions are NOAA's lat/lon and are"
        " marked `exact` when inside US waters (lat 17–72, lon -180 to -64). GeoNames US.txt has no Puerto Rico,"
        " Virgin Islands or Guam places, so those NRC records without coordinates get `ref_method = none`.",
    ]
    open("results/exp1/summary.md", "w").write("\n".join(parts) + "\n")
    print("wrote", len(allx), "rows")


if __name__ == "__main__":
    main()
