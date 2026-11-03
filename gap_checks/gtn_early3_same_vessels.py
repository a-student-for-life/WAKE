"""Exploratory (after all results were seen): does each detector keep its signal when the
window ends 3 hours before T, compared on identical vessels?

For each simple detector d (1-5), keep the members of the GeoTrackNet events' true-date M4
sets that are scored by d AND by GeoTrackNet in BOTH the main and the early3 window. On
these identical pairs, compute the pooled AUC of d and of GeoTrackNet in each window, the
drop (main minus early3) for each, and the difference of the drops (GeoTrackNet's drop minus
d's drop), with one bootstrap of sets shared by all four AUCs (5,000 resamples, seed
20261022). AUC, set rules and seed are those of stage_b/analyse.py, imported unchanged.

usage: python3 -I gap_checks/gtn_early3_same_vessels.py
Writes results/gap_checks/gtn_early3_same_vessels.csv
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
sys.path.insert(0, os.path.join(ROOT, "gtn"))
import analyse as sb  # noqa: E402
import analyse_gtn as ag  # noqa: E402

OUT = os.path.join(ROOT, "results", "gap_checks", "gtn_early3_same_vessels.csv")


def per_set(sets):
    return {s[0]: (s[1][s[2]], s[3]) for s in sets}


def main():
    regions = pd.read_csv(os.path.join(ag.G, "regions.csv"))
    ids = {int(e) for r in regions.itertuples() for e in r.event_ids.split(";")}
    m4 = pd.read_csv(os.path.join(ag.SB, "matched", "M4.csv.gz"))
    m4r = m4[(m4.scenario == "real") & m4.event_id.isin(ids)]
    scores = ag.load_scores()
    w = sb.load_windows()
    key = ["event_id", "scenario", "mmsi"]
    base = None
    for win in ["main", "early3"]:
        g = ag.gtn_members(m4, scores, ids, "real", win)[key + ["set_id", "role", ag.D7]]
        g = g.rename(columns={ag.D7: f"g_{win}"})
        s = sb.members_for(m4r, w, win)[key + sb.DET]
        s = s.rename(columns={d: f"{d}_{win}" for d in sb.DET})
        x = g.merge(s, on=key, how="left")
        base = x if base is None else base.merge(x.drop(columns=["set_id", "role"]), on=key)
    rows = []
    for d in sb.DET:
        cols = [f"{d}_main", f"{d}_early3", "g_main", "g_early3"]
        both = base.dropna(subset=cols)
        arr = {c: per_set(sb.set_arrays(both, c)) for c in cols}
        sids = sorted(set.intersection(*[set(a) for a in arr.values()]))
        W = {c: np.array([arr[c][s][0] for s in sids], float) for c in cols}
        N = np.array([arr[cols[0]][s][1] for s in sids], float)
        auc = {c: W[c].sum() / N.sum() for c in cols}
        rng = np.random.default_rng(sb.SEED)
        idx = rng.integers(0, len(sids), (sb.NBOOT, len(sids)))
        B = {c: W[c][idx].sum(1) / N[idx].sum(1) for c in cols}
        drop_d = B[f"{d}_main"] - B[f"{d}_early3"]
        drop_g = B["g_main"] - B["g_early3"]
        q = lambda v: np.percentile(v, [2.5, 97.5])  # noqa: E731
        rows.append(dict(
            detector=d, n_sets=len(sids), n_pairs=int(N.sum()),
            auc_det_main=auc[f"{d}_main"], auc_det_early3=auc[f"{d}_early3"],
            auc_gtn_main=auc["g_main"], auc_gtn_early3=auc["g_early3"],
            drop_det=auc[f"{d}_main"] - auc[f"{d}_early3"],
            drop_det_lo=q(drop_d)[0], drop_det_hi=q(drop_d)[1],
            drop_gtn=auc["g_main"] - auc["g_early3"],
            drop_gtn_lo=q(drop_g)[0], drop_gtn_hi=q(drop_g)[1],
            gtn_minus_det_early3=auc["g_early3"] - auc[f"{d}_early3"],
            gtn_minus_det_early3_lo=q(B["g_early3"] - B[f"{d}_early3"])[0],
            gtn_minus_det_early3_hi=q(B["g_early3"] - B[f"{d}_early3"])[1],
            drop_diff=(auc["g_main"] - auc["g_early3"]) - (auc[f"{d}_main"] - auc[f"{d}_early3"]),
            drop_diff_lo=q(drop_g - drop_d)[0], drop_diff_hi=q(drop_g - drop_d)[1]))
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    pd.set_option("display.width", 250)
    print(out.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
