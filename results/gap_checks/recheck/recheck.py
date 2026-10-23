"""Independent recheck of WAKE stage B headline numbers (written from the method description only)."""
import glob, os, sys
import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

ROOT = "/home/claude/wake/data/stage_b"
DETS = ["d1_speed_drop", "d2_loiter_h", "d3_gap_ratio", "d4_off_lane", "d5_iforest"]
NPERM, NBOOT, SEED = 10_000, 5_000, 20261022

def tobool(s):
    return s.astype(str).str.strip().str.lower().map({"true": True, "false": False, "1": True, "0": False})

ev = pd.read_csv(f"{ROOT}/events.csv")
ev["main_exclude_b"] = tobool(ev["main_exclude"])
assert ev["main_exclude_b"].notna().all()
main_ids = set(ev.loc[~ev["main_exclude_b"], "event_id"])
print("main-sample events:", len(main_ids), "(total events:", len(ev), ")")

m4 = pd.read_csv(f"{ROOT}/matched/M4.csv.gz")
m4 = m4[m4["event_id"].isin(main_ids)].copy()

# load all windows files
parts = [pd.read_csv(f) for f in sorted(glob.glob(f"{ROOT}/windows/*.csv.gz"))]
W = pd.concat(parts, ignore_index=True)
W["is_incident_b"] = tobool(W["is_incident"])
dup = W.duplicated(["event_id", "scenario", "mmsi", "window"], keep=False)
print("duplicate (event,scenario,mmsi,window) rows in windows:", int(dup.sum()))
dupm = m4.duplicated(["event_id", "scenario", "mmsi"], keep=False)
print("duplicate (event,scenario,mmsi) rows in M4 (main sample):", int(dupm.sum()))

for scen in ["real", "placebo30", "placebo60"]:
    s = m4[m4.scenario == scen]
    g = s.groupby("event_id")
    ninc = g["role"].apply(lambda r: (r == "incident").sum())
    nctl = g["role"].apply(lambda r: (r == "control").sum())
    print(f"[{scen}] sets in main sample: {g.ngroups}; sets with !=1 incident: {(ninc != 1).sum()}; "
          f"controls per set min/max: {nctl.min()}/{nctl.max()}")

# incident consistency (main window)
for scen in ["real", "placebo30", "placebo60"]:
    inc = m4[(m4.scenario == scen) & (m4.role == "incident")][["event_id", "scenario", "mmsi"]]
    wm = W[(W.window == "main") & (W.scenario == scen)]
    j = inc.merge(wm[["event_id", "scenario", "mmsi", "is_incident_b"]], how="left", on=["event_id", "scenario", "mmsi"])
    miss = j["is_incident_b"].isna().sum()
    notinc = (j["is_incident_b"] == False).sum()
    # windows incident flagged rows whose mmsi differs from M4 incident
    winc = wm[wm.is_incident_b][["event_id", "mmsi"]].rename(columns={"mmsi": "w_mmsi"})
    jj = inc.merge(winc, on="event_id", how="left")
    mism = (jj["w_mmsi"].notna() & (jj["w_mmsi"] != jj["mmsi"])).sum()
    nflag = winc.groupby("event_id").size()
    print(f"[{scen}] M4 incident rows missing from windows(main): {miss}; is_incident False: {notinc}; "
          f"windows incident mmsi != M4 incident mmsi: {mism}; events with >1 is_incident in windows: {(nflag > 1).sum()}")
    # control members missing from windows
    allm = m4[m4.scenario == scen].merge(wm[["event_id", "scenario", "mmsi"]], how="left",
                                         on=["event_id", "scenario", "mmsi"], indicator=True)
    print(f"[{scen}] M4 members (any role) missing from windows(main): {(allm['_merge'] == 'left_only').sum()}")


def build_sets(scen, window, det):
    s = m4[m4.scenario == scen][["event_id", "scenario", "mmsi", "role"]]
    w = W[(W.scenario == scen) & (W.window == window)][["event_id", "scenario", "mmsi", det]]
    j = s.merge(w, how="left", on=["event_id", "scenario", "mmsi"])
    j = j[j[det].notna()]
    sets = []
    for eid, g in j.groupby("event_id", sort=True):
        inc = g[g.role == "incident"]
        ctl = g[g.role == "control"]
        if len(inc) != 1 or len(ctl) < 1:
            continue
        sc = np.concatenate([inc[det].to_numpy(float), ctl[det].to_numpy(float)])  # index 0 = incident
        # wins[k] = numerator if member k were the incident
        diff = sc[:, None] - sc[None, :]
        wins = (diff > 0).sum(1) + 0.5 * ((diff == 0).sum(1) - 1)  # exclude self-tie
        sets.append(wins)
    return sets


def analyse(scen, window, det, rng, perm=True):
    sets = build_sets(scen, window, det)
    n = np.array([len(x) for x in sets])
    pairs = n - 1
    P = pairs.sum()
    obs_w = np.array([x[0] for x in sets])
    auc = obs_w.sum() / P
    out = dict(scenario=scen, window=window, detector=det, n_sets=len(sets), n_pairs=int(P), auc=auc)
    if perm:
        flat = np.concatenate(sets)
        offs = np.concatenate([[0], np.cumsum(n)[:-1]])
        cnt = 0
        for _ in range(NPERM // 1000):
            idx = offs[None, :] + np.floor(rng.random((1000, len(n))) * n[None, :]).astype(int)
            ap = flat[idx].sum(1) / P
            cnt += (np.abs(ap - 0.5) >= np.abs(auc - 0.5) - 1e-12).sum()
        out["p_perm"] = (1 + cnt) / (1 + NPERM)
    bi = rng.integers(0, len(n), size=(NBOOT, len(n)))
    ba = obs_w[bi].sum(1) / pairs[bi].sum(1)
    out["ci_lo"], out["ci_hi"] = np.percentile(ba, [2.5, 97.5])
    return out


rng = np.random.default_rng(SEED)
rows = [analyse("real", "main", d, rng) for d in DETS]
main = pd.DataFrame(rows)
main["p_holm"] = multipletests(main["p_perm"], method="holm")[1]
other = []
for d in DETS:
    other.append(analyse("real", "early3", d, rng, perm=False))
    other.append(analyse("placebo30", "main", d, rng, perm=False))
    other.append(analyse("placebo60", "main", d, rng, perm=False))
other = pd.DataFrame(other)
pd.set_option("display.width", 200)
print("\nMAIN (real, main window)\n", main.round(4).to_string(index=False))
print("\nOTHER\n", other.round(4).to_string(index=False))
main.to_csv("/tmp/claude-0/recheck/recheck_main.csv", index=False)
other.to_csv("/tmp/claude-0/recheck/recheck_other.csv", index=False)
