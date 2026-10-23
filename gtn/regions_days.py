"""GeoTrackNet addendum (ANALYSIS_PLAN_ADDENDUM_1.md): regions and training days.

usage: python3 -I gtn/regions_days.py
writes data/gtn/regions.csv, data/gtn/train_days.csv

Regions: 2 x 3 degree grid cells (floor(lat/2), floor(lon/3)) of the main-window centre of
the 197 events with an M4 set (true date, main sample); cells with at least 4 events; each
model region = cell + 0.5 degree on every side. Uses only the centre columns of the window
files and the matched-set list (no detector scores).

Training days: 4 per year 2015-2025, seed 20261022, drawn from all days of the year. A day is
not used for a region if it lies within 7 days of any incident in data/incidents.csv whose
reference point is inside that region.
"""
import glob
import os

import numpy as np
import pandas as pd

SEED = 20261022


def main():
    os.makedirs("data/gtn", exist_ok=True)
    ev = pd.read_csv("data/stage_b/events.csv")
    ev = ev[ev.main_exclude.astype(str).str.lower() != "true"]
    m = pd.read_csv("data/stage_b/matched/M4.csv.gz")
    ids = sorted(set(m[m.scenario == "real"].event_id) & set(ev.event_id))
    rows = []
    for e in ids:
        c = pd.read_csv(f"data/stage_b/windows/{e}_real.csv.gz", usecols=["centre_lat", "centre_lon"]).iloc[0]
        rows.append(dict(event_id=e, lat=c.centre_lat, lon=c.centre_lon,
                         cell=f"{int(np.floor(c.centre_lat / 2))}_{int(np.floor(c.centre_lon / 3))}"))
    cen = pd.DataFrame(rows)
    vc = cen.cell.value_counts()
    keep = vc[vc >= 4]
    reg = []
    for i, (cell, n) in enumerate(sorted(keep.items(), key=lambda kv: (-kv[1], kv[0]))):
        a, b = map(int, cell.split("_"))
        reg.append(dict(region=f"R{i + 1:02d}", cell=cell, n_events=int(n),
                        lat_min=2 * a - 0.5, lat_max=2 * a + 2.5, lon_min=3 * b - 0.5, lon_max=3 * b + 3.5,
                        event_ids=";".join(str(x) for x in sorted(cen[cen.cell == cell].event_id))))
    reg = pd.DataFrame(reg)
    reg.to_csv("data/gtn/regions.csv", index=False)
    print(reg[["region", "cell", "n_events", "lat_min", "lat_max", "lon_min", "lon_max"]].to_string(index=False))
    print("events covered:", reg.n_events.sum(), "of", len(cen))

    inc = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False)
    inc = inc[(inc.ref_lat != "") & (inc.ref_lon != "")]
    ilat, ilon = inc.ref_lat.astype(float).to_numpy(), inc.ref_lon.astype(float).to_numpy()
    idate = pd.to_datetime(inc.date_local).to_numpy()
    rng = np.random.default_rng(SEED)
    out = []
    for y in range(2015, 2026):
        days = pd.date_range(f"{y}-01-01", f"{y}-12-31", freq="D")
        pick = sorted(rng.choice(len(days), 4, replace=False))
        for p in pick:
            d = days[p]
            row = dict(day=d.strftime("%Y-%m-%d"))
            near = np.abs((idate - d.to_datetime64()) / np.timedelta64(1, "D")) <= 7
            for r in reg.itertuples():
                inside = (ilat >= r.lat_min) & (ilat <= r.lat_max) & (ilon >= r.lon_min) & (ilon <= r.lon_max)
                row[r.region] = int(not (near & inside).any())
            out.append(row)
    td = pd.DataFrame(out)
    td.to_csv("data/gtn/train_days.csv", index=False)
    print(len(td), "days; usable days per region:", td[reg.region].sum().to_dict())


if __name__ == "__main__":
    main()
