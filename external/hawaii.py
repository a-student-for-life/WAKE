"""External check on HawaiiCoast_GT (external/HAWAII_PLAN.md).

usage (from the repository root; HAWAII = folder holding the unzipped HawaiiCoast_GT/):
  python3 -I external/hawaii.py events  HAWAII     # event table
  python3 -I external/hawaii.py days    HAWAII     # daily files in Marine Cadastre layout
  python3 -I external/hawaii.py windows HAWAII     # unchanged Stage B window code
  python3 -I external/hawaii.py analyse HAWAII     # M4 matching and tests
outputs: data/external/hawaii/ and results/external/hawaii.md, hawaii_tests.csv
"""
import glob
import os
import sys
import zipfile
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
D = os.path.join(ROOT, "data", "external", "hawaii")
HST = "Pacific/Honolulu"


def src(h):
    return os.path.join(h, "HawaiiCoast_GT")


def events(h):
    from zoneinfo import ZoneInfo
    x = pd.read_csv(os.path.join(src(h), "incident_data", "hawaii_primary_trajectories_of_interest_2017_2020.csv"))
    x = x[x.report_vessel_role.fillna("") != "Helper vessel"].copy()
    T = []
    for r in x.itertuples():
        if isinstance(r.report_incident_time_of_interest_hst, str) and r.report_incident_time_of_interest_hst:
            t = pd.Timestamp(r.report_incident_time_of_interest_hst).tz_convert("UTC")
            rule = "report_time"
        elif isinstance(r.report_start_date_of_interest_hst, str) and r.report_start_date_of_interest_hst:
            t = pd.Timestamp(r.report_start_date_of_interest_hst[:10] + " 00:00").tz_localize(HST).tz_convert("UTC")
            rule = "midnight_hst"
        else:
            t, rule = None, "none"
        T.append((t, rule))
    x["T"] = [a for a, _ in T]
    x["T_rule"] = [b for _, b in T]
    x = x[x["T"].notna()].sort_values(["MMSI", "T"])
    keep, last = [], {}
    for r in x.itertuples():
        if r.MMSI in last and (r.T - last[r.MMSI]) <= pd.Timedelta(days=3):
            continue
        last[r.MMSI] = r.T
        keep.append(r.Index)
    x = x.loc[keep].sort_values("T").reset_index(drop=True)
    e = pd.DataFrame({
        "event_id": np.arange(1, len(x) + 1), "mmsi": x.MMSI.astype(str), "mmsis": x.MMSI.astype(str),
        "imo": "", "incident_id": "H" + x.incident_num.astype(str), "incident_ids": "H" + x.incident_num.astype(str),
        "n_reports": 1, "T_rule": x.T_rule, "tz_used": HST, "source": "HawaiiCoast_GT",
        "sources": "HawaiiCoast_GT", "setting": "sea", "incident_type": x.ais_incident_type.fillna(""),
        "main_exclude": False, "main_exclude_any": False, "first_pass_both_yes": True,
        "ref_lat": np.nan, "ref_lon": np.nan, "ref_source": "none",
        "evidence": x.ais_incident_evidence.fillna(""), "vessel_class": x.vessel_class_from_ais.fillna(""),
    })
    t = x["T"].dt.strftime("%Y-%m-%d %H:%M")
    e["T_utc"] = t.values
    e["T_real"] = t.values
    e["T_placebo30"] = (x["T"] - pd.Timedelta(days=30)).dt.strftime("%Y-%m-%d %H:%M").values
    e["T_placebo60"] = (x["T"] - pd.Timedelta(days=60)).dt.strftime("%Y-%m-%d %H:%M").values
    os.makedirs(D, exist_ok=True)
    e.to_csv(os.path.join(D, "events.csv"), index=False)
    # all incident vessels (helpers included) for the control exclusion
    a = pd.read_csv(os.path.join(src(h), "incident_data", "hawaii_primary_trajectories_of_interest_2017_2020.csv"))
    a["day"] = a.report_start_date_of_interest_hst.fillna(a.ais_incident_start_bound_hst.str[:10])
    a[["MMSI", "day"]].dropna().to_csv(os.path.join(D, "incident_vessels.csv"), index=False)
    print(len(e), "events;", e.T_rule.value_counts().to_dict(), e.vessel_class.value_counts().head(6).to_dict())


def needed_days():
    e = pd.read_csv(os.path.join(D, "events.csv"))
    days = set()
    for col in ("T_real", "T_placebo30"):
        for t in e[col]:
            T = datetime.strptime(t, "%Y-%m-%d %H:%M")
            d = (T - timedelta(hours=48)).date()
            while d <= (T + timedelta(hours=12)).date():
                days.add(d)
                d += timedelta(days=1)
    return sorted(days)


def day_path(d):
    return os.path.join(D, "days", f"AIS_{d:%Y_%m_%d}.zip")


def days(h):
    import pyarrow.csv as pcsv
    os.makedirs(os.path.join(D, "days"), exist_ok=True)
    need = needed_days()
    months = sorted({(d.year, d.month) for d in need})
    cols = {"MMSI": "MMSI", "datetime_utc": "BaseDateTime", "lat": "LAT", "lon": "LON",
            "speed_over_ground_knots": "SOG", "course_over_ground_deg": "COG", "imo_number": "IMO",
            "vessel_type_code": "VesselType", "length_m": "Length"}
    zf = zipfile.ZipFile(os.path.join(h, "HawaiiCoast_GT.zip"))
    have = set(zf.namelist())
    for y, m in months:
        if f"HawaiiCoast_GT/AIS_data/Hawaii_{y}_{m:02d}.csv" not in have:
            continue  # outside 2017-2020: those days stay missing
        todo = [d for d in need if (d.year, d.month) == (y, m) and not os.path.exists(day_path(d))]
        if not todo:
            continue
        with zf.open(f"HawaiiCoast_GT/AIS_data/Hawaii_{y}_{m:02d}.csv") as f:
            import pyarrow as pa
            t = pcsv.read_csv(f, convert_options=pcsv.ConvertOptions(
                include_columns=list(cols), column_types={"datetime_utc": pa.string(), "imo_number": pa.string()}))
        df = t.to_pandas().rename(columns=cols)
        df["VesselType"] = pd.to_numeric(df.VesselType, errors="coerce").astype("Int64")
        df["day"] = df.BaseDateTime.str[:10]
        df["BaseDateTime"] = df.BaseDateTime.str[:19].str.replace(" ", "T")
        for d in todo:
            g = df[df.day == f"{d:%Y-%m-%d}"].drop(columns="day")
            with zipfile.ZipFile(day_path(d), "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(f"AIS_{d:%Y_%m_%d}.csv", g.to_csv(index=False))
        print(y, m, len(todo), "days", flush=True)
        del df, t


def patch(W):
    import aisday
    aisday.raw_path = day_path
    aisday.start_download = lambda d: None if os.path.exists(day_path(d)) else _missing()
    W.MIN_DAY_POS = 10_000
    W.EVENTS = os.path.join(D, "events.csv")
    W.OUTDIR = os.path.join(D, "windows")
    W.STATE = os.path.join(D, "state.json")
    W.SCEN = ["real", "placebo30"]
    iv = pd.read_csv(os.path.join(D, "incident_vessels.csv"))
    ts = np.array([datetime.strptime(x[:10], "%Y-%m-%d").timestamp() for x in iv.day])
    W.candidate_lists = lambda: (ts, iv.MMSI.astype(np.int64).to_numpy(), np.zeros(len(iv), np.int64))
    # raw files are the rebuilt day files: never delete them after reading
    os_remove = os.remove
    W.os.remove = lambda p: None if p.startswith(os.path.join(D, "days")) else os_remove(p)


class _P:
    def wait(self):
        return 44


def _missing():
    return _P()


def windows(h):
    import windows as W
    patch(W)
    sys.argv = [sys.argv[0], "--no-git", "--max-minutes", "600"]
    W.main()


def analyse(h):
    import analyse as A
    import match as M
    files = sorted(glob.glob(os.path.join(D, "windows", "*.csv.gz")))
    rows = {}
    for f in files:
        d = pd.read_csv(f, usecols=M.COLS)
        d = M.add_logs(d[d.window == "main"])
        s, r = M.match_one(d, "M4")
        if s is not None:
            rows.setdefault(d.scenario.iloc[0], []).append(s)
    m4 = pd.concat([pd.concat(v) for v in rows.values()], ignore_index=True)
    m4.to_csv(os.path.join(D, "M4.csv.gz"), index=False, compression={"method": "gzip", "mtime": 0})
    w = pd.concat([pd.read_csv(f, usecols=A.WCOLS) for f in files], ignore_index=True)
    w["candidate_excluded"] = w.candidate_excluded.astype(bool)
    w["is_incident"] = w.is_incident.astype(bool)
    ev = pd.read_csv(os.path.join(D, "events.csv"))
    out = []
    for sc, win, perm in [("real", "main", True), ("real", "early3", False), ("placebo30", "main", True)]:
        mm = m4[m4.scenario == sc]
        mem = A.members_for(mm, w[w.scenario == sc], win)
        res = []
        for d in A.DET:
            r = A.auc_test(A.set_arrays(mem, d), perm=perm)
            r.update(scenario=sc, window=win, detector=d)
            res.append(r)
        res = pd.DataFrame(res)
        if sc == "real" and win == "main":
            res["p_holm"] = A.holm(res.p.to_numpy())
        out.append(res)
    o = pd.concat(out, ignore_index=True)
    os.makedirs(os.path.join(ROOT, "results", "external"), exist_ok=True)
    o.to_csv(os.path.join(ROOT, "results", "external", "hawaii_tests.csv"), index=False)
    real = m4[m4.scenario == "real"]
    ids = set(real.event_id)
    L = ["# External check: HawaiiCoast_GT (external/HAWAII_PLAN.md)\n",
         f"Events {len(ev)} (T rule: {ev.T_rule.value_counts().to_dict()}); window files {len(files)}; "
         f"M4 sets on the true date {len(ids)} (placebo30 {m4[m4.scenario == 'placebo30'].event_id.nunique()}).\n",
         f"Vessel class of matched events: {ev[ev.event_id.isin(ids)].vessel_class.value_counts().to_dict()}\n",
         f"AIS evidence of matched events: {ev[ev.event_id.isin(ids)].evidence.value_counts().to_dict()}\n",
         "| Scenario | Window | Detector | Sets | Pairs | AUC | 95% interval | Perm. p | Holm p |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in o.itertuples():
        L.append(f"| {r.scenario} | {r.window} | {A.DNAME[r.detector]} | {r.n_sets} | {r.n_pairs} | {r.auc:.3f} | "
                 f"{r.lo:.3f}-{r.hi:.3f} | {'' if pd.isna(r.p) else f'{r.p:.4f}'} | "
                 f"{'' if pd.isna(getattr(r, 'p_holm', np.nan)) else f'{r.p_holm:.4f}'} |")
    open(os.path.join(ROOT, "results", "external", "hawaii.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    os.chdir(ROOT)
    {"events": events, "days": days, "windows": windows, "analyse": analyse}[sys.argv[1]](sys.argv[2])
