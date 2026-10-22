"""Build the blind review page data: one JSON chunk per 25 cases, plus the case order.

usage: python3 -I review_page/build_review.py   (from the repo root)
inputs : data/candidates.csv (rows not auto-rejected), data/incidents.csv,
         data/tracks/<incident>_<mmsi>.csv.gz, data/raw/ne/*.geojson (Natural Earth)
outputs: review_page/build/cases_NN.json, review_page/build/index.json

BLIND: nothing from data/claude_review.csv is read here, so Claude's decisions cannot
reach the page. Order is a fixed random permutation (seed 20261022), so the first 50
are a random sample.
"""
import json
import math
import os
import re
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from shapely.geometry import box, shape
from shapely.strtree import STRtree

OUT = "review_page/build"
CHUNK = 25
W, H, PAD = 640, 420, 28
NE = "data/raw/ne"
TYPE = {0: "Not given", 30: "Fishing", 31: "Towing", 32: "Towing (long tow)", 33: "Dredging",
        34: "Diving", 35: "Military", 36: "Sailing", 37: "Pleasure craft", 50: "Pilot", 51: "Search and rescue",
        52: "Tug", 53: "Port tender", 55: "Law enforcement", 1001: "Commercial fishing (old code)",
        1004: "Freight ship (old code)", 1019: "Recreational (old code)"}


def type_label(code):
    try:
        c = int(float(code))
    except (TypeError, ValueError):
        return "Not given"
    if c in TYPE:
        return TYPE[c]
    if 60 <= c <= 69:
        return "Passenger"
    if 70 <= c <= 79:
        return "Cargo"
    if 80 <= c <= 89:
        return "Tanker"
    if 90 <= c <= 99:
        return "Other type"
    if 1000 <= c <= 1100:
        return "Old code, meaning unclear"
    return "Other"


def num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, h)))


def sentence_case(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    if not t or sum(ch.isupper() for ch in t) < 0.6 * sum(ch.isalpha() for ch in t):
        return t
    t = t.lower()
    t = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    for w in ("uscg", "noaa", "nrc", "ssc", "imo", "mmsi", "ais", "llc", "inc", "usa", "us"):
        t = re.sub(rf"\b{w}\b", w.upper(), t)
    return t


def load_ne(name):
    g = json.load(open(f"{NE}/{name}.geojson"))
    geoms = [shape(f["geometry"]) for f in g["features"]]
    return geoms, STRtree(geoms)


LAND10, LAND50, RIVERS, LAKES = (load_ne(n) for n in ("land10", "ne_50m_land", "ne_10m_rivers_lake_centerlines",
                                                       "ne_10m_lakes"))


def clip(layer, bb):
    geoms, tree = layer
    return [geoms[i].intersection(bb) for i in tree.query(bb)]


def path_of(geom, P, tol):
    out = []
    gs = [geom] if geom.geom_type in ("Polygon", "LineString") else list(getattr(geom, "geoms", []))
    for x in gs:
        x = x.simplify(tol)
        if x.is_empty:
            continue
        if x.geom_type == "Polygon":
            for ring in [x.exterior] + list(x.interiors):
                pts = [P(a, b) for a, b in ring.coords]
                out.append("M" + "L".join(f"{p[0]},{p[1]}" for p in pts) + "Z")
        elif x.geom_type == "LineString":
            pts = [P(a, b) for a, b in x.coords]
            if len(pts) > 1:
                out.append("M" + "L".join(f"{p[0]},{p[1]}" for p in pts))
        elif hasattr(x, "geoms"):
            out.append(path_of(x, P, tol))
    return "".join(out)


def local(ts, tz):
    if pd.isna(ts):
        return ""
    t = ts.tz_localize("UTC")
    if tz:
        t = t.tz_convert(ZoneInfo(tz))
    return t.strftime("%-d %b %Y %H:%M")


def build_case(c, inc, others):
    tz = inc.tz or ""
    tzlab = "" if tz else "UTC"
    tr = pd.read_csv(f"data/tracks/{c.incident_id}_{c.mmsi}.csv.gz", dtype=str, keep_default_na=False)
    tr["t"] = pd.to_datetime(tr.time, errors="coerce")
    tr["la"], tr["lo"] = pd.to_numeric(tr.lat, errors="coerce"), pd.to_numeric(tr.lon, errors="coerce")
    tr = tr[tr.la.notna() & tr.lo.notna() & tr.t.notna()].sort_values("t")
    if tz:
        tzlab = pd.Timestamp(tr.t.iloc[0]).tz_localize("UTC").tz_convert(ZoneInfo(tz)).strftime("%Z")
    ref = (num(inc.ref_lat), num(inc.ref_lon))
    alt = (num(inc.alt_lat), num(inc.alt_lon))
    show_alt = alt[0] is not None and (ref[0] is None or hav(*ref, *alt) > 10)
    pts_lat, pts_lon = list(tr.la), list(tr.lo)
    marks = [p for p in (ref, alt if show_alt else (None, None)) if p[0] is not None]
    lats = pts_lat + [p[0] for p in marks]
    lons = pts_lon + [p[1] for p in marks]
    la0, la1, lo0, lo1 = min(lats), max(lats), min(lons), max(lons)
    k = math.cos(math.radians((la0 + la1) / 2))
    span = max(la1 - la0, (lo1 - lo0) * k, 0.06)
    m = span * 0.25 + 0.02
    la0, la1 = la0 - m, la1 + m
    lo0, lo1 = lo0 - m / k, lo1 + m / k
    latc = (la0 + la1) / 2
    k = math.cos(math.radians(latc))
    s = min((W - 2 * PAD) / ((lo1 - lo0) * k), (H - 2 * PAD) / (la1 - la0))
    cx, cy = (lo0 + lo1) / 2, latc

    def P(lon, lat):
        return (round(W / 2 + (lon - cx) * k * s, 1), round(H / 2 - (lat - cy) * s, 1))

    vw, vh = (W / 2) / (k * s), (H / 2) / s
    bb = box(cx - vw, cy - vh, cx + vw, cy + vh)
    big = (2 * vw) > 8
    tol = (2 * vw) / W * 0.8
    land = "".join(path_of(g, P, tol) for g in clip(LAND50 if big else LAND10, bb))
    lake = "" if big else "".join(path_of(g, P, tol) for g in clip(LAKES, bb))
    river = "" if big else "".join(path_of(g, P, tol) for g in clip(RIVERS, bb))
    step = max(1, len(tr) // 400)
    g = tr.iloc[::step]
    if g.index[-1] != tr.index[-1]:
        g = pd.concat([g, tr.iloc[[-1]]])
    t0 = tr.t.iloc[0]
    track = [dict(x=P(lo, la)[0], y=P(lo, la)[1], h=round((t - t0).total_seconds() / 3600, 3), sog=sog,
                  tl=local(t, tz)[-5:], dl=local(t, tz)[:-6])
             for lo, la, t, sog in zip(g.lo, g.la, g.t, g.sog)]
    t_rep = pd.to_datetime(inc.time_utc, errors="coerce") if inc.time_utc else pd.NaT
    if pd.notna(t_rep):
        j = (tr.t - t_rep).abs().values.argmin()
        gap = (tr.t.iloc[j] - t_rep).total_seconds() / 3600
        at = P(tr.lo.iloc[j], tr.la.iloc[j])
        if abs(gap) < 0.5:
            timenote = "AIS was reporting at the report time"
        elif gap > 0:
            timenote = f"AIS starts {gap:.0f} h after the report time" if j == 0 else f"nearest position {gap:.0f} h after the report time"
        else:
            timenote = (f"AIS stops {-gap:.0f} h before the report time" if j == len(tr) - 1
                        else f"nearest position {-gap:.0f} h before the report time")
        dist_at = round(hav(*ref, tr.la.iloc[j], tr.lo.iloc[j]), 1) if ref[0] is not None else None
    else:
        at, timenote, dist_at = None, "The report gives a date only, no time", None
    dmin = round(min(hav(*ref, a, b) for a, b in zip(tr.la, tr.lo)), 1) if ref[0] is not None else None
    dmin_alt = round(min(hav(*alt, a, b) for a, b in zip(tr.la, tr.lo)), 1) if show_alt else None
    L = num(inc.length_ft)
    nice = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    kmpx = 111.32 / s
    sb = max([n for n in nice if n <= W * 0.18 * kmpx] or [0.5])
    when = f"{inc.date_local} {inc.time_local}".strip()
    return dict(
        key=f"{c.incident_id}__{c.mmsi}",
        report=dict(name=inc.vessel_name, source=("Coast Guard NRC report #" if inc.source == "NRC" else "NOAA IncidentNews #")
                    + inc.source_id, when=when, tz=tzlab or (tz and tz.split("/")[-1].replace("_", " ")) or "",
                    date_only=not bool(inc.time_utc), type=inc.vessel_type_reported.title() or "Not given",
                    length=(f"{L:.0f} ft ({L * 0.3048:.0f} m)" if L else "Not given"), flag=inc.flag.title() or "Not given",
                    aground={"Y": "Yes", "N": "No"}.get(inc.aground, "Not given"),
                    place=inc.place_text, state=inc.state,
                    material=inc.material.title(), text=sentence_case(inc.description)),
        ais=dict(name=c.ais_name, mmsi=c.mmsi, match=c.match, type=type_label(c.ais_type),
                 code=c.ais_type or "–", length=(f"{float(c.ais_length_m):.0f} m" if num(c.ais_length_m) else "Not broadcast"),
                 first=local(tr.t.iloc[0], tz), last=local(tr.t.iloc[-1], tz), n=len(tr),
                 timenote=timenote, dist_at=dist_at, dmin=dmin, dmin_alt=dmin_alt),
        ref=dict(method=inc.ref_method, xy=P(ref[1], ref[0]) if ref[0] is not None else None,
                 alt=P(alt[1], alt[0]) if show_alt else None),
        at=at, others=others,
        map=dict(w=W, h=H, land=land, lake=lake, river=river, sb_km=sb, sb_px=round(sb / kmpx, 1)),
        track=track)


def main():
    cand = pd.read_csv("data/candidates.csv", dtype=str, keep_default_na=False)
    inc = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False).set_index("incident_id")
    rev = cand[cand.auto_reject == ""].copy()
    rng = np.random.default_rng(20261022)
    order = list(rev.index[rng.permutation(len(rev))])
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    keys, chunk, n_chunk = [], [], 0
    for i, idx in enumerate(order):
        c = rev.loc[idx]
        same = cand[(cand.incident_id == c.incident_id) & (cand.mmsi != c.mmsi)]
        others = [dict(name=o.ais_name, km=(round(float(o.closest_km)) if num(o.closest_km) is not None else None))
                  for o in same.itertuples()]
        case = build_case(c, inc.loc[c.incident_id], others)
        keys.append(case["key"])
        chunk.append(case)
        if len(chunk) == CHUNK or i == len(order) - 1:
            json.dump(chunk, open(f"{OUT}/cases_{n_chunk:02d}.json", "w"), separators=(",", ":"))
            chunk, n_chunk = [], n_chunk + 1
        if i % 50 == 0:
            print(i, flush=True)
    json.dump(dict(keys=keys, chunk=CHUNK, n=len(keys)), open(f"{OUT}/index.json", "w"))
    print("cases", len(keys), "chunks", n_chunk)


if __name__ == "__main__":
    main()
