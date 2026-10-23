"""GeoTrackNet addendum: AIS for the vessels of the matched sets, prepared for scoring.

usage: python3 -I gtn/score_prep.py --gpy <GeoTrackNet python> --gdir <GeoTrackNet dir> [--max-minutes M]
       [--only-test]
Runs ONLY after the OSF registration (ANALYSIS_PLAN_ADDENDUM_1.md, Order of work): refuses
to run while the addendum has no OSF link.

For every event of a region (data/gtn/regions.csv) and every scenario with an M4 set
(data/stage_b/matched/M4.csv.gz), collects the positions of the set's members inside the
region from T-27 h to T, one pass over the national AIS days (stage_b/aisday.py), and runs
gtn/score_seqs.py (GeoTrackNet Python) to cut them into the windows main (T-24 h..T),
early3 (T-27 h..T-3 h) and w6 (T-6 h..T) and apply the scoring preprocessing.
Writes data/gtn/score/<region>/<event>_<scenario>.npz and progress in data/gtn/score_state.json.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage_b"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aisday  # noqa: E402
from extract_train import read_day  # noqa: E402

STATE = "data/gtn/score_state.json"
RAW = "data/raw/gtn_score"


def osf_registered():
    return "osf.io/" in open("ANALYSIS_PLAN_ADDENDUM_1.md").read()


def jobs():
    reg = pd.read_csv("data/gtn/regions.csv")
    ev = pd.read_csv("data/stage_b/events.csv")
    m = pd.read_csv("data/stage_b/matched/M4.csv.gz")
    out = []
    for r in reg.itertuples():
        for e in map(int, r.event_ids.split(";")):
            row = ev[ev.event_id == e].iloc[0]
            for sc in ("real", "placebo30", "placebo60"):
                mm = m[(m.event_id == e) & (m.scenario == sc)]
                if mm.empty:
                    continue
                T = pd.Timestamp(row["T_" + sc])
                out.append(dict(region=r.region, event_id=e, scenario=sc, T=T, mmsi=sorted(set(mm.mmsi.astype(int))),
                                box=(r.lat_min, r.lat_max, r.lon_min, r.lon_max)))
    return out


def main():
    A = argparse.ArgumentParser()
    A.add_argument("--gpy", required=True)
    A.add_argument("--gdir", required=True)
    A.add_argument("--max-minutes", type=float, default=150)
    a = A.parse_args()
    if not osf_registered():
        sys.exit("refusing: ANALYSIS_PLAN_ADDENDUM_1.md has no OSF registration link yet")
    start = time.time()
    st = json.load(open(STATE)) if os.path.exists(STATE) else {"done": {}}
    todo = [j for j in jobs() if f"{j['region']}/{j['event_id']}_{j['scenario']}" not in st["done"]]
    todo.sort(key=lambda j: j["T"])
    print(len(todo), "event-scenarios to do", flush=True)
    cache = {}
    for j in todo:
        if (time.time() - start) / 60 > a.max_minutes:
            break
        key = f"{j['region']}/{j['event_id']}_{j['scenario']}"
        t0, t1 = j["T"] - pd.Timedelta(hours=27), j["T"]
        days = pd.date_range(t0.normalize(), (t1 - pd.Timedelta(seconds=1)).normalize(), freq="D")
        parts, missing = [], []
        for d in days:
            ds = d.strftime("%Y-%m-%d")
            if ds not in cache:
                for old in [k for k in cache if k < (t0 - pd.Timedelta(days=1)).strftime("%Y-%m-%d")]:
                    del cache[old]
                p = aisday.start_download(d.date())
                rc = 0 if p is None else p.wait()
                path = aisday.raw_path(d.date())
                if rc != 0 or not os.path.exists(path):
                    cache[ds] = None
                else:
                    a_ = read_day(path)
                    os.remove(path)
                    cache[ds] = a_ if len(a_) >= 1_000_000 else None
            if cache[ds] is None:
                missing.append(ds)
                continue
            x = cache[ds]
            lat0, lat1, lon0, lon1 = j["box"]
            sel = (np.isin(x[:, 8].astype(np.int64), j["mmsi"]) & (x[:, 0] >= lat0) & (x[:, 0] <= lat1)
                   & (x[:, 1] >= lon0) & (x[:, 1] <= lon1) & (x[:, 7] >= t0.timestamp()) & (x[:, 7] < t1.timestamp()))
            parts.append(x[sel])
        os.makedirs(RAW, exist_ok=True)
        rawf = f"{RAW}/{j['region']}_{j['event_id']}_{j['scenario']}.npz"
        np.savez(rawf, m=np.concatenate(parts) if parts else np.zeros((0, 9)), T=j["T"].timestamp())
        out = f"data/gtn/score/{key}.npz"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([a.gpy, "gtn/score_seqs.py", j["region"], rawf, out, a.gdir], check=True)
        os.remove(rawf)
        st["done"][key] = {"members": len(j["mmsi"]), "missing_days": missing}
        json.dump(st, open(STATE, "w"), indent=1)
        print(key, "done", flush=True)


if __name__ == "__main__":
    main()
