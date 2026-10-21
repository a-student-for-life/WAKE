"""Print one candidate's facts, its incident record and a condensed track, for Claude's
case-by-case review. It only displays; it makes no decision.

usage: python3 -I stage_a/show_case.py <incident_id> <mmsi>
"""
import math
import sys

import pandas as pd


def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(min(1, x)))


def main(iid, mmsi):
    c = pd.read_csv("data/candidates.csv", dtype=str, keep_default_na=False)
    i = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False)
    r = i[i.incident_id == iid].iloc[0]
    row = c[(c.incident_id == iid) & (c.mmsi == mmsi)].iloc[0]
    print("INCIDENT", iid, "|", r.source, r.source_id, "linked", r.linked_ids)
    for k in ("vessel_name", "vessel_type_reported", "length_ft", "flag", "aground", "date_local", "time_local",
              "tz", "time_utc", "state", "place_text", "ref_lat", "ref_lon", "ref_method", "incident_type", "setting",
              "material", "amount", "units"):
        print(f"  {k}: {r[k]}")
    print("  description:", r.description[:900])
    print("CANDIDATE")
    for k in row.index:
        if k not in r.index or k in ("incident_id",):
            print(f"  {k}: {row[k]}")
    others = c[(c.incident_id == iid) & (c.mmsi != mmsi)]
    for _, o in others.iterrows():
        print(f"  other candidate {o.mmsi} {o.ais_name} {o.match} closest {o.closest_km} km type {o.ais_type} len {o.ais_length_m}")
    t = pd.read_csv(f"data/tracks/{iid}_{mmsi}.csv.gz")
    t["time"] = pd.to_datetime(t.time)
    lat0 = float(r.ref_lat) if r.ref_lat else None
    lon0 = float(r.ref_lon) if r.ref_lon else None
    if lat0 is not None:
        t["km"] = [hav(lat0, lon0, a, b) for a, b in zip(t.lat, t.lon)]
    t["hour"] = t.time.dt.floor("h")
    agg = {"lat": "mean", "lon": "mean", "sog": ["min", "max"], "time": "count"}
    if "km" in t:
        agg["km"] = "min"
    g = t.groupby("hour").agg(agg)
    g.columns = ["_".join(x) for x in g.columns]
    print("TRACK by hour (UTC): mean lat/lon, SOG min/max, n positions" + (", min km to ref" if "km" in t else ""))
    print(g.round(3).to_string())
    print("first", t.time.min(), "last", t.time.max(), "status", t.status.value_counts().head(3).to_dict())


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
