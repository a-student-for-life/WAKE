"""B4: analysis (STAGE_B_SPEC.md B4, ANALYSIS_PLAN.md sections 6-8, DEVIATIONS.md).

usage: python3 -I stage_b/analyse.py

Inputs: data/stage_b/events.csv, data/stage_b/state.json, data/stage_b/windows/,
data/stage_b/matched/. Output: results/stageB/results.md and the tables in
results/stageB/tables/.

AUC: pooled over incident-control pairs of all matched sets (ties count half).
Per set the incident vessel's rank among itself and its controls, scaled 0-1 (ties
averaged), is written to tables/ranks_main.csv. Members without a score in a window
(fewer than 10 positions) are left out of that window's pairs; a set with no scored
control is left out. Permutation test: within each set a random member is labelled the
incident vessel, 10,000 permutations, two-sided around 0.5, p = (1 + #extreme) /
(1 + 10,000). Bootstrap: 5,000 resamples of sets (events), percentile 95% interval.
Seed 20261022 for each test.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB = os.path.join(ROOT, "data", "stage_b")
RES = os.path.join(ROOT, "results", "stageB")
TAB = os.path.join(RES, "tables")
SEED = 20261022
NPERM, NBOOT = 10_000, 5_000
DET = ["d1_speed_drop", "d2_loiter_h", "d3_gap_ratio", "d4_off_lane", "d5_iforest"]
DNAME = {"d1_speed_drop": "1 Speed drop", "d2_loiter_h": "2 Loitering",
         "d3_gap_ratio": "3 AIS gap", "d4_off_lane": "4 Off-lane",
         "d5_iforest": "5 Isolation Forest", "d6_tars": "6 TARS"}
WCOLS = ["event_id", "scenario", "window", "mmsi", "is_incident", "candidate_excluded",
         "n_pos", "dist_centre_km"] + DET + ["d6_tars"] + \
        [f"thr_d{i}_p{q}" for i in range(1, 6) for q in (90, 95, 99)]


def load_windows():
    parts = []
    for f in sorted(glob.glob(os.path.join(SB, "windows", "*.csv.gz"))):
        parts.append(pd.read_csv(f, usecols=WCOLS))
    w = pd.concat(parts, ignore_index=True)
    w["candidate_excluded"] = w.candidate_excluded.astype(bool)
    w["is_incident"] = w.is_incident.astype(bool)
    return w


def set_arrays(members, det):
    """members: rows with set_id, role, det. Returns list of (wins_per_member, n-1)."""
    out = []
    for sid, g in members.groupby("set_id", sort=True):
        g = g.dropna(subset=[det])
        if (g.role == "incident").sum() != 1 or (g.role == "control").sum() < 1:
            continue
        s = g[det].to_numpy(float)
        # wins of each member against the others: (#less + 0.5 #equal excluding self)
        order = np.sort(s)
        less = np.searchsorted(order, s, side="left")
        leq = np.searchsorted(order, s, side="right")
        wins = less + 0.5 * (leq - less - 1)
        inc = int(np.where(g.role.to_numpy() == "incident")[0][0])
        out.append((sid, wins, inc, len(s) - 1))
    return out


def auc_test(sets, perm=True, boot=True):
    if not sets:
        return dict(n_sets=0, n_pairs=0, auc=np.nan, p=np.nan, lo=np.nan, hi=np.nan)
    w_obs = np.array([s[1][s[2]] for s in sets])
    npair = np.array([s[3] for s in sets], float)
    auc = w_obs.sum() / npair.sum()
    r = dict(n_sets=len(sets), n_pairs=int(npair.sum()), auc=auc, p=np.nan,
             lo=np.nan, hi=np.nan)
    if perm:
        rng = np.random.default_rng(SEED)
        tot = np.zeros(NPERM)
        for _, wins, _, _ in sets:
            tot += wins[rng.integers(0, len(wins), NPERM)]
        a = tot / npair.sum()
        ext = np.abs(a - 0.5) >= np.abs(auc - 0.5) - 1e-12
        r["p"] = (1 + ext.sum()) / (1 + NPERM)
    if boot:
        rng = np.random.default_rng(SEED)
        idx = rng.integers(0, len(sets), (NBOOT, len(sets)))
        b = w_obs[idx].sum(1) / npair[idx].sum(1)
        r["lo"], r["hi"] = np.percentile(b, [2.5, 97.5])
    return r


def holm(ps):
    ps = np.asarray(ps, float)
    o = np.argsort(ps)
    adj = np.empty_like(ps)
    run = 0.0
    for k, i in enumerate(o):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def members_for(matched, w, window):
    m = matched[["event_id", "scenario", "mmsi", "role"]].copy()
    m["set_id"] = m.event_id.astype(str) + "_" + m.scenario
    ww = w[w.window == window]
    m = m.merge(ww, on=["event_id", "scenario", "mmsi"], how="left")
    # incident rows: match on the incident flag (one per file)
    return m


def fmt(x, d=3):
    return "" if pd.isna(x) else f"{x:.{d}f}"


def fmtp(p):
    return "" if pd.isna(p) else ("< 0.0001" if p < 1e-4 else f"{p:.4f}")


def main():
    os.makedirs(TAB, exist_ok=True)
    ev = pd.read_csv(os.path.join(SB, "events.csv"))
    for c in ["main_exclude", "main_exclude_any", "first_pass_both_yes"]:
        ev[c] = ev[c].astype(str).str.lower() == "true"
    state = json.load(open(os.path.join(SB, "state.json")))
    n_files = len(glob.glob(os.path.join(SB, "windows", "*.csv.gz")))
    assert n_files + len(state["impossible"]) == 3 * len(ev), "B2 incomplete"
    sets_tab = pd.read_csv(os.path.join(SB, "matched", "sets.csv"))
    w = load_windows()
    M = {n: pd.read_csv(os.path.join(SB, "matched", f"{n}.csv.gz"))
         for n in ["M1", "M2", "M3", "M4", "M4_k5", "M4_k20", "M4_min30"]}
    main_ids = set(ev.event_id[~ev.main_exclude])
    L = []
    src = {}

    def run(matched, ids, scenario, window, dets=DET, perm=True, label=""):
        mm = matched[(matched.scenario == scenario) & matched.event_id.isin(ids)]
        mem = members_for(mm, w, window)
        rows = []
        for d in dets:
            r = auc_test(set_arrays(mem, d), perm=perm)
            r["detector"] = d
            rows.append(r)
        out = pd.DataFrame(rows)
        out["label"] = label
        return out

    # ---- 1. Main test ----------------------------------------------------------
    main_res = run(M["M4"], main_ids, "real", "main", dets=DET + ["d6_tars"])
    core = main_res[main_res.detector.isin(DET)].copy()
    core["p_holm"] = holm(core.p.to_numpy())
    main_res = main_res.merge(core[["detector", "p_holm"]], on="detector", how="left")
    main_res.to_csv(os.path.join(TAB, "main_test.csv"), index=False)

    # per-set ranks (main test)
    mm = M["M4"][(M["M4"].scenario == "real") & M["M4"].event_id.isin(main_ids)]
    mem = members_for(mm, w, "main")
    rk = []
    for d in DET:
        for sid, wins, inc, n1 in set_arrays(mem, d):
            rk.append(dict(set_id=sid, detector=d, n_controls=n1,
                           rank01=wins[inc] / n1))
    pd.DataFrame(rk).to_csv(os.path.join(TAB, "ranks_main.csv"), index=False)

    # ---- 2. Reading rules ------------------------------------------------------
    concl = {}
    all_upper_below = bool((core.hi < 0.60).all())
    for _, r in main_res.iterrows():
        d = r.detector
        if d == "d6_tars":
            continue
        if r.p_holm < 0.05 and r.auc >= 0.60:
            concl[d] = "carries a useful signal (significant after Holm, AUC >= 0.60)."
        elif all_upper_below:
            concl[d] = ("no useful signal: the upper end of the interval is below 0.60 "
                        "for all five detectors.")
        else:
            concl[d] = (f"inconclusive: AUC {r.auc:.3f} (95% interval {r.lo:.3f}-"
                        f"{r.hi:.3f}), Holm p {fmtp(r.p_holm)}.")

    # ---- 3. Supporting analyses ------------------------------------------------
    # naive: every vessel in the area (median main-window position within 50 km),
    # at least 10 positions, not candidate-excluded, no matching
    naive_rows = []
    wr = w[(w.scenario == "real") & (w.window == "main") & w.event_id.isin(main_ids)]
    inc_ok = wr[wr.is_incident & (wr.n_pos >= 10)][["event_id"]]
    nv = wr[wr.event_id.isin(inc_ok.event_id) &
            (wr.is_incident | ((~wr.candidate_excluded) & (wr.n_pos >= 10) &
                               (wr.dist_centre_km <= 50)))].copy()
    nv["role"] = np.where(nv.is_incident, "incident", "control")
    nv["set_id"] = nv.event_id.astype(str) + "_real"
    for d in DET:
        r = auc_test(set_arrays(nv, d))
        r["detector"] = d
        naive_rows.append(r)
    naive = pd.DataFrame(naive_rows)
    naive.to_csv(os.path.join(TAB, "naive.csv"), index=False)

    # definitions side by side (real, main window)
    defs = pd.concat([run(M[n], main_ids, "real", "main", label=n)
                      for n in ["M1", "M2", "M3", "M4"]], ignore_index=True)
    defs.to_csv(os.path.join(TAB, "definitions.csv"), index=False)

    # flag rates: conditional logit of flagged on incident status, by matched set
    import statsmodels.api as sm  # noqa
    from statsmodels.discrete.conditional_models import ConditionalLogit
    flag_rows = []
    mm = M["M4"][(M["M4"].scenario == "real") & M["M4"].event_id.isin(main_ids)]
    mem = members_for(mm, w, "main")
    for d in DET:
        k = d[:2]
        for q, top in [(99, "1%"), (95, "5%"), (90, "10%")]:
            x = mem.dropna(subset=[d]).copy()
            x = x[x.groupby("set_id").role.transform(lambda s: (s == "incident").any()
                                                     & (s == "control").any())]
            x["flag"] = (x[d] >= x[f"thr_{k}_p{q}"]).astype(float)
            x["inc"] = (x.role == "incident").astype(float)
            info = x.groupby("set_id").flag.transform(lambda s: s.nunique() > 1)
            xi = x[info]
            r = dict(detector=d, top=top, n_sets=x.set_id.nunique(),
                     inc_flagged=x[x.inc == 1].flag.mean(),
                     ctrl_flagged=x[x.inc == 0].flag.mean(),
                     informative_sets=xi.set_id.nunique(), OR=np.nan, lo=np.nan,
                     hi=np.nan, p=np.nan, note="")
            try:
                if xi.set_id.nunique() < 2 or xi.inc.nunique() < 2:
                    raise ValueError("too few informative sets")
                fit = ConditionalLogit(xi.flag.to_numpy(), xi[["inc"]].to_numpy(),
                                       groups=xi.set_id.to_numpy()).fit(disp=0)
                b, se = float(fit.params[0]), float(fit.bse[0])
                if not np.isfinite(se) or se > 50:
                    raise ValueError("no finite estimate (separation)")
                r.update(OR=np.exp(b), lo=np.exp(b - 1.96 * se),
                         hi=np.exp(b + 1.96 * se), p=float(fit.pvalues[0]))
            except Exception as e:  # recorded in the table
                r["note"] = str(e)[:80]
            flag_rows.append(r)
    flags = pd.DataFrame(flag_rows)
    flags.to_csv(os.path.join(TAB, "flag_rates.csv"), index=False)

    plac = pd.concat([run(M["M4"], main_ids, sc, "main", label=sc)
                      for sc in ["real", "placebo30", "placebo60"]], ignore_index=True)
    plac.to_csv(os.path.join(TAB, "placebo.csv"), index=False)
    wins_ = pd.concat([run(M["M4"], main_ids, "real", wn, label=wn)
                       for wn in ["w6", "main", "w48"]], ignore_index=True)
    wins_.to_csv(os.path.join(TAB, "windows.csv"), index=False)
    after = run(M["M4"], main_ids, "real", "after12", perm=False, label="after12")
    after.to_csv(os.path.join(TAB, "after12_descriptive.csv"), index=False)

    # ---- 4. Robustness ---------------------------------------------------------
    rob = []
    allids = set(ev.event_id)

    def add(label, matched, ids, window="main", note=""):
        r = run(matched, ids, "real", window, perm=False, label=label)
        r["note"] = note
        rob.append(r)

    add("Main (M4, main sample)", M["M4"], main_ids)
    for s in ["sea", "inland"]:
        add(f"Setting: {s}", M["M4"], main_ids & set(ev.event_id[ev.setting == s]))
    for t in sorted(ev.incident_type.unique()):
        add(f"Incident type: {t}", M["M4"],
            main_ids & set(ev.event_id[ev.incident_type == t]))
    add("NRC only", M["M4"], main_ids & set(ev.event_id[ev.source == "NRC"]))
    add("IncidentNews only", M["M4"],
        main_ids & set(ev.event_id[ev.source == "IncidentNews"]))
    n_unsure = int((pd.read_csv(os.path.join(ROOT, "data", "second_look.csv"))
                    .final == "unsure").sum())
    rob.append(pd.DataFrame([dict(label="Unsure cases added back", detector=d,
                                  n_sets=0, auc=np.nan, lo=np.nan, hi=np.nan,
                                  note=f"not run: {n_unsure} matches end as unsure "
                                       "in data/second_look.csv, but B1 builds events "
                                       "from data/confirmed_events.csv only, so they "
                                       "have no window files or matched sets")
                             for d in DET]))
    add("Berth and storm events added back (all 283)", M["M4"], allids)
    add("Event 211 dropped (main_exclude_any)", M["M4"],
        set(ev.event_id[~ev.main_exclude_any]))
    add("Both raters yes in blind review only (DEVIATIONS #2)", M["M4"],
        main_ids & set(ev.event_id[ev.first_pass_both_yes]))
    add("5 controls", M["M4_k5"], main_ids)
    add("20 controls", M["M4_k20"], main_ids)
    add("Minimum 30 positions", M["M4_min30"], main_ids)
    # MMSI-only events: same as main when IMO merging joined no events of
    # different MMSIs and split no same-MMSI reports within 3 days
    ce = pd.read_csv(os.path.join(ROOT, "data", "confirmed_events.csv"), dtype=str)
    multi = int((ce.groupby("event_id").mmsi.nunique() > 1).sum())
    ev_t = ev.assign(T=pd.to_datetime(ev.T_utc)).sort_values(["mmsi", "T"])
    gap = ev_t.groupby("mmsi")["T"].diff()
    split = int((gap <= pd.Timedelta(days=3)).sum())
    note = (f"identical to main: {multi} events merge several MMSIs and {split} "
            "same-MMSI event pairs lie within 3 days")
    add("MMSI-only events (no IMO merging)", M["M4"], main_ids, note=note)
    add("Main window ending 3 h before T (early3)", M["M4"], main_ids, window="early3")
    robt = pd.concat(rob, ignore_index=True)
    robt.to_csv(os.path.join(TAB, "robustness.csv"), index=False)

    # ---- 5. Counts and report --------------------------------------------------
    s = sets_tab[sets_tab.event_id.isin(main_ids)]
    def cnt(defn, sc):
        x = s[(s.definition == defn) & (s.scenario == sc)]
        return x.status.value_counts().to_dict(), len(x)

    L += ["# Stage B results", "",
          "Generated by `stage_b/analyse.py`; every table below is also in "
          "`results/stageB/tables/` (file named under each table). Method as in "
          "`ANALYSIS_PLAN.md` sections 6-8, `STAGE_B_SPEC.md` B4 and `DEVIATIONS.md`. "
          "AUC pooled over incident-control pairs (ties half); permutation p "
          "two-sided, 10,000 permutations within matched sets; 95% bootstrap "
          "interval, 5,000 resamples of events; seed 20261022. No interpretation "
          "beyond the plan's reading rules.", ""]
    L += ["## Events used and dropped", "",
          f"- Vessel events: {len(ev)} (`data/stage_b/events.csv`); main sample "
          f"{len(main_ids)}, {len(ev) - len(main_ids)} excluded by `main_exclude` "
          "(berth, storm, not the source, unclear; `data/event_coding.csv`).",
          f"- Event-scenarios: {3 * len(ev)}; window files {n_files}, recorded "
          f"impossible {len(state['impossible'])} (`data/stage_b/state.json`: AIS days "
          "missing or nearly empty, DEVIATIONS #4)."]
    for sc in ["real", "placebo30", "placebo60"]:
        c, n = cnt("M4", sc)
        L.append(f"- M4, {sc}, main sample: {n} events; matched {c.get('matched', 0)}; "
                 f"dropped: incident vessel with fewer than 10 positions in the window "
                 f"{c.get('incident_fewer_than_10_positions', 0)}, fewer than 5 "
                 f"controls {c.get('fewer_than_5_controls', 0)}, no AIS "
                 f"{c.get('impossible_no_ais', 0)} "
                 "(`data/stage_b/matched/sets.csv`).")
    L.append("- Per detector, sets where the incident vessel or every control has no "
             "score are left out; the number of sets used is in each table.")
    L += ["", "## 1. Main test (M4, main window, real date, main sample)", "",
          "| Detector | Sets | Pairs | AUC | 95% interval | Permutation p | Holm p |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in main_res.iterrows():
        L.append(f"| {DNAME[r.detector]} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} | {fmtp(r.p_holm)} |"
                 if r.n_sets else f"| {DNAME[r.detector]} | 0 | 0 | | | | |")
    L += ["", "File: `results/stageB/tables/main_test.csv`; per-set ranks "
          "`tables/ranks_main.csv`. Detector 6 is empty (`results/stageB/notes.md`) and "
          "outside the Holm family.", "",
          "## 2. Reading rules (plan section 6)", ""]
    for d in DET:
        L.append(f"- **{DNAME[d]}:** {concl[d]}")
    L += ["", "## 3. Supporting analyses", "",
          "### Naive comparison (every vessel within 50 km, at least 10 positions, "
          "no matching)", "",
          "| Detector | Sets | Pairs | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in naive.iterrows():
        L.append(f"| {DNAME[r.detector]} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "File: `tables/naive.csv`.", "",
          "### Matching definitions side by side (real date, main window)", "",
          "| Definition | Detector | Sets | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in defs.iterrows():
        L.append(f"| {r.label} | {DNAME[r.detector]} | {r.n_sets} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "File: `tables/definitions.csv`.", "",
          "### Flag rates (conditional logistic regression, M4, real, main window)", "",
          "Flagged = score at or above the national 99th, 95th or 90th percentile of "
          "that day's fleet. `ConditionalLogit` of flagged on incident status, "
          "stratified by matched set; sets where all or no members are flagged carry "
          "no information.", "",
          "| Detector | Top | Sets | Incident flagged | Controls flagged | "
          "Informative sets | OR | 95% CI | p | Note |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in flags.iterrows():
        L.append(f"| {DNAME[r.detector]} | {r.top} | {r.n_sets} | "
                 f"{r.inc_flagged:.1%} | {r.ctrl_flagged:.1%} | {r.informative_sets} | "
                 f"{fmt(r.OR, 2)} | {fmt(r.lo, 2)}-{fmt(r.hi, 2)} | {fmtp(r.p)} | "
                 f"{r.note} |")
    L += ["", "File: `tables/flag_rates.csv`.", "",
          "### Placebo dates (M4, main window, re-matched on each date)", "",
          "| Scenario | Detector | Sets | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in plac.iterrows():
        L.append(f"| {r.label} | {DNAME[r.detector]} | {r.n_sets} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "File: `tables/placebo.csv`.", "",
          "### Windows (M4 sets of the main window, real date)", "",
          "| Window | Detector | Sets | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in wins_.iterrows():
        L.append(f"| {r.label} | {DNAME[r.detector]} | {r.n_sets} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "File: `tables/windows.csv`.", "",
          "### After T (T to T+12 h), descriptive only, not a detection result", "",
          "| Detector | Sets | AUC | 95% interval |", "| --- | --- | --- | --- |"]
    for _, r in after.iterrows():
        L.append(f"| {DNAME[r.detector]} | {r.n_sets} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} |")
    L += ["", "File: `tables/after12_descriptive.csv`.", "",
          "## 4. Robustness checks (AUC and 95% bootstrap interval)", "",
          "| Check | Detector | Sets | AUC | 95% interval | Note |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in robt.iterrows():
        L.append(f"| {r.label} | {DNAME[r.detector]} | {int(r.n_sets)} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {'' if pd.isna(r.note) else r.note} |")
    L += ["", "File: `tables/robustness.csv`.", ""]
    open(os.path.join(RES, "results.md"), "w").write("\n".join(L))
    print("wrote results/stageB/results.md")


if __name__ == "__main__":
    sys.exit(main())
