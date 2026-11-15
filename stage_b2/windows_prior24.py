"""prior24 windows (ANALYSIS_PLAN_ADDENDUM_2.md, approved 15 Nov 2026).

prior24 = [T - 48 h, T - 24 h). Implemented by running the unchanged Stage B window code
(stage_b/windows.py) with T' = T - 24 h and keeping only its 24-hour window before T', which is
exactly [T - 48 h, T - 24 h). The fleet reference day is then the UTC day containing
T' - 12 h = T - 36 h, as the addendum requires. Only that one window is computed (SPAN and
WINDOWS are narrowed to it, so no other AIS days are downloaded); the detector code itself is
not changed. The box centre is the incident vessel's median position in prior24.

usage: python3 -I stage_b2/windows_prior24.py [real|placebo30|placebo60 ...] [--max-minutes M]
Events: those with an M4 set (main sample) for the scenario. Output:
data/stage_b2/prior24/windows/<event_id>_<scenario>.csv.gz (window name `main` = prior24) and
data/stage_b2/prior24/state.json.
"""
import os
import sys
from datetime import datetime, timedelta

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
import windows as W  # noqa: E402

D = os.path.join(ROOT, "data", "stage_b2", "prior24")


def build_events(scen):
    ev = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "events.csv"), dtype={"mmsis": str, "imo": str})
    ev = ev[ev.main_exclude.astype(str).str.lower() == "false"]
    s = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "matched", "sets.csv"))
    main = set(ev.event_id)
    keep_ids = {sc: set(s[(s.definition == "M4") & (s.scenario == sc) & (s.status == "matched")].event_id) & main
                for sc in scen}
    out = ev.copy()
    for sc in ["real", "placebo30", "placebo60"]:
        out[f"T_{sc}"] = [(datetime.strptime(t, "%Y-%m-%d %H:%M") - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M")
                          for t in out[f"T_{sc}"]]
    out = out[out.event_id.isin(set().union(*keep_ids.values()))]
    os.makedirs(D, exist_ok=True)
    out.to_csv(os.path.join(D, "events_shifted.csv"), index=False)
    return keep_ids


if __name__ == "__main__":
    os.chdir(ROOT)
    args = sys.argv[1:]
    scen = [a for a in args if a in ("real", "placebo30", "placebo60")] or ["real"]
    rest = [a for a in args if a not in scen]
    keep_ids = build_events(scen)
    W.EVENTS = os.path.join(D, "events_shifted.csv")
    W.OUTDIR = os.path.join(D, "windows")
    W.STATE = os.path.join(D, "state.json")
    W.SCEN = scen
    W.SPAN = (-24, 0)
    W.WINDOWS = {"main": (-24, 0)}
    # only event-scenarios that have an M4 set for that scenario
    orig = W.scenario_list
    W.scenario_list = lambda ev, st: [r for r in orig(ev, st) if r[2].event_id in keep_ids[r[3]]]
    sys.argv = [sys.argv[0], "--no-git"] + rest
    W.main()
