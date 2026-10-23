"""B3: matched control sets (STAGE_B_SPEC.md B3, ANALYSIS_PLAN.md section 4).

usage: python3 -I stage_b/match.py

Reads only the exposure columns of the window files (window `main`); detector scores
are never loaded. Writes:

- data/stage_b/matched/<definition>.csv.gz: one row per member of each matched set
  (event_id, scenario, definition, role, mmsi, n_pos, hours, length_m, type_group,
  dist_centre_km, distance, radius_km)
- data/stage_b/matched/sets.csv: per event-scenario and definition, the number of
  controls or the reason the set was dropped
- results/stageB/balance.md: standardised mean differences of the matching variables

Definitions (implementation choices, also in results/stageB/notes.md):
- Pool for every definition: box vessels in the same window, not the incident vessel,
  not candidate-excluded, with at least `min_pos` positions (10, or 30 for the
  robustness check), positions within 25% of the incident vessel's.
- M1: whole box (150 km), distance on log positions.
- M2: whole box, log positions and log(1 + hours).
- M3: whole box, exact type group, log positions, log(1 + hours), log length.
- M4 (main): M3 restricted to vessels whose median main-window position is within 50 km
  of the centre; widened to the whole box (150 km) when fewer than 10 qualify.
- M4_k5, M4_k20: M4 with 5 and 20 controls. M4_min30: M4 with a 30-position minimum
  for the incident vessel and the controls.
- Mahalanobis covariance from the qualifying pool (pseudo-inverse); length is left out
  of the distance when the incident vessel has none, and for a control without length
  that control's distance uses the other variables only.
- k nearest, without replacement (each control used once per set); a set with fewer
  than 5 controls is dropped and counted (the same 5-control minimum for every
  definition).
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = os.path.join(ROOT, "data", "stage_b", "windows")
OUT = os.path.join(ROOT, "data", "stage_b", "matched")
BAL = os.path.join(ROOT, "results", "stageB", "balance.md")
COLS = ["event_id", "scenario", "window", "mmsi", "is_incident", "candidate_excluded",
        "n_pos", "hours", "type_group", "length_m", "dist_centre_km"]
DEFS = {
    # name: (vars, exact_type, area, k, min_pos)
    "M1": (["lpos"], False, False, 10, 10),
    "M2": (["lpos", "lhrs"], False, False, 10, 10),
    "M3": (["lpos", "lhrs", "llen"], True, False, 10, 10),
    "M4": (["lpos", "lhrs", "llen"], True, True, 10, 10),
    "M4_k5": (["lpos", "lhrs", "llen"], True, True, 5, 10),
    "M4_k20": (["lpos", "lhrs", "llen"], True, True, 20, 10),
    "M4_min30": (["lpos", "lhrs", "llen"], True, True, 10, 30),
}
MIN_CONTROLS = 5


def add_logs(d):
    d = d.copy()
    d["lpos"] = np.log(d["n_pos"].clip(lower=1))
    d["lhrs"] = np.log1p(d["hours"])
    L = d["length_m"].where(d["length_m"] > 0)
    d["llen"] = np.log(L)
    return d


def mahal(inc, pool, vars_):
    """Distance of each pool row to the incident row; NaN vars left out per pair."""
    X = pool[vars_].to_numpy(float)
    x0 = inc[vars_].to_numpy(float)
    use = ~np.isnan(x0)
    X, x0, vv = X[:, use], x0[use], [v for v, u in zip(vars_, use) if u]
    out = np.full(len(pool), np.nan)
    complete = ~np.isnan(X).any(axis=1)
    # covariance from the qualifying pool (complete rows for the full set)
    def dist(cols, rows):
        Xs = X[np.ix_(rows, cols)]
        ref = X[:, cols][~np.isnan(X[:, cols]).any(axis=1)]
        if len(ref) >= 2:
            S = np.atleast_2d(np.cov(ref, rowvar=False))
        else:
            S = np.eye(len(cols))
        Si = np.linalg.pinv(S)
        if not np.isfinite(Si).all() or np.allclose(Si, 0):
            Si = np.eye(len(cols))
        D = Xs - x0[cols]
        return np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", D, Si, D), 0))
    allc = list(range(X.shape[1]))
    if complete.any():
        out[complete] = dist(allc, np.where(complete)[0])
    inc_rows = np.where(~complete)[0]
    if len(inc_rows):
        # per-pattern of missing columns (only length can be missing in practice)
        pats = {}
        for i in inc_rows:
            key = tuple(np.where(~np.isnan(X[i]))[0])
            pats.setdefault(key, []).append(i)
        for key, rows in pats.items():
            if len(key):
                out[rows] = dist(list(key), np.array(rows))
    return out


def match_one(d, name):
    vars_, exact, area, k, min_pos = DEFS[name]
    inc = d[d.is_incident]
    if len(inc) != 1:
        return None, "no_incident_row"
    inc = inc.iloc[0]
    if inc.n_pos < min_pos:
        return None, f"incident_fewer_than_{min_pos}_positions"
    p = d[(~d.is_incident) & (~d.candidate_excluded.astype(bool)) & (d.n_pos >= min_pos)]
    p = p[(p.n_pos >= 0.75 * inc.n_pos) & (p.n_pos <= 1.25 * inc.n_pos)]
    if exact:
        p = p[p.type_group == inc.type_group]
    radius = 150
    if area:
        near = p[p.dist_centre_km <= 50]
        if len(near) >= 10:
            p, radius = near, 50
    if len(p) < MIN_CONTROLS:
        return None, "fewer_than_5_controls"
    dist = mahal(inc, p, vars_)
    p = p.assign(distance=dist).dropna(subset=["distance"])
    p = p.sort_values(["distance", "mmsi"], kind="mergesort").head(k)
    if len(p) < MIN_CONTROLS:
        return None, "fewer_than_5_controls"
    keep = ["event_id", "scenario", "mmsi", "n_pos", "hours", "length_m", "type_group",
            "dist_centre_km", "distance"]
    i_row = inc.to_frame().T.assign(distance=0.0)[keep].assign(role="incident")
    c_rows = p[keep].assign(role="control")
    s = pd.concat([i_row, c_rows], ignore_index=True)
    s["definition"], s["radius_km"] = name, radius
    return s, len(p)


def smd(a, b):
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return np.nan
    sd = np.sqrt((a.var() + b.var()) / 2)
    return (a.mean() - b.mean()) / sd if sd > 0 else 0.0


def main():
    os.makedirs(OUT, exist_ok=True)
    state = json.load(open(os.path.join(ROOT, "data", "stage_b", "state.json")))
    sets, rows = [], {n: [] for n in DEFS}
    for key in sorted(state["impossible"]):
        e, sc = key.split("_")
        for n in DEFS:
            sets.append(dict(event_id=int(e), scenario=sc, definition=n, n_controls=0,
                             radius_km=np.nan, status="impossible_no_ais"))
    files = sorted(glob.glob(os.path.join(WIN, "*.csv.gz")))
    for f in files:
        d = pd.read_csv(f, usecols=COLS)
        d = add_logs(d[d.window == "main"])
        e, sc = int(d.event_id.iloc[0]), d.scenario.iloc[0]
        for n in DEFS:
            s, r = match_one(d, n)
            if s is None:
                sets.append(dict(event_id=e, scenario=sc, definition=n, n_controls=0,
                                 radius_km=np.nan, status=r))
            else:
                rows[n].append(s)
                sets.append(dict(event_id=e, scenario=sc, definition=n, n_controls=r,
                                 radius_km=s.radius_km.iloc[0], status="matched"))
    for n in DEFS:
        m = pd.concat(rows[n], ignore_index=True)
        m.to_csv(os.path.join(OUT, f"{n}.csv.gz"), index=False,
                 compression={"method": "gzip", "mtime": 0})
    S = pd.DataFrame(sets).sort_values(["definition", "scenario", "event_id"])
    S.to_csv(os.path.join(OUT, "sets.csv"), index=False)

    # balance table (matching variables only)
    ev = pd.read_csv(os.path.join(ROOT, "data", "stage_b", "events.csv"),
                     usecols=["event_id", "main_exclude"])
    main_ids = set(ev.event_id[~ev.main_exclude.astype(bool)])
    L = ["# Stage B balance (B3)", "",
         "Matching variables only, window `main`. SMD = (mean incident - mean controls) / "
         "sqrt((var incident + var controls) / 2), on log positions, log(1 + hours) and "
         "log length (length where present). Controls pooled over sets. Main sample = "
         "events without `main_exclude`. Generated by `stage_b/match.py` from "
         "`data/stage_b/matched/`.", ""]
    L += ["## Sets per definition and scenario (main sample)", "",
          "| Definition | Scenario | Event-scenarios | Matched | Widened to 150 km | "
          "Incident < min positions | < 5 controls | No AIS days | Median controls |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    Sm = S[S.event_id.isin(main_ids)]
    for n in DEFS:
        for sc in ["real", "placebo30", "placebo60"]:
            x = Sm[(Sm.definition == n) & (Sm.scenario == sc)]
            mt = x[x.status == "matched"]
            L.append(f"| {n} | {sc} | {len(x)} | {len(mt)} | "
                     f"{int((mt.radius_km == 150).sum()) if DEFS[n][2] else '-'} | "
                     f"{int(x.status.str.startswith('incident_fewer').sum())} | "
                     f"{int((x.status == 'fewer_than_5_controls').sum())} | "
                     f"{int((x.status == 'impossible_no_ais').sum())} | "
                     f"{mt.n_controls.median() if len(mt) else ''} |")
    L += ["", "All 283 events (main sample plus excluded events) are in "
          "`data/stage_b/matched/sets.csv`.", "",
          "## Standardised mean differences (main sample)", "",
          "| Definition | Scenario | Sets | SMD log positions | SMD log hours | "
          "SMD log length | Same type group (controls) |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for n in DEFS:
        m = add_logs(pd.read_csv(os.path.join(OUT, f"{n}.csv.gz")))
        m = m[m.event_id.isin(main_ids)]
        for sc in ["real", "placebo30", "placebo60"]:
            x = m[m.scenario == sc]
            i, c = x[x.role == "incident"], x[x.role == "control"]
            it = i.set_index(["event_id"]).type_group
            same = (c.type_group.to_numpy() ==
                    it.reindex(c.event_id).to_numpy()).mean() if len(c) else np.nan
            L.append(f"| {n} | {sc} | {len(i)} | {smd(i.lpos, c.lpos):.3f} | "
                     f"{smd(i.lhrs, c.lhrs):.3f} | {smd(i.llen, c.llen):.3f} | "
                     f"{same:.1%} |")
    open(BAL, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
