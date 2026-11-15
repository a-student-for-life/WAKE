"""Six-hour slices of the last day (ANALYSIS_PLAN_ADDENDUM_3.md, approved 15 Nov 2026).

Runs the unchanged Stage B window code (stage_b/windows.py) on the original T with
WINDOWS = main, s24 [T-24,T-18), s18 [T-18,T-12), s12 [T-12,T-6), s6 [T-6,T) and SPAN (-24, 0),
so only the AIS days of the main window are read. Detectors, fleet reference (UTC day containing
T - 12 h) and box centre (incident vessel's median position in the main window) are unchanged.
The main window is recomputed as a check against the published main-window values.

Events: the main-analysis events with an M4 set on the true date and an NRC report time
(T_rule nrc_time_utc or nrc_local_tz_from_ais). True date only.

usage: python3 -I stage_b3/windows_slices.py [--max-minutes M]   (from the repository root)
output: data/stage_b3/slices/windows/<event_id>_real.csv.gz and state.json
"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
import windows as W  # noqa: E402

D = os.path.join(ROOT, "data", "stage_b3", "slices")
NRC = ("nrc_time_utc", "nrc_local_tz_from_ais")


def build_events():
    ev = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "events.csv"), dtype={"mmsis": str, "imo": str})
    ev = ev[(ev.main_exclude.astype(str).str.lower() == "false") & ev.T_rule.isin(NRC)]
    s = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "matched", "sets.csv"))
    ok = set(s[(s.definition == "M4") & (s.scenario == "real") & (s.status == "matched")].event_id)
    ev = ev[ev.event_id.isin(ok)]
    os.makedirs(D, exist_ok=True)
    ev.to_csv(os.path.join(D, "events.csv"), index=False)
    return set(ev.event_id)


if __name__ == "__main__":
    os.chdir(ROOT)
    ids = build_events()
    print(len(ids), "events", flush=True)
    W.EVENTS = os.path.join(D, "events.csv")
    W.OUTDIR = os.path.join(D, "windows")
    W.STATE = os.path.join(D, "state.json")
    W.SCEN = ["real"]
    W.SPAN = (-24, 0)
    W.WINDOWS = {"main": (-24, 0), "s24": (-24, -18), "s18": (-18, -12), "s12": (-12, -6), "s6": (-6, 0)}
    sys.argv = [sys.argv[0], "--no-git"] + sys.argv[1:]
    W.main()
