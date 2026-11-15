"""Independently timed incidents: T from NTSB reports (DEVIATIONS.md 10).

For the matched events whose accident the NTSB investigated, data/gap_checks/ntsb_times.csv
holds the accident time stated in the NTSB report (local time and zone, report number). This
check (1) compares that time with WAKE's T, and (2) sets T to the NTSB time, rebuilds the
windows with the unchanged stage_b/windows.py, rematches with the unchanged M4 rule and
recomputes the AUCs in the main and early3 windows. Fewer than 40 events were found, so the
results are descriptive (FOLLOWUP_PLAN_DRAFT.md section 2). Exploratory, after all results.

usage (from the repository root):
  python3 -I gap_checks/ntsb_time.py windows [--max-minutes M]   # downloads AIS, resumable
  python3 -I gap_checks/ntsb_time.py analyse
outputs: data/gap_checks/ntsb/ and results/gap_checks/ntsb_time.csv / .md
"""
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
D = os.path.join(ROOT, "data", "gap_checks", "ntsb")
EV = os.path.join(D, "events.csv")


def build_events():
    from zoneinfo import ZoneInfo
    ev = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "events.csv"), dtype={"mmsis": str, "imo": str})
    n = pd.read_csv(os.path.join(ROOT, "data", "gap_checks", "ntsb_times.csv"))
    n["ntsb_utc"] = [datetime.fromisoformat(f"{d} {t}").replace(tzinfo=ZoneInfo(z)).astimezone(ZoneInfo("UTC"))
                     .strftime("%Y-%m-%d %H:%M") for d, t, z in zip(n.ntsb_date_local, n.ntsb_time_local, n.tz)]
    keep = ev[ev.event_id.isin(n.event_id)].copy()
    t = n.set_index("event_id").ntsb_utc
    keep["T_wake"] = keep.T_real
    keep["T_real"] = keep.event_id.map(t)
    keep["T_utc"] = keep.T_real
    keep["T_rule"] = "ntsb_report_time"
    os.makedirs(D, exist_ok=True)
    keep.to_csv(EV, index=False)
    return keep


def windows(argv):
    import windows as W
    if not os.path.exists(EV):
        build_events()
    W.EVENTS = EV
    W.OUTDIR = os.path.join(D, "windows")
    W.STATE = os.path.join(D, "state.json")
    W.SCEN = ["real"]
    sys.argv = [sys.argv[0], "--no-git"] + argv
    W.main()


def lag_table(ev):
    ev = ev.assign(lag_h=(pd.to_datetime(ev.T_wake) - pd.to_datetime(ev.T_real)).dt.total_seconds() / 3600)
    L = ["WAKE T minus NTSB time (hours; positive = WAKE T after the NTSB time):\n",
         "| Event | Source | NTSB time (UTC) | WAKE T (UTC) | Hours |", "| --- | --- | --- | --- | --- |"]
    for r in ev.sort_values(["source", "event_id"]).itertuples():
        L.append(f"| {r.event_id} | {r.source} | {r.T_real} | {r.T_wake} | {r.lag_h:+.2f} |")
    for src, g in ev.groupby("source"):
        L.append(f"\n{src}: n {len(g)}, median {g.lag_h.median():+.2f} h, range {g.lag_h.min():+.2f} to {g.lag_h.max():+.2f}")
    return "\n".join(L) + "\n"


def analyse():
    import glob

    import analyse as A
    import match as M
    ev = pd.read_csv(EV)
    rows, sets = [], []
    for f in sorted(glob.glob(os.path.join(D, "windows", "*.csv.gz"))):
        d = pd.read_csv(f, usecols=M.COLS)
        d = M.add_logs(d[d.window == "main"])
        s, r = M.match_one(d, "M4")
        sets.append(dict(event_id=int(d.event_id.iloc[0]), status="matched" if s is not None else r))
        if s is not None:
            rows.append(s)
    noon = pd.concat(rows, ignore_index=True)
    noon.to_csv(os.path.join(D, "M4_ntsb.csv.gz"), index=False, compression={"method": "gzip", "mtime": 0})
    S = pd.DataFrame(sets)
    orig = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "matched", "M4.csv.gz"))
    orig = orig[(orig.scenario == "real") & orig.event_id.isin(ev.event_id)]
    w0 = A.load_windows()
    old_files = glob.glob(os.path.join(D, "windows", "*.csv.gz"))
    w1 = pd.concat([pd.read_csv(f, usecols=A.WCOLS) for f in old_files], ignore_index=True)
    w1["candidate_excluded"] = w1.candidate_excluded.astype(bool)
    w1["is_incident"] = w1.is_incident.astype(bool)
    both = set(orig.event_id) & set(noon.event_id)
    out = []
    for lab, mm, ww, ids in [("WAKE T (as analysed), all these events", orig, w0, set(orig.event_id)),
                             ("NTSB T, all sets matched at NTSB T", noon, w1, set(noon.event_id)),
                             ("WAKE T, events matched at both times", orig, w0, both),
                             ("NTSB T, events matched at both times", noon, w1, both)]:
        for window in ("main", "early3"):
            mem = A.members_for(mm[mm.event_id.isin(ids)], ww, window)
            for det in A.DET:
                r = A.auc_test(A.set_arrays(mem, det), perm=False)
                r.update(label=lab, window=window, detector=det)
                out.append(r)
    o = pd.DataFrame(out)
    o.to_csv(os.path.join(ROOT, "results", "gap_checks", "ntsb_time.csv"), index=False)
    L = ["# Independently timed incidents (NTSB)\n",
         f"Exploratory (DEVIATIONS.md 10). Generated by `gap_checks/ntsb_time.py`. "
         f"Events with an NTSB time: {len(ev)}; window files built at the NTSB time: {len(old_files)}; "
         f"matched there: {(S.status == 'matched').sum()} (at WAKE T: {orig.event_id.nunique()}; both: "
         f"{len(both)}).\n",
         lag_table(ev),
         f"NTSB-time sets not matched: {S[S.status != 'matched'].status.value_counts().to_dict()}\n",
         "| Timing | Window | Sets | " + " | ".join(A.DNAME[d] for d in A.DET) + " |",
         "| --- | --- | --- |" + " --- |" * len(A.DET)]
    for (lab, win), g in o.groupby(["label", "window"], sort=False):
        g = g.set_index("detector")
        L.append(f"| {lab} | {win} | {int(g.n_sets.iloc[0])} | " + " | ".join(
            f"{g.auc[d]:.3f} ({g.lo[d]:.3f}-{g.hi[d]:.3f})" for d in A.DET) + " |")
    open(os.path.join(ROOT, "results", "gap_checks", "ntsb_time.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    os.chdir(ROOT)
    {"windows": lambda: windows(sys.argv[2:]), "analyse": analyse}[sys.argv[1]]()
