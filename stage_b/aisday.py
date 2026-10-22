"""Read one Marine Cadastre AIS day into compact numpy arrays (STAGE_B_SPEC.md B2).

Read in chunks with pyarrow's streaming CSV reader; only the needed columns are kept, as
int32 / float32. Cleaning (spec B2): SOG >= 102.2 -> missing, positions outside lat
-90..90 / lon -180..180 or at 0,0 dropped, MMSIs that are not 9 digits dropped, exact
duplicate (MMSI, time) rows dropped. Output sorted by MMSI, then time.
"""
import io
import os
import subprocess
import zipfile

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pcsv

RAWDIR = "data/raw/ais"
EPOCH0 = np.datetime64("1970-01-01T00:00:00", "s")

OLD = {"MMSI": "mmsi", "BaseDateTime": "time", "LAT": "lat", "LON": "lon", "SOG": "sog",
       "COG": "cog", "IMO": "imo", "VesselType": "type", "Length": "length"}
NEW = {"mmsi": "mmsi", "base_date_time": "time", "latitude": "lat", "longitude": "lon", "sog": "sog",
       "cog": "cog", "imo": "imo", "vessel_type": "type", "length": "length"}
FIELDS = ["mmsi", "t", "lat", "lon", "sog", "cog", "type", "length", "imo"]


def url(d):
    # same hosts as stage_a/match_ais.py (2024 zips moved to the blob host)
    if d.year <= 2023:
        return f"https://coast.noaa.gov/htdata/CMSP/AISDataHandler/{d.year}/AIS_{d:%Y_%m_%d}.zip"
    return f"https://noaaocm.blob.core.windows.net/ais/csv2/csv{d.year}/ais-{d:%Y-%m-%d}.csv.zst"


def raw_path(d):
    return os.path.join(RAWDIR, os.path.basename(url(d)))


def start_download(d):
    """Background download; returns Popen. Exit code 22 from curl -f means HTTP error (404)."""
    os.makedirs(RAWDIR, exist_ok=True)
    out = raw_path(d)
    if os.path.exists(out):
        return None
    cmd = (f'for a in 1 2 3; do curl -s -f -m 1500 -o "{out}.tmp" "{url(d)}"; rc=$?; '
           f'if [ $rc -eq 0 ]; then mv "{out}.tmp" "{out}"; exit 0; fi; '
           f'if [ $rc -eq 22 ]; then code=$(curl -s -o /dev/null -w "%{{http_code}}" -I "{url(d)}"); '
           f'if [ "$code" = "404" ]; then rm -f "{out}.tmp"; exit 44; fi; fi; sleep 5; done; '
           f'rm -f "{out}.tmp"; exit 1')
    return subprocess.Popen(["bash", "-c", cmd])


def _stream(path):
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.endswith(".csv")][0]
        return z.open(name)
    import zstandard
    return zstandard.ZstdDecompressor().stream_reader(open(path, "rb"))


def read_day(path):
    # detect the format from the header
    h = _stream(path)
    first = io.BufferedReader(h).readline().decode("utf-8", "replace").strip().lstrip("﻿")
    h.close()
    f = _stream(path)
    names = [c.strip() for c in first.split(",")]
    mp = OLD if "MMSI" in names else NEW
    types = {k: pa.string() for k in mp}
    for k in mp:
        if mp[k] in ("lat", "lon", "sog", "cog", "length"):
            types[k] = pa.float64()
    conv = pcsv.ConvertOptions(include_columns=list(mp), column_types=types,
                               strings_can_be_null=True)
    rd = pcsv.open_csv(f, read_options=pcsv.ReadOptions(block_size=64 << 20),
                       parse_options=pcsv.ParseOptions(invalid_row_handler=lambda r: "skip"),
                       convert_options=conv)
    parts = {k: [] for k in FIELDS}
    for batch in rd:
        b = {mp[k]: batch.column(k) for k in mp}
        ms = pc.utf8_trim_whitespace(b["mmsi"])
        ok9 = pc.and_(pc.equal(pc.utf8_length(ms), 9), pc.utf8_is_digit(ms))
        ok9 = pc.fill_null(ok9, False)
        ms = pc.if_else(ok9, ms, "0")
        mmsi = pc.cast(ms, pa.int64()).to_numpy(zero_copy_only=False)
        ts = pc.replace_substring(pc.utf8_trim_whitespace(b["time"]), "T", " ")
        tt = pc.strptime(ts, format="%Y-%m-%d %H:%M:%S", unit="s", error_is_null=True)
        t = pc.cast(tt, pa.int64()).to_numpy(zero_copy_only=False)
        tvalid = pc.is_valid(tt).to_numpy(zero_copy_only=False)
        lat = b["lat"].to_numpy(zero_copy_only=False)
        lon = b["lon"].to_numpy(zero_copy_only=False)
        sog = b["sog"].to_numpy(zero_copy_only=False).astype(np.float32)
        cog = b["cog"].to_numpy(zero_copy_only=False).astype(np.float32)
        ln = b["length"].to_numpy(zero_copy_only=False).astype(np.float32)
        ty = pc.cast(pc.utf8_trim_whitespace(pc.fill_null(b["type"], "")), pa.string())
        tyd = pc.fill_null(pc.utf8_is_digit(ty), False)
        ty = pc.if_else(pc.and_(tyd, pc.less_equal(pc.utf8_length(ty), 4)), ty, "-1")
        ty = pc.cast(ty, pa.int32()).to_numpy(zero_copy_only=False)
        im = pc.utf8_trim_whitespace(pc.fill_null(b["imo"], ""))
        im = pc.replace_substring(im, "IMO", "")
        imd = pc.and_(pc.utf8_is_digit(im), pc.less_equal(pc.utf8_length(im), 9))
        im = pc.if_else(pc.fill_null(imd, False), im, "0")
        im = pc.cast(im, pa.int64()).to_numpy(zero_copy_only=False)
        with np.errstate(invalid="ignore"):
            keep = (ok9.to_numpy(zero_copy_only=False) & tvalid & np.isfinite(lat) & np.isfinite(lon)
                    & (lat >= -90) & (lat <= 90) & (lon >= -180) & (lon <= 180) & ~((lat == 0) & (lon == 0)))
            sog = np.where(sog >= 102.2, np.nan, sog).astype(np.float32)
        parts["mmsi"].append(mmsi[keep].astype(np.int32))
        parts["t"].append(t[keep].astype(np.int64))
        parts["lat"].append(lat[keep].astype(np.float32))
        parts["lon"].append(lon[keep].astype(np.float32))
        parts["sog"].append(sog[keep])
        parts["cog"].append(cog[keep])
        parts["type"].append(ty[keep].astype(np.int16))
        parts["length"].append(ln[keep])
        parts["imo"].append(np.clip(im[keep], 0, 2**31 - 1).astype(np.int32))
    f.close()
    d = {k: np.concatenate(v) if v else np.array([]) for k, v in parts.items()}
    o = np.lexsort((d["t"], d["mmsi"]))
    d = {k: v[o] for k, v in d.items()}
    dup = np.zeros(len(o), bool)
    dup[1:] = (d["mmsi"][1:] == d["mmsi"][:-1]) & (d["t"][1:] == d["t"][:-1])
    return {k: v[~dup] for k, v in d.items()}
