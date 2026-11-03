"""GeoTrackNet phase 4: analysis (ANALYSIS_PLAN_ADDENDUM_1.md "Tests and reading rules",
GTN_SPEC.md phase 4, GTN_PRE_PHASE4_NOTES.md sections 1-2).

usage: python3 -I gtn/analyse_gtn.py

Detector d7_gtn = -log10(smallest NFA) from data/gtn/scores/*.csv (one row per scored
vessel, window and scenario; a vessel without a row is not scored), joined to the M4 sets
(data/stage_b/matched/M4.csv.gz) on (event_id, scenario, mmsi). Only the 122 events of the
16 regions (data/gtn/regions.csv) are used. AUC, permutation test, bootstrap and the
set-building rules are those of stage_b/analyse.py (imported unchanged: set_arrays,
auc_test, members_for, load_windows): pooled over incident-control pairs, ties half; a set
is used when its incident vessel and at least one control are scored; 10,000 within-set
permutations, two-sided; 5,000 bootstrap resamples of events; seed 20261022.

Outputs: results/gtn/results.md and results/gtn/tables/*.csv.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "stage_b"))
import analyse as sb  # noqa: E402  (stage_b/analyse.py, unchanged)

SB = os.path.join(ROOT, "data", "stage_b")
G = os.path.join(ROOT, "data", "gtn")
RES = os.path.join(ROOT, "results", "gtn")
TAB = os.path.join(RES, "tables")
SEED, NBOOT = sb.SEED, sb.NBOOT
DET = sb.DET
D7 = "d7_gtn"
DNAME = dict(sb.DNAME)
DNAME[D7] = "7 GeoTrackNet"
SCEN = ["real", "placebo30", "placebo60"]
fmt, fmtp = sb.fmt, sb.fmtp


def load_scores():
    s = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(G, "scores", "R*.csv")))],
                  ignore_index=True)
    assert not s.duplicated(["event_id", "scenario", "window", "mmsi"]).any()
    return s


def gtn_members(m4, scores, ids, scenario, window):
    m = m4[(m4.scenario == scenario) & m4.event_id.isin(ids)][
        ["event_id", "scenario", "mmsi", "role"]].copy()
    m["set_id"] = m.event_id.astype(str) + "_" + m.scenario
    sw = scores[(scores.scenario == scenario) & (scores.window == window)]
    return m.merge(sw[["event_id", "scenario", "mmsi", D7, "gtn_flag", "n_sequences"]],
                   on=["event_id", "scenario", "mmsi"], how="left")


def set_counts(mem, det):
    """Counts of sets at each step for one detector in one scenario/window."""
    n_sets = mem.set_id.nunique()
    inc = mem[mem.role == "incident"].groupby("set_id")[det].apply(lambda x: x.notna().any())
    ctl = mem[mem.role == "control"].groupby("set_id")[det].apply(lambda x: x.notna().sum())
    ctl = ctl.reindex(inc.index, fill_value=0)
    return dict(sets=n_sets, incident_not_scored=int((~inc).sum()),
                incident_scored_no_control_scored=int((inc & (ctl == 0)).sum()),
                used=int((inc & (ctl > 0)).sum()),
                vessels=len(mem), vessels_scored=int(mem[det].notna().sum()))


def aligned(sets, ids):
    d = {s[0]: (s[1][s[2]], s[3]) for s in sets}
    w = np.array([d.get(i, (0.0, 0))[0] for i in ids], float)
    n = np.array([d.get(i, (0.0, 0))[1] for i in ids], float)
    return w, n


def paired_diff(sets_g, sets_d, ids):
    """AUC(GTN) - AUC(d) over the set list ids, bootstrap of events (same resamples)."""
    wg, ng = aligned(sets_g, ids)
    wd, nd = aligned(sets_d, ids)
    diff = wg.sum() / ng.sum() - wd.sum() / nd.sum()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(ids), (NBOOT, len(ids)))
    with np.errstate(invalid="ignore", divide="ignore"):
        b = wg[idx].sum(1) / ng[idx].sum(1) - wd[idx].sum(1) / nd[idx].sum(1)
    b = b[np.isfinite(b)]
    lo, hi = np.percentile(b, [2.5, 97.5])
    return diff, lo, hi


def reading_rule(r):
    if r["p"] < 0.05 and r["auc"] >= 0.60:
        return "useful signal (p < 0.05 and AUC >= 0.60)."
    if r["hi"] < 0.60:
        return "no useful signal (upper end of the 95% interval below 0.60)."
    return (f"inconclusive: AUC {r['auc']:.3f} (95% interval {r['lo']:.3f}-{r['hi']:.3f}), "
            f"permutation p {fmtp(r['p'])}.")


def flag_rate(mem):
    from statsmodels.discrete.conditional_models import ConditionalLogit
    x = mem.dropna(subset=[D7]).copy()
    x = x[x.groupby("set_id").role.transform(lambda s: (s == "incident").any()
                                             & (s == "control").any())]
    x["flag"] = x.gtn_flag.astype(float)
    x["inc"] = (x.role == "incident").astype(float)
    xi = x[x.groupby("set_id").flag.transform(lambda s: s.nunique() > 1)]
    r = dict(n_sets=x.set_id.nunique(), inc_flagged=x[x.inc == 1].flag.mean(),
             ctrl_flagged=x[x.inc == 0].flag.mean(), informative_sets=xi.set_id.nunique(),
             OR=np.nan, lo=np.nan, hi=np.nan, p=np.nan, note="")
    try:
        if xi.set_id.nunique() < 2 or xi.inc.nunique() < 2:
            raise ValueError("too few informative sets")
        fit = ConditionalLogit(xi.flag.to_numpy(), xi[["inc"]].to_numpy(),
                               groups=xi.set_id.to_numpy()).fit(disp=0)
        b, se = float(fit.params[0]), float(fit.bse[0])
        if not np.isfinite(se) or se > 50:
            raise ValueError("no finite estimate (separation)")
        r.update(OR=np.exp(b), lo=np.exp(b - 1.96 * se), hi=np.exp(b + 1.96 * se),
                 p=float(fit.pvalues[0]))
    except Exception as e:  # recorded in the table
        r["note"] = str(e)[:80]
    return r


def main():
    os.makedirs(TAB, exist_ok=True)
    regions = pd.read_csv(os.path.join(G, "regions.csv"))
    reg_of = {int(e): r.region for r in regions.itertuples() for e in r.event_ids.split(";")}
    ids = set(reg_of)
    assert len(ids) == 122 and len(regions) == 16
    ev = pd.read_csv(os.path.join(SB, "events.csv"))
    ev["main_exclude"] = ev.main_exclude.astype(str).str.lower() == "true"
    assert ids <= set(ev.event_id[~ev.main_exclude])
    m4 = pd.read_csv(os.path.join(SB, "matched", "M4.csv.gz"))
    sets_tab = pd.read_csv(os.path.join(SB, "matched", "sets.csv"))
    scores = load_scores()
    state = json.load(open(os.path.join(G, "score_state.json")))
    w = sb.load_windows()
    L = []

    # ---- training summary (from the committed files) ---------------------------
    trows = []
    failed_p = os.path.join(G, "failed.json")
    failed = json.load(open(failed_p)) if os.path.exists(failed_p) else {}
    for r in regions.itertuples():
        dp = os.path.join(G, "models", r.region, "DONE.json")
        c = pd.read_csv(os.path.join(G, "models", r.region, "curve.csv"))
        best = c.loc[c.valid_ll_per_t.idxmax()]
        row = dict(region=r.region, n_events=r.n_events, n_valid_tracks=int(c.n_valid.iloc[-1]),
                   best_step=int(best.step), best_valid_ll=float(best.valid_ll_per_t),
                   stop_step=np.nan, stop_valid_ll=np.nan, status="")
        if os.path.exists(dp):
            d = json.load(open(dp))
            row.update(stop_step=int(d["stop_step"]), stop_valid_ll=float(d["valid_ll_per_t"]),
                       status="done: " + d["reason"].replace("|", ""))
        elif r.region in failed:
            row["status"] = "failed twice (dropped)"
        trows.append(row)
    train = pd.DataFrame(trows)
    train.to_csv(os.path.join(TAB, "training.csv"), index=False)

    # ---- counts of sets used and dropped ---------------------------------------
    crows = []
    for sc in SCEN:
        st = sets_tab[(sets_tab.definition == "M4") & (sets_tab.scenario == sc)
                      & sets_tab.event_id.isin(ids)]
        for win in ["main", "early3", "w6"]:
            mem = gtn_members(m4, scores, ids, sc, win)
            c = set_counts(mem, D7)
            crows.append(dict(scenario=sc, window=win, events=len(ids),
                              m4_status_rows=len(st),
                              m4_dropped_incident_lt10=int((st.status == "incident_fewer_than_10_positions").sum()),
                              m4_dropped_lt5_controls=int((st.status == "fewer_than_5_controls").sum()),
                              m4_dropped_no_ais=int((st.status == "impossible_no_ais").sum()),
                              m4_sets=c["sets"],
                              event_scenarios_prepared=sum(1 for k in state["done"] if k.endswith(f"_{sc}")),
                              dropped_incident_not_scored=c["incident_not_scored"],
                              dropped_no_control_scored=c["incident_scored_no_control_scored"],
                              sets_used=c["used"], vessels=c["vessels"],
                              vessels_scored=c["vessels_scored"]))
    counts = pd.DataFrame(crows)
    counts.to_csv(os.path.join(TAB, "counts.csv"), index=False)

    # ---- 1. Main test ----------------------------------------------------------
    mem_main = gtn_members(m4, scores, ids, "real", "main")
    sets_main = sb.set_arrays(mem_main, D7)
    main = sb.auc_test(sets_main)
    main["detector"] = D7
    main["reading_rule"] = reading_rule(main)
    pd.DataFrame([main]).to_csv(os.path.join(TAB, "main_test.csv"), index=False)
    pd.DataFrame([dict(set_id=s, region=reg_of[int(s.split("_")[0])], n_controls=n1,
                       rank01=wins[inc] / n1) for s, wins, inc, n1 in sets_main]
                 ).to_csv(os.path.join(TAB, "ranks_main.csv"), index=False)
    used_ids = [s[0] for s in sets_main]
    used_events = {int(s.split("_")[0]) for s in used_ids}

    # descriptive sensitivity (GTN_PRE_PHASE4_NOTES.md 1-2): not tests
    sens = []
    for label, drop in [("Without the events of R14 and R15",
                         {e for e, r in reg_of.items() if r in ("R14", "R15")}),
                        ("Without event 203 (one AIS day missing)", {203})]:
        r = sb.auc_test(sb.set_arrays(mem_main[~mem_main.event_id.isin(drop)], D7), perm=False)
        r["label"] = label
        r["events_dropped"] = len(drop & used_events)
        sens.append(r)
    sens = pd.DataFrame(sens)
    sens.to_csv(os.path.join(TAB, "sensitivity_descriptive.csv"), index=False)

    # ---- 2. Same-subset comparison with detectors 1-5 -------------------------
    mem_sb = sb.members_for(m4[(m4.scenario == "real") & m4.event_id.isin(used_events)],
                            w, "main")
    mem_sb = mem_sb.merge(mem_main[["event_id", "scenario", "mmsi", D7]],
                          on=["event_id", "scenario", "mmsi"], how="left")
    assert set(mem_sb.set_id) == set(used_ids)
    comp = []
    for d in DET:
        # (a) same sets, each detector on the members it scores
        sa = sb.set_arrays(mem_sb, d)
        ra = sb.auc_test(sa)
        da = paired_diff(sets_main, sa, used_ids)
        # (b) same sets and same vessels: members scored by both GTN and the detector
        both = mem_sb.dropna(subset=[d, D7])
        sbd, sbg = sb.set_arrays(both, d), sb.set_arrays(both, D7)
        ids_b = [s[0] for s in sbg]
        rbd, rbg = sb.auc_test(sbd), sb.auc_test(sbg, perm=False)
        db = paired_diff(sbg, sbd, ids_b)
        comp.append(dict(detector=d, subset="a: same sets", n_sets=ra["n_sets"],
                         n_pairs=ra["n_pairs"], auc_gtn=main["auc"], auc_det=ra["auc"],
                         lo_det=ra["lo"], hi_det=ra["hi"], p_det=ra["p"],
                         diff=da[0], diff_lo=da[1], diff_hi=da[2]))
        comp.append(dict(detector=d, subset="b: same sets and vessels", n_sets=rbd["n_sets"],
                         n_pairs=rbd["n_pairs"], auc_gtn=rbg["auc"], auc_det=rbd["auc"],
                         lo_det=rbd["lo"], hi_det=rbd["hi"], p_det=rbd["p"],
                         diff=db[0], diff_lo=db[1], diff_hi=db[2]))
    comp = pd.DataFrame(comp)
    comp.to_csv(os.path.join(TAB, "same_subset.csv"), index=False)

    # ---- 3. Supporting ---------------------------------------------------------
    flags = pd.DataFrame([flag_rate(mem_main)])
    flags.to_csv(os.path.join(TAB, "flag_rates.csv"), index=False)

    def run(sc, win, label):
        r = sb.auc_test(sb.set_arrays(gtn_members(m4, scores, ids, sc, win), D7))
        r["label"] = label
        return r

    wins_ = pd.DataFrame([run("real", wn, wn) for wn in ["w6", "main", "early3"]])
    wins_.to_csv(os.path.join(TAB, "windows.csv"), index=False)
    plac = pd.DataFrame([run(sc, "main", sc) for sc in SCEN])
    plac.to_csv(os.path.join(TAB, "placebo.csv"), index=False)

    # ---- report ----------------------------------------------------------------
    c0 = counts[(counts.scenario == "real") & (counts.window == "main")].iloc[0]
    L += ["# GeoTrackNet results (addendum 1)", "",
          "Generated by `gtn/analyse_gtn.py`; tables in `results/gtn/tables/` (file named under "
          "each table). Method as in `ANALYSIS_PLAN_ADDENDUM_1.md` (\"Scoring\", \"Tests and "
          "reading rules\") with the AUC, permutation test and bootstrap of `stage_b/analyse.py`: "
          "pooled over incident-control pairs (ties half); permutation p two-sided, 10,000 "
          "permutations within matched sets; 95% bootstrap interval, 5,000 resamples of events; "
          "seed 20261022. Score `d7_gtn` = -log10(smallest NFA); higher = more anomalous. "
          "GeoTrackNet is one pre-specified test at alpha 0.05, outside the Holm family of "
          "detectors 1-5. No interpretation beyond the reading rules.", "",
          "## Sets used and dropped", "",
          f"- Regions: {len(regions)} (`data/gtn/regions.csv`), {len(ids)} events; regions with "
          f"`DONE.json` {int(train.stop_step.notna().sum())}, failed twice {len(failed)}.",
          f"- Event-scenarios prepared for scoring: {len(state['done'])} "
          "(`data/gtn/score_state.json`), one per existing M4 set of these events.",
          f"- Vessels scored (rows in `data/gtn/scores/`): {len(scores)} vessel-windows; a vessel "
          "with no sequence of at least 6 hours inside the region in the window has no row.", "",
          "| Scenario | Window | Events | M4 sets | Dropped by M4 (incident < 10 pos. / < 5 controls / no AIS) | "
          "Incident not scored | No control scored | Sets used | Vessels scored / in sets |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in counts.iterrows():
        L.append(f"| {r.scenario} | {r.window} | {r.events} | {r.m4_sets} | "
                 f"{r.m4_dropped_incident_lt10} / {r.m4_dropped_lt5_controls} / {r.m4_dropped_no_ais} | "
                 f"{r.dropped_incident_not_scored} | {r.dropped_no_control_scored} | {r.sets_used} | "
                 f"{r.vessels_scored} / {r.vessels} |")
    L += ["", "File: `tables/counts.csv`. M4 drop counts are from `data/stage_b/matched/sets.csv` "
          "(Stage B rules, unchanged).", "",
          "## 1. Main test (M4, main window, true date)", "",
          "| Detector | Sets | Pairs | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |",
          f"| {DNAME[D7]} | {main['n_sets']} | {main['n_pairs']} | {fmt(main['auc'])} | "
          f"{fmt(main['lo'])}-{fmt(main['hi'])} | {fmtp(main['p'])} |", "",
          f"Of the {c0.events} events, {c0.sets_used} sets are used (incident vessel and at least "
          f"one control scored). File: `tables/main_test.csv`; per-set ranks `tables/ranks_main.csv`.",
          "", "## 2. Reading rule (plan section 6, addendum)", "",
          f"- **{DNAME[D7]}:** {main['reading_rule']}", "",
          "### Descriptive sensitivity (`GTN_PRE_PHASE4_NOTES.md` 1-2; not tests, not used by "
          "the reading rule)", "",
          "| Subset | Events dropped | Sets | Pairs | AUC | 95% interval |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in sens.iterrows():
        L.append(f"| {r.label} | {r.events_dropped} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} |")
    L += ["", "File: `tables/sensitivity_descriptive.csv`.", "",
          "## 3. Same-subset comparison with detectors 1-5 (true date, main window)", "",
          "Detectors 1-5 recomputed on the sets used in the main test. (a) same sets, each "
          "detector on the members it scores (at least 10 positions, Stage B rule); (b) same "
          "sets and the same vessels (members scored by both GeoTrackNet and the detector), so "
          "both AUCs use identical pairs. Difference = GeoTrackNet AUC minus the detector's AUC, "
          "95% interval from 5,000 bootstrap resamples of events (the same resamples for both "
          "AUCs). Permutation p of detectors 1-5 on these subsets is descriptive (no Holm).", "",
          "| Detector | Subset | Sets | Pairs | AUC GeoTrackNet | AUC detector | 95% interval | "
          "Permutation p | Difference | 95% interval |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in comp.iterrows():
        L.append(f"| {DNAME[r.detector]} | {r.subset} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc_gtn)} | "
                 f"{fmt(r.auc_det)} | {fmt(r.lo_det)}-{fmt(r.hi_det)} | {fmtp(r.p_det)} | "
                 f"{fmt(r['diff'])} | {fmt(r.diff_lo)} to {fmt(r.diff_hi)} |")
    f0 = flags.iloc[0]
    L += ["", "File: `tables/same_subset.csv`.", "",
          "## 4. Supporting analyses", "",
          "### Flag rate (smallest NFA < 1e-9; conditional logistic regression, M4, true date, "
          "main window)", "",
          "`ConditionalLogit` of flagged on incident status, stratified by matched set; sets "
          "where all or no members are flagged carry no information.", "",
          "| Sets | Incident flagged | Controls flagged | Informative sets | OR | 95% CI | p | Note |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |",
          f"| {f0.n_sets} | {f0.inc_flagged:.1%} | {f0.ctrl_flagged:.1%} | {f0.informative_sets} | "
          f"{fmt(f0.OR, 2)} | {fmt(f0.lo, 2)}-{fmt(f0.hi, 2)} | {fmtp(f0.p)} | {f0.note} |", "",
          "File: `tables/flag_rates.csv`.", "",
          "### Windows (M4, true date)", "",
          "| Window | Sets | Pairs | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in wins_.iterrows():
        L.append(f"| {r.label} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "w6 = T-6 h..T; main = T-24 h..T; early3 = T-27 h..T-3 h. File: `tables/windows.csv`.",
          "", "### Placebo dates (M4, main window, sets that exist on each date)", "",
          "| Scenario | Sets | Pairs | AUC | 95% interval | Permutation p |",
          "| --- | --- | --- | --- | --- | --- |"]
    for _, r in plac.iterrows():
        L.append(f"| {r.label} | {r.n_sets} | {r.n_pairs} | {fmt(r.auc)} | "
                 f"{fmt(r.lo)}-{fmt(r.hi)} | {fmtp(r.p)} |")
    L += ["", "File: `tables/placebo.csv`.", "",
          "## 5. Training (stop rule applied mechanically)", "",
          "| Region | Events | Held-out tracks | Stop step | Held-out bound at stop | "
          "Best held-out bound (step) | Status |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for _, r in train.iterrows():
        L.append(f"| {r.region} | {r.n_events} | {r.n_valid_tracks} | "
                 f"{'' if pd.isna(r.stop_step) else f'{int(r.stop_step):,}'} | {fmt(r.stop_valid_ll)} | "
                 f"{fmt(r.best_valid_ll)} ({int(r.best_step):,}) | {r.status} |")
    L += ["", "Held-out bound = validation log-likelihood per time step (`curve.csv`). R14 and R15 "
          "stopped at 20,000 steps with the bound below its best value (`GTN_PRE_PHASE4_NOTES.md` "
          "1); their committed step-20,000 models are used in all analyses above. Event-scenario "
          "R08/203_real was scored with one national AIS day (2015-03-15) missing "
          "(`GTN_PRE_PHASE4_NOTES.md` 2). File: `tables/training.csv`.", ""]
    open(os.path.join(RES, "results.md"), "w").write("\n".join(L))
    print("wrote results/gtn/results.md")


if __name__ == "__main__":
    sys.exit(main())
