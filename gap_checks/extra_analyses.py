"""Gap checks 2 and 3 (added 23 Oct 2026, after Stage B; DEVIATIONS.md #6).

usage: python3 -I gap_checks/extra_analyses.py
writes results/gap_checks/placebo_same_events.csv, placebo_paired_difference.csv, results/gap_checks/drop_timing.csv

2. Placebo on the same events. The placebo AUCs in results/stageB come from 120 and 119
   matched sets, the real-date AUC from 197, so the comparison mixes event sets. Here the
   real-date AUC is recomputed on exactly the events that also have a placebo set, with
   the same M4 sets, permutation test and bootstrap as stage_b/analyse.py.
3. When the largest speed drop happens (exploratory, descriptive). The main window is
   T-24 h to T and early3 is T-27 h to T-3 h, so a vessel whose main-window speed drop
   is larger than its early3 speed drop had its largest drop in the last 3 hours before
   T; likewise main vs w6 (largest drop in the last 6 hours when equal). Shares are
   given for incident vessels and their M4 controls (main sample, real date), overall
   and by incident type and source.
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
import analyse as A  # noqa: E402

OUT = os.path.join(ROOT, "results", "gap_checks")


def main():
    os.makedirs(OUT, exist_ok=True)
    ev = pd.read_csv(os.path.join(A.SB, "events.csv"))
    ev["main_exclude"] = ev.main_exclude.astype(str).str.lower() == "true"
    main_ids = set(ev.event_id[~ev.main_exclude])
    w = A.load_windows()
    M4 = pd.read_csv(os.path.join(A.SB, "matched", "M4.csv.gz"))

    def run(ids, scen, window="main"):
        mm = M4[(M4.scenario == scen) & M4.event_id.isin(ids)]
        mem = A.members_for(mm, w, window)
        rows = []
        for d in A.DET:
            r = A.auc_test(A.set_arrays(mem, d))
            r["detector"] = d
            rows.append(r)
        return pd.DataFrame(rows)

    have = {s: set(M4[M4.scenario == s].event_id) & main_ids
            for s in ["real", "placebo30", "placebo60"]}
    out = []
    for comp, ids in [("real & placebo30", have["real"] & have["placebo30"]),
                      ("real & placebo60", have["real"] & have["placebo60"]),
                      ("all three", have["real"] & have["placebo30"] & have["placebo60"])]:
        scens = ["real"] + [s for s in ["placebo30", "placebo60"] if s in comp or comp == "all three"]
        for s in scens:
            r = run(ids, s)
            r["events"], r["scenario"], r["comparison"] = len(ids), s, comp
            out.append(r)
    pl = pd.concat(out, ignore_index=True)
    pl.to_csv(os.path.join(OUT, "placebo_same_events.csv"), index=False)

    # paired difference real - placebo on the same events: bootstrap of events,
    # resampling each event's real and placebo set together
    diff = []
    for plc in ["placebo30", "placebo60"]:
        ids = have["real"] & have[plc]
        for d in A.DET:
            per = {}
            for sc in ["real", plc]:
                mem = A.members_for(M4[(M4.scenario == sc) & M4.event_id.isin(ids)], w, "main")
                for sid, wins, inc, n1 in A.set_arrays(mem, d):
                    per.setdefault(int(sid.split("_")[0]), {})[sc] = (wins[inc], n1)
            e = sorted(k for k, v in per.items() if len(v) == 2)
            wr = np.array([per[k]["real"][0] for k in e]); nr = np.array([per[k]["real"][1] for k in e], float)
            wp = np.array([per[k][plc][0] for k in e]); npl = np.array([per[k][plc][1] for k in e], float)
            obs = wr.sum() / nr.sum() - wp.sum() / npl.sum()
            rng = np.random.default_rng(A.SEED)
            idx = rng.integers(0, len(e), (A.NBOOT, len(e)))
            b = wr[idx].sum(1) / nr[idx].sum(1) - wp[idx].sum(1) / npl[idx].sum(1)
            lo, hi = np.percentile(b, [2.5, 97.5])
            diff.append(dict(placebo=plc, detector=d, events=len(e), auc_real=wr.sum() / nr.sum(),
                             auc_placebo=wp.sum() / npl.sum(), difference=obs, lo=lo, hi=hi,
                             share_boot_le0=(b <= 0).mean()))
    diff = pd.DataFrame(diff)
    diff.to_csv(os.path.join(OUT, "placebo_paired_difference.csv"), index=False)

    # ---- 3. timing of the largest speed drop
    mm = M4[(M4.scenario == "real") & M4.event_id.isin(main_ids)]
    piv = {}
    for win in ["main", "w6", "early3"]:
        x = A.members_for(mm, w, win)[["event_id", "mmsi", "role", "d1_speed_drop"]]
        piv[win] = x.rename(columns={"d1_speed_drop": win})
    t = piv["main"].merge(piv["w6"], on=["event_id", "mmsi", "role"]).merge(
        piv["early3"], on=["event_id", "mmsi", "role"])
    t = t.dropna(subset=["main"])
    t = t.merge(ev[["event_id", "incident_type", "source"]], on="event_id")
    t["last3h"] = t["main"] > t["early3"].fillna(-np.inf) + 1e-9
    t["last6h"] = np.isclose(t["main"], t["w6"].fillna(-np.inf))
    t["big_drop"] = t["main"] >= 5  # a fall of 5 knots or more within 10 minutes
    rows = []
    for grp, g in [("all", t)] + [(f"type: {k}", v) for k, v in t.groupby("incident_type")] + \
                  [(f"source: {k}", v) for k, v in t.groupby("source")]:
        for role in ["incident", "control"]:
            h = g[g.role == role]
            rows.append(dict(group=grp, role=role, vessels=len(h),
                             median_drop_kn=h["main"].median(),
                             share_drop_ge5kn=h.big_drop.mean(),
                             share_largest_drop_last6h=h.last6h.mean(),
                             share_largest_drop_last3h=h.last3h.mean(),
                             share_ge5kn_and_last3h=(h.big_drop & h.last3h).mean()))
    tm = pd.DataFrame(rows)
    tm.to_csv(os.path.join(OUT, "drop_timing.csv"), index=False)
    pd.set_option("display.width", 200)
    print(pl[["comparison", "scenario", "detector", "n_sets", "auc", "lo", "hi", "p"]].round(4).to_string(index=False))
    print(diff.round(4).to_string(index=False))
    print(tm.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
