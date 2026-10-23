"""Gap check 1: main test with the unsure cases added back (plan section 8).

usage: python3 -I gap_checks/unsure_check.py
reads  data/gap_checks/unsure_events.csv, data/gap_checks/windows/, and the Stage B
       inputs; writes data/gap_checks/unsure_M4.csv.gz, unsure_sets.csv and
       results/gap_checks/unsure_added_back.csv
M4 sets for the new events are built with stage_b/match.py's match_one, unchanged; the
AUC, permutation p and bootstrap come from stage_b/analyse.py, unchanged.
"""
import glob
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
import analyse as A  # noqa: E402
import match  # noqa: E402

GD = os.path.join(ROOT, "data", "gap_checks")
OUT = os.path.join(ROOT, "results", "gap_checks")


def main():
    ue = pd.read_csv(os.path.join(GD, "unsure_events.csv"))
    ue["main_exclude"] = ue.main_exclude.astype(str).str.lower() == "true"
    sets, rows, wins = [], [], []
    for f in sorted(glob.glob(os.path.join(GD, "windows", "*.csv.gz"))):
        full = pd.read_csv(f, usecols=A.WCOLS + ["hours", "type_group", "length_m"])
        full["candidate_excluded"] = full.candidate_excluded.astype(bool)
        full["is_incident"] = full.is_incident.astype(bool)
        wins.append(full[A.WCOLS])
        d = match.add_logs(full[full.window == "main"][match.COLS].copy())
        e = int(d.event_id.iloc[0])
        s, r = match.match_one(d, "M4")
        sets.append(dict(event_id=e, status="matched" if s is not None else r,
                         n_controls=r if s is not None else 0))
        if s is not None:
            rows.append(s)
    S = pd.DataFrame(sets).merge(ue[["event_id", "incident_id", "main_exclude"]], on="event_id")
    S.to_csv(os.path.join(GD, "unsure_sets.csv"), index=False)
    um = pd.concat(rows, ignore_index=True)
    um.to_csv(os.path.join(GD, "unsure_M4.csv.gz"), index=False,
              compression={"method": "gzip", "mtime": 0})

    ev = pd.read_csv(os.path.join(A.SB, "events.csv"))
    ev["main_exclude"] = ev.main_exclude.astype(str).str.lower() == "true"
    main_ids = set(ev.event_id[~ev.main_exclude])
    add_ids = set(ue.event_id[~ue.main_exclude])
    w = pd.concat([A.load_windows(), pd.concat(wins, ignore_index=True)], ignore_index=True)
    M4 = pd.concat([pd.read_csv(os.path.join(A.SB, "matched", "M4.csv.gz")), um],
                   ignore_index=True)
    out = []
    for label, ids in [("Main (M4, main sample)", main_ids),
                       ("Unsure cases added back", main_ids | add_ids)]:
        mm = M4[(M4.scenario == "real") & M4.event_id.isin(ids)]
        mem = A.members_for(mm, w, "main")
        for d in A.DET:
            r = A.auc_test(A.set_arrays(mem, d))
            r.update(detector=d, label=label, events=len(ids))
            out.append(r)
    res = pd.DataFrame(out)
    res.to_csv(os.path.join(OUT, "unsure_added_back.csv"), index=False)
    print(S.to_string(index=False))
    print(res[["label", "detector", "events", "n_sets", "auc", "lo", "hi", "p"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
