"""Experiment 2: AIS matching (STAGE_A_SPEC.md).

usage:
  python3 -I stage_a/match_ais.py scan [--max-days N] [--max-minutes M]
      download the needed AIS days one at a time (next day prefetched), keep rows whose
      normalised VesselName matches a needed name, write data/ais_hits/<day>.csv.gz,
      record the day in data/stage_a_state.json, delete the raw file.
  python3 -I stage_a/match_ais.py candidates
      for every incident whose two days are scanned, write tracks to data/tracks/ and
      one row per (incident, MMSI) to data/candidates.csv; data/match_status.csv lists
      every incident with its scan state and number of candidates.
"""
import gzip
import io
import json
import math
import os
import subprocess
import sys
import time
import zipfile
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from names import loose_match, norm_name  # noqa: E402

STATE = "data/stage_a_state.json"
HITS = "data/ais_hits"
TRACKS = "data/tracks"
RAWDIR = "data/raw/ais"
AUTO_REJECT_KM = 100
COLS = ["mmsi", "time", "lat", "lon", "sog", "cog", "heading", "name", "imo", "callsign",
        "type", "status", "length", "width", "draft", "cargo", "tclass"]
OLD = ["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading", "VesselName", "IMO", "CallSign",
       "VesselType", "Status", "Length", "Width", "Draft", "Cargo", "TransceiverClass"]
NEW = ["mmsi", "base_date_time", "latitude", "longitude", "sog", "cog", "heading", "vessel_name", "imo",
       "call_sign", "vessel_type", "status", "length", "width", "draft", "cargo", "transceiver"]


def url(d):
    if d.year <= 2024:
        return f"https://coast.noaa.gov/htdata/CMSP/AISDataHandler/{d.year}/AIS_{d:%Y_%m_%d}.zip"
    return f"https://noaaocm.blob.core.windows.net/ais/csv2/csv{d.year}/ais-{d:%Y-%m-%d}.csv.zst"


def raw_path(d):
    return os.path.join(RAWDIR, os.path.basename(url(d)))


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"days_done": [], "days_failed": {}}


def save_state(st):
    st["days_done"] = sorted(set(st["days_done"]))
    json.dump(st, open(STATE, "w"), indent=1)


def incidents():
    d = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False)
    d = d[d.name_norm.str.len() > 0].copy()
    day0 = d.time_utc.str[:10].where(d.time_utc.str.len() > 0, d.date_local)
    d["day0"] = pd.to_datetime(day0, errors="coerce").dt.date
    return d[d.day0.notna()]


def needed_by_day(inc):
    need = {}
    for nn, d0 in zip(inc.name_norm, inc.day0):
        for d in (d0 - timedelta(days=1), d0):
            if date(2015, 1, 1) <= d <= date(2025, 12, 31):
                need.setdefault(d, set()).add(nn)
    return need


# ---------------------------------------------------------------- scan
def start_download(d):
    os.makedirs(RAWDIR, exist_ok=True)
    out = raw_path(d)
    if os.path.exists(out):
        return None
    return subprocess.Popen(["bash", "-c", f'for a in 1 2 3; do curl -s -f -m 1500 -o "{out}.tmp" "{url(d)}" '
                             f'&& mv "{out}.tmp" "{out}" && exit 0; sleep 5; done; rm -f "{out}.tmp"; exit 1'])


def open_text(path):
    if path.endswith(".zip"):
        z = zipfile.ZipFile(path)
        name = [n for n in z.namelist() if n.endswith(".csv")][0]
        return io.TextIOWrapper(z.open(name), encoding="utf-8", errors="replace")
    import zstandard
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, "rb")),
                            encoding="utf-8", errors="replace")


def scan_day(d, names):
    path = raw_path(d)
    cache = {}
    names = set(names)
    kept, nrows = [], 0
    with open_text(path) as fh:
        for ch in pd.read_csv(fh, dtype=str, keep_default_na=False, chunksize=1_000_000, on_bad_lines="skip"):
            if "vessel_name" in ch.columns:
                ch = ch[[c for c in NEW if c in ch.columns]].rename(columns=dict(zip(NEW, COLS)))
            else:
                ch = ch[[c for c in OLD if c in ch.columns]].rename(columns=dict(zip(OLD, COLS)))
            nrows += len(ch)
            for u in ch["name"].unique():
                if u not in cache:
                    n = norm_name(u)
                    hit = n in names or (n and any(loose_match(x, n) for x in names))
                    cache[u] = hit
            m = ch["name"].map(cache).astype(bool)
            if m.any():
                kept.append(ch[m])
    out = pd.concat(kept) if kept else pd.DataFrame(columns=COLS)
    out = out.reindex(columns=COLS)
    out["time"] = out["time"].str.replace("T", " ")
    os.makedirs(HITS, exist_ok=True)
    out.to_csv(os.path.join(HITS, f"{d}.csv.gz"), index=False, compression="gzip")
    return nrows, len(out), out.mmsi.nunique()


def git_commit(msg):
    subprocess.run(["git", "add", STATE, HITS], check=False)
    r = subprocess.run(["git", "commit", "-q", "-m", msg], capture_output=True, text=True)
    if r.returncode == 0:
        subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], check=False)
        subprocess.run(["git", "push", "-q", "origin", "main"], check=False)


def scan(max_days, max_minutes):
    t0 = time.time()
    inc = incidents()
    need = needed_by_day(inc)
    st = load_state()
    done = set(st["days_done"])
    todo = [d for d in sorted(need) if str(d) not in done]
    print(f"needed days {len(need)}, done {len(done & set(map(str, need)))}, todo {len(todo)}", flush=True)
    todo = todo[:max_days]
    procs = {}
    if todo:
        procs[todo[0]] = start_download(todo[0])
    since_commit = 0
    for i, d in enumerate(todo):
        if i + 1 < len(todo) and (time.time() - t0) / 60 < max_minutes:
            procs[todo[i + 1]] = start_download(todo[i + 1])
        p = procs.pop(d, None)
        ok = p is None or p.wait() == 0
        if not ok or not os.path.exists(raw_path(d)):
            st["days_failed"][str(d)] = st["days_failed"].get(str(d), 0) + 1
            print(d, "download failed", flush=True)
            save_state(st)
            continue
        try:
            n, k, nm = scan_day(d, need[d])
        except Exception as e:  # corrupt download: drop it, retry another session
            st["days_failed"][str(d)] = st["days_failed"].get(str(d), 0) + 1
            print(d, "read failed", repr(e)[:200], flush=True)
            os.remove(raw_path(d))
            save_state(st)
            continue
        os.remove(raw_path(d))
        st["days_done"].append(str(d))
        st["days_failed"].pop(str(d), None)
        save_state(st)
        since_commit += 1
        print(f"{d} rows {n} kept {k} mmsi {nm} names {len(need[d])} [{(time.time() - t0) / 60:.1f} min]", flush=True)
        if since_commit >= 10:
            git_commit(f"Stage A exp. 2: AIS scan, {len(st['days_done'])} days done")
            since_commit = 0
        if (time.time() - t0) / 60 >= max_minutes:
            break
    for d, p in procs.items():  # stop a prefetch that is no longer needed
        if p:
            p.terminate()
        for f in (raw_path(d), raw_path(d) + ".tmp"):
            if os.path.exists(f):
                os.remove(f)
    if since_commit:
        git_commit(f"Stage A exp. 2: AIS scan, {len(st['days_done'])} days done")


# ---------------------------------------------------------------- candidates
def hav(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(min(1.0, a)))


def num(x):
    try:
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def mode(series):
    s = series[series.astype(str).str.len() > 0]
    return "" if s.empty else s.mode().iloc[0]


def candidates():
    inc = incidents()
    st = load_state()
    done = set(st["days_done"])
    os.makedirs(TRACKS, exist_ok=True)
    hits_cache = {}

    def hits(d):
        if d not in hits_cache:
            f = os.path.join(HITS, f"{d}.csv.gz")
            h = pd.read_csv(f, dtype=str, keep_default_na=False) if os.path.exists(f) else pd.DataFrame(columns=COLS)
            h["nn"] = h["name"].map(norm_name)
            hits_cache[d] = h
        return hits_cache[d]

    rows, status = [], []
    for _, r in inc.iterrows():
        days = [r.day0 - timedelta(days=1), r.day0]
        days = [d for d in days if date(2015, 1, 1) <= d <= date(2025, 12, 31)]
        scanned = all(str(d) in done for d in days)
        if not scanned:
            status.append(dict(incident_id=r.incident_id, scanned=False, n_candidates=""))
            continue
        h = pd.concat([hits(d) for d in days], ignore_index=True)
        nn = r.name_norm
        exact = h[h.nn == nn]
        loose = h[h.nn.map(lambda a: loose_match(nn, a))]
        lat0, lon0 = num(r.ref_lat), num(r.ref_lon)
        t_rep = pd.to_datetime(r.time_utc, errors="coerce") if r.time_utc else pd.NaT
        per = []
        for kind, sub in (("exact", exact), ("loose", loose)):
            for mmsi, g in sub.groupby("mmsi"):
                g = g.sort_values("time")
                g["la"], g["lo"] = pd.to_numeric(g.lat, errors="coerce"), pd.to_numeric(g.lon, errors="coerce")
                g = g[g.la.notna() & g.lo.notna()]
                if g.empty:
                    continue
                tr = g[["mmsi", "time", "lat", "lon", "sog", "cog", "heading", "name", "type", "length", "status"]]
                tr.to_csv(os.path.join(TRACKS, f"{r.incident_id}_{mmsi}.csv.gz"), index=False, compression="gzip")
                c = dict(incident_id=r.incident_id, mmsi=mmsi, match=kind, ais_name=mode(g["name"]),
                         n_positions=len(g), first_time=g.time.iloc[0], last_time=g.time.iloc[-1],
                         ais_type=mode(g["type"]), ais_length_m=mode(g["length"]), ais_imo=mode(g["imo"]))
                if lat0 is not None:
                    dist = [hav(lat0, lon0, a, b) for a, b in zip(g.la, g.lo)]
                    i = min(range(len(dist)), key=dist.__getitem__)
                    c.update(closest_km=round(dist[i], 2), closest_time=g.time.iloc[i])
                else:
                    c.update(closest_km=None, closest_time="")
                if pd.notna(t_rep):
                    tt = pd.to_datetime(g.time, errors="coerce")
                    gap = (tt - t_rep).abs()
                    j = gap.values.argmin()
                    c.update(near_report_time=g.time.iloc[j], near_report_gap_h=round(gap.iloc[j].total_seconds() / 3600, 2),
                             near_report_lat=g.la.iloc[j], near_report_lon=g.lo.iloc[j],
                             near_report_sog=g.sog.iloc[j],
                             dist_at_report_km=round(hav(lat0, lon0, g.la.iloc[j], g.lo.iloc[j]), 2) if lat0 is not None else None)
                per.append(c)
        for c in per:
            others = [o for o in per if o["mmsi"] != c["mmsi"] and o["match"] == "exact"]
            od = [o["closest_km"] for o in others if o.get("closest_km") is not None]
            L = num(r.length_ft)
            c.update(source=r.source, vessel_name=r.vessel_name, name_norm=nn, date_local=r.date_local,
                     time_utc=r.time_utc, state=r.state, ref_method=r.ref_method, ref_lat=r.ref_lat, ref_lon=r.ref_lon,
                     vessel_type_reported=r.vessel_type_reported,
                     length_reported_m=round(L * 0.3048, 1) if L else None,
                     n_other_same_name=len(others), others_min_closest_km=min(od) if od else None)
            rej = (r.ref_method in ("exact", "town", "town+offset") and c.get("closest_km") is not None
                   and c["closest_km"] > AUTO_REJECT_KM)
            c["auto_reject"] = "closest distance > 100 km" if rej else ""
            rows.append(c)
        status.append(dict(incident_id=r.incident_id, scanned=True, n_candidates=len(per)))
    first = ["incident_id", "mmsi", "match", "source", "vessel_name", "ais_name", "name_norm", "date_local", "time_utc",
             "state", "ref_method", "ref_lat", "ref_lon", "auto_reject"]
    out = pd.DataFrame(rows)
    if len(out):
        out = out[first + [c for c in out.columns if c not in first]]
    out.to_csv("data/candidates.csv", index=False)
    pd.DataFrame(status).to_csv("data/match_status.csv", index=False)
    print("candidates", len(out), "incidents scanned", sum(s["scanned"] for s in status), "of", len(status))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "scan":
        md = int(a[a.index("--max-days") + 1]) if "--max-days" in a else 10 ** 6
        mm = float(a[a.index("--max-minutes") + 1]) if "--max-minutes" in a else 150
        scan(md, mm)
    elif a and a[0] == "candidates":
        candidates()
    else:
        print(__doc__)
