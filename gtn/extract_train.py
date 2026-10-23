"""GeoTrackNet addendum: extract normal-traffic AIS messages for each region on its training days.

usage: python3 -I gtn/extract_train.py
reads  data/gtn/regions.csv, data/gtn/train_days.csv; national AIS days (stage_b/aisday.py hosts)
writes data/raw/gtn/<region>/<day>.npz (not committed): columns LAT, LON, SOG, COG, HEADING,
       ROT, NAV_STT, TIMESTAMP, MMSI (the authors' message layout), progress in
       data/gtn/extract_state.json

Cleaning as in stage_b/aisday.py (9-digit MMSI, valid positions, SOG >= 102.2 missing), plus
the status field: numeric codes kept; text mapped to AIS codes (moored 5, at anchor 1, ...).
A national day with fewer than 1,000,000 positions is skipped (DEVIATIONS.md #4). ROT is not
in the files and is set to 0 (GeoTrackNet does not use it).
"""
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pcsv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage_b"))
import aisday  # noqa: E402

OUT = "data/raw/gtn"
STATE = "data/gtn/extract_state.json"
OLD = {"MMSI": "mmsi", "BaseDateTime": "time", "LAT": "lat", "LON": "lon", "SOG": "sog",
       "COG": "cog", "Heading": "heading", "Status": "status"}
NEW = {"mmsi": "mmsi", "base_date_time": "time", "latitude": "lat", "longitude": "lon", "sog": "sog",
       "cog": "cog", "heading": "heading", "status": "status"}
TEXT = [("moored", 5), ("anchor", 1), ("not under command", 2), ("restricted", 3),
        ("constrained", 4), ("aground", 6), ("fishing", 7), ("sailing", 8), ("under way", 0)]


def status_code(arr):
    s = pc.utf8_lower(pc.utf8_trim_whitespace(pc.fill_null(arr, ""))).to_numpy(zero_copy_only=False)
    out = np.full(len(s), 15, np.int16)
    for i, v in enumerate(s):
        if v.isdigit():
            out[i] = int(v)
        elif v:
            for key, code in TEXT:
                if key in v:
                    out[i] = code
                    break
    return out


def read_day(path):
    h = aisday._stream(path)
    first = io.BufferedReader(h).readline().decode("utf-8", "replace").strip().lstrip("﻿")
    h.close()
    names = [c.strip() for c in first.split(",")]
    mp = OLD if "MMSI" in names else NEW
    types = {k: (pa.float64() if mp[k] in ("lat", "lon", "sog", "cog", "heading") else pa.string()) for k in mp}
    rd = pcsv.open_csv(aisday._stream(path), read_options=pcsv.ReadOptions(block_size=64 << 20),
                       parse_options=pcsv.ParseOptions(invalid_row_handler=lambda r: "skip"),
                       convert_options=pcsv.ConvertOptions(include_columns=list(mp), column_types=types,
                                                           strings_can_be_null=True))
    parts = []
    for batch in rd:
        b = {mp[k]: batch.column(k) for k in mp}
        ms = pc.utf8_trim_whitespace(b["mmsi"])
        ok9 = pc.fill_null(pc.and_(pc.equal(pc.utf8_length(ms), 9), pc.utf8_is_digit(ms)), False)
        mmsi = pc.cast(pc.if_else(ok9, ms, "0"), pa.int64()).to_numpy(zero_copy_only=False)
        ts = pc.replace_substring(pc.utf8_trim_whitespace(b["time"]), "T", " ")
        tt = pc.strptime(ts, format="%Y-%m-%d %H:%M:%S", unit="s", error_is_null=True)
        t = pc.cast(tt, pa.int64()).to_numpy(zero_copy_only=False)
        tv = pc.is_valid(tt).to_numpy(zero_copy_only=False)
        lat = b["lat"].to_numpy(zero_copy_only=False)
        lon = b["lon"].to_numpy(zero_copy_only=False)
        sog = b["sog"].to_numpy(zero_copy_only=False)
        cog = b["cog"].to_numpy(zero_copy_only=False)
        hd = b["heading"].to_numpy(zero_copy_only=False)
        with np.errstate(invalid="ignore"):
            keep = (ok9.to_numpy(zero_copy_only=False) & tv & np.isfinite(lat) & np.isfinite(lon)
                    & (np.abs(lat) <= 90) & (np.abs(lon) <= 180) & ~((lat == 0) & (lon == 0))
                    & np.isfinite(sog) & (sog < 102.2))
        st = status_code(b["status"].filter(pa.array(keep)))
        m = np.column_stack([lat[keep], lon[keep], sog[keep], np.nan_to_num(cog[keep], nan=0.0),
                             np.nan_to_num(hd[keep], nan=511.0), np.zeros(keep.sum()), st,
                             t[keep].astype(np.float64), mmsi[keep].astype(np.float64)])
        parts.append(m)
    a = np.concatenate(parts) if parts else np.zeros((0, 9))
    a = a[np.lexsort((a[:, 7], a[:, 8]))]
    dup = np.zeros(len(a), bool)
    dup[1:] = (a[1:, 8] == a[:-1, 8]) & (a[1:, 7] == a[:-1, 7])
    return a[~dup]


def main():
    reg = pd.read_csv("data/gtn/regions.csv")
    td = pd.read_csv("data/gtn/train_days.csv")
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"done": {}, "skipped": {}}
    days = [d for d in td.day if d not in st["done"] and d not in st["skipped"]]
    print(len(days), "days to do", flush=True)
    procs = {}
    for i, d in enumerate(days):
        dd = pd.Timestamp(d).date()
        for nd in days[i:i + 3]:
            if nd not in procs:
                procs[nd] = aisday.start_download(pd.Timestamp(nd).date())
        p = procs.pop(d)
        rc = 0 if p is None else p.wait()
        path = aisday.raw_path(dd)
        if rc != 0 or not os.path.exists(path):
            st["skipped"][d] = f"download failed rc={rc}"
            json.dump(st, open(STATE, "w"), indent=1)
            print(d, "skipped", rc, flush=True)
            continue
        t0 = time.time()
        a = read_day(path)
        os.remove(path)
        if len(a) < 1_000_000:
            st["skipped"][d] = f"national file has {len(a)} positions"
            json.dump(st, open(STATE, "w"), indent=1)
            continue
        row = td[td.day == d].iloc[0]
        counts = {}
        for r in reg.itertuples():
            if not int(row[r.region]):
                continue
            sel = (a[:, 0] >= r.lat_min) & (a[:, 0] <= r.lat_max) & (a[:, 1] >= r.lon_min) & (a[:, 1] <= r.lon_max)
            os.makedirs(f"{OUT}/{r.region}", exist_ok=True)
            np.savez_compressed(f"{OUT}/{r.region}/{d}.npz", m=a[sel].astype(np.float64))
            counts[r.region] = int(sel.sum())
        st["done"][d] = counts
        json.dump(st, open(STATE, "w"), indent=1)
        print(f"{d}: {len(a)} positions, {time.time() - t0:.0f}s, regions {counts}", flush=True)


if __name__ == "__main__":
    main()
