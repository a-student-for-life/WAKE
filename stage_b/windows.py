"""B2: window files (STAGE_B_SPEC.md B2, detectors as in ANALYSIS_PLAN.md section 5).

usage: python3 -I stage_b/windows.py [--max-minutes M] [--no-git]

Event-scenarios (data/stage_b/events.csv x real/placebo30/placebo60) are processed in
order of window start (T-48 h), so consecutive ones share AIS days. AIS days are read once
into compact arrays (stage_b/aisday.py) and kept in memory while an unfinished
event-scenario still needs them; raw files are deleted after reading (never more than 4
on disk, within the spec's cap of 20).

Writes data/stage_b/windows/<event_id>_<scenario>.csv.gz (one row per box vessel and
window) and records progress in data/stage_b/state.json. Commits and pushes after every
window file unless --no-git.

Implementation details the plan and spec leave open (also in results/stageB/notes.md):
- Windows are half-open: pre-T windows [start, end), after12 [T, T+12 h).
- Days covering T-48 h..T are required; if one does not exist on the AIS hosts (404) or
  its national file has fewer than 1,000,000 positions (an outage; normal days have
  6-10 million), the event-scenario is recorded as impossible (DEVIATIONS.md #4). Days that only cover (T, T+12 h] are
  optional; if missing, after12 is computed on what exists and the file says so.
- Consecutive positions: hours observed sum gaps <= 1 h; distance sailed sums all
  consecutive great-circle steps; speed-drop and turn-rate pairs need 0 < gap <= 10 min.
- Speed drop: max(0, largest fall); 0 when no qualifying pair.
- Loitering: runs of consecutive positions with SOG < 2 kn, each within 1 km of the run's
  first position, broken by a gap > 1 h, a position within 3 km of a stationary place, or
  a position at >= 2 kn; score = longest run duration (hours).
- AIS gap: longest silence starting at SOG >= 3 kn (hours) divided by the gap norm of the
  0.25-degree cell of the vessel's median position (vessel's day median for the fleet,
  window median for windows); 0 when there is no such silence. The norm uses vessels
  that have at least one such silence that day.
- Off-lane: per position -log(1 + other vessels in the 0.01-degree cell that day), other
  = distinct vessels in the cell on the reference day minus the vessel itself if it was
  there that day; mean over positions.
- Isolation Forest features with no defined value (no valid SOG, fewer than 2 turn-rate
  pairs) are set to 0.
- Type group and length per window; when a window has no valid type (0 or missing) or
  length, the vessel's value over the whole T-48 h..T+12 h span is used.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from numba import njit
from scipy.spatial import cKDTree
from sklearn.ensemble import IsolationForest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aisday  # noqa: E402

EVENTS = "data/stage_b/events.csv"
OUTDIR = "data/stage_b/windows"
STATE = "data/stage_b/state.json"
SCEN = ["real", "placebo30", "placebo60"]
WINDOWS = {"main": (-24, 0), "w6": (-6, 0), "w48": (-48, 0), "early3": (-27, -3), "after12": (0, 12)}
SPAN = (-48, 12)
BOX_KM = 150.0
MIN_POS = 10
MIN_DAY_POS = 1_000_000  # a national day file below this is an outage (DEVIATIONS.md #4)
SEED = 20261022
R = 6371.0088
DET = ["d1_speed_drop", "d2_loiter_h", "d3_gap_ratio", "d4_off_lane", "d5_iforest"]
FEAT = ["mean_sog", "std_sog", "speed_drop", "longest_gap_h", "turn_std", "share_stat", "off_lane"]


def utc(s):
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())


def day_of(ts):
    return datetime.fromtimestamp(ts, tz=timezone.utc).date()


def type_group(t):
    if t in (30, 1001):
        return "fishing"
    if t in (31, 32, 52, 1025):
        return "tug_towing"
    if 70 <= t <= 79 or t == 1004:
        return "cargo"
    if 80 <= t <= 89:
        return "tanker"
    if 60 <= t <= 69:
        return "passenger"
    return "other_unknown"


# ------------------------------------------------------------------ kernels
@njit(cache=True)
def _hav(la1, lo1, la2, lo2):
    p1 = np.radians(la1)
    p2 = np.radians(la2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lo2 - lo1) / 2) ** 2
    if a > 1.0:
        a = 1.0
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


@njit(cache=True)
def vessel_stats(t, lat, lon, sog, cog, excl, st, en):
    """Per group [st[g], en[g]) of time-sorted positions. Returns a (G, 11) array:
    n, hours, dist_km, speed_drop, longest_gap_h, moving_gap_h, mean_sog, std_sog,
    share_stat, turn_std, loiter_h (NaN where undefined)."""
    G = len(st)
    out = np.full((G, 11), np.nan)
    for g in range(G):
        a, b = st[g], en[g]
        n = b - a
        out[g, 0] = n
        hours = 0.0
        dist = 0.0
        drop = 0.0
        lgap = 0.0
        mgap = 0.0
        s1 = 0.0
        s2 = 0.0
        ns = 0
        nstat = 0
        r1 = 0.0
        r2 = 0.0
        nr = 0
        best = 0.0
        active = False
        anc = 0
        ts = 0
        tl = 0
        for i in range(a, b):
            v = sog[i]
            if not np.isnan(v):
                s1 += v
                s2 += v * v
                ns += 1
                if v < 0.5:
                    nstat += 1
            if i > a:
                dt = t[i] - t[i - 1]
                if dt <= 3600:
                    hours += dt
                dist += _hav(lat[i - 1], lon[i - 1], lat[i], lon[i])
                if dt > lgap:
                    lgap = dt
                if sog[i - 1] >= 3.0 and dt > mgap:
                    mgap = dt
                if dt > 0 and dt <= 600:
                    if not np.isnan(v) and not np.isnan(sog[i - 1]):
                        f = sog[i - 1] - v
                        if f > drop:
                            drop = f
                    c0 = cog[i - 1]
                    c1 = cog[i]
                    if c0 >= 0 and c0 < 360 and c1 >= 0 and c1 < 360:
                        dc = (c1 - c0 + 180.0) % 360.0 - 180.0
                        rr = dc / (dt / 60.0)
                        r1 += rr
                        r2 += rr * rr
                        nr += 1
            # loitering
            c = (not np.isnan(v)) and v < 2.0 and not excl[i]
            if c:
                if active and (t[i] - t[i - 1]) <= 3600 and _hav(lat[anc], lon[anc], lat[i], lon[i]) <= 1.0:
                    tl = t[i]
                else:
                    active = True
                    anc = i
                    ts = t[i]
                    tl = t[i]
                if tl - ts > best:
                    best = tl - ts
            else:
                active = False
        out[g, 1] = hours / 3600.0
        out[g, 2] = dist
        out[g, 3] = drop
        out[g, 4] = lgap / 3600.0
        out[g, 5] = mgap / 3600.0
        if ns > 0:
            m = s1 / ns
            out[g, 6] = m
            out[g, 7] = np.sqrt(max(s2 / ns - m * m, 0.0))
            out[g, 8] = nstat / ns
        if nr >= 2:
            m = r1 / nr
            out[g, 9] = np.sqrt(max(r2 / nr - m * m, 0.0))
        out[g, 10] = best / 3600.0
    return out


def _mode(a):
    u, c = np.unique(a, return_counts=True)
    return u[c.argmax()]


def groups(mmsi):
    if len(mmsi) == 0:
        return np.array([], np.int64), np.array([], np.int64)
    st = np.flatnonzero(np.r_[True, mmsi[1:] != mmsi[:-1]])
    en = np.r_[st[1:], len(mmsi)]
    return st, en


def cell01(lat, lon):
    return (np.floor((lat.astype(np.float64) + 90) * 100).astype(np.int64) * 36000
            + np.floor((lon.astype(np.float64) + 180) * 100).astype(np.int64))


def cell25(lat, lon):
    return (np.floor((np.asarray(lat, np.float64) + 90) * 4).astype(np.int64) * 1440
            + np.floor((np.asarray(lon, np.float64) + 180) * 4).astype(np.int64))


def xyz(lat, lon):
    la = np.radians(np.asarray(lat, np.float64))
    lo = np.radians(np.asarray(lon, np.float64))
    return np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)]


def hav_np(la1, lo1, la2, lo2):
    p1, p2 = np.radians(la1), np.radians(la2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(np.asarray(lo2) - lo1) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


# ------------------------------------------------------------------ fleet reference
class FleetRef:
    """Reference for one UTC day, from the full national file (spec B2 step 5)."""

    def __init__(self, d, day):
        self.day = str(day)
        c = cell01(d["lat"], d["lon"])
        pair = np.unique(c * 1_000_000_000 + d["mmsi"].astype(np.int64))
        self.pairs = pair
        pc_ = pair // 1_000_000_000
        self.dcell, self.dcount = np.unique(pc_, return_counts=True)
        slow = d["sog"] < 0.5
        sp = np.unique(c[slow] * 1_000_000_000 + d["mmsi"][slow].astype(np.int64))
        sc, scount = np.unique(sp // 1_000_000_000, return_counts=True)
        stat = sc[scount >= 20]
        self.n_stat = len(stat)
        if len(stat):
            clat = (stat // 36000) / 100 - 90 + 0.005
            clon = (stat % 36000) / 100 - 180 + 0.005
            self.tree = cKDTree(xyz(clat, clon))
        else:
            self.tree = None
        st, en = groups(d["mmsi"])
        excl = self.excluded(d["lat"], d["lon"])
        S = vessel_stats(d["t"], d["lat"], d["lon"], d["sog"], d["cog"], excl, st, en)
        off = self.off_lane(d["mmsi"], c, st)
        mlat = np.array([np.median(d["lat"][a:b]) for a, b in zip(st, en)])
        mlon = np.array([np.median(d["lon"][a:b]) for a, b in zip(st, en)])
        # gap norm per 0.25-degree cell
        has = S[:, 0] >= 2
        mg = S[:, 5]
        movers = has & (mg > 0)
        gc = cell25(mlat[movers], mlon[movers])
        self.gap_nat = float(np.median(mg[movers])) if movers.any() else np.nan
        df = pd.DataFrame({"c": gc, "g": mg[movers]}).groupby("c").g.agg(["median", "size"])
        df = df[df["size"] >= 10]
        self.gap_cells = dict(zip(df.index.to_numpy(), df["median"].to_numpy()))
        # fleet scores for vessels with >= MIN_POS positions
        ok = S[:, 0] >= MIN_POS
        F = self.features(S, off)[ok]
        self.n_fleet = int(ok.sum())
        self.iforest = IsolationForest(n_estimators=200, random_state=SEED).fit(F)
        scores = np.c_[S[ok, 3], S[ok, 10], self.gap_ratio(S[ok, 5], mlat[ok], mlon[ok]), off[ok],
                       -self.iforest.score_samples(F)]
        self.thr = {}
        for j, name in enumerate(DET):
            for q in (90, 95, 99):
                self.thr[f"thr_{name.split('_')[0]}_p{q}"] = float(np.percentile(scores[:, j], q))

    @staticmethod
    def features(S, off):
        F = np.c_[S[:, 6], S[:, 7], S[:, 3], S[:, 4], S[:, 9], S[:, 8], off]
        return np.nan_to_num(F, nan=0.0)

    def excluded(self, lat, lon):
        if self.tree is None or len(lat) == 0:
            return np.zeros(len(lat), np.bool_)
        chord = 2 * np.sin(3.0 / R / 2)
        hits = self.tree.query_ball_point(xyz(lat, lon), chord, return_length=True)
        return np.asarray(hits) > 0

    def off_lane(self, mmsi, c, st):
        i = np.searchsorted(self.dcell, c)
        i = np.clip(i, 0, len(self.dcell) - 1)
        dens = np.where(self.dcell[i] == c, self.dcount[i], 0)
        key = c * 1_000_000_000 + mmsi.astype(np.int64)
        j = np.clip(np.searchsorted(self.pairs, key), 0, len(self.pairs) - 1)
        self_in = self.pairs[j] == key
        other = np.maximum(dens - self_in, 0)
        v = -np.log1p(other)
        if len(st) == 0:
            return np.array([])
        n = np.diff(np.r_[st, len(mmsi)])
        return np.add.reduceat(v, st) / n

    def gap_ratio(self, mgap, mlat, mlon):
        gc = cell25(mlat, mlon)
        norm = np.array([self.gap_cells.get(int(x), self.gap_nat) for x in gc], dtype=float)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = np.where(mgap > 0, mgap / norm, 0.0)
        return r


# ------------------------------------------------------------------ candidates
def candidate_lists():
    c = pd.read_csv("data/candidates.csv", dtype=str, keep_default_na=False)
    when = c.time_utc.where(c.time_utc.str.len() > 0, c.date_local + " 00:00")
    ts = np.array([utc(x) for x in when])
    imo = pd.to_numeric(c.ais_imo.str.replace("IMO", ""), errors="coerce").fillna(0).astype(np.int64).to_numpy()
    return ts, c.mmsi.astype(np.int64).to_numpy(), imo


# ------------------------------------------------------------------ main
def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"done": {}, "impossible": {}}


def save_state(st):
    st["done"] = dict(sorted(st["done"].items()))
    st["impossible"] = dict(sorted(st["impossible"].items()))
    json.dump(st, open(STATE, "w"), indent=1)


def git(*a, check=False):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=check)


def commit(paths, msg):
    git("add", *paths)
    if git("commit", "-q", "-m", msg).returncode == 0:
        git("pull", "-q", "--rebase", "origin", "main")
        r = git("push", "-q", "origin", "main")
        if r.returncode != 0:
            print("push failed:", r.stderr[:300], flush=True)


def scenario_list(ev, st):
    rows = []
    for e in ev.itertuples(index=False):
        for s in SCEN:
            key = f"{e.event_id}_{s}"
            if key in st["done"] or key in st["impossible"]:
                continue
            T = utc(getattr(e, f"T_{s}"))
            rows.append((T + SPAN[0] * 3600, key, e, s, T))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows


def span_days(T):
    a = day_of(T + SPAN[0] * 3600)
    req_end = day_of(T - 1)
    b = day_of(T + SPAN[1] * 3600 - 1)
    days, d = [], a
    while d <= b:
        days.append(d)
        d += timedelta(days=1)
    return days, [x for x in days if x <= req_end]


def process(key, e, scen, T, buf, refs, missing, cands, version):
    days, req = span_days(T)
    t0, t1 = T + SPAN[0] * 3600, T + SPAN[1] * 3600
    inc_mmsi = [int(x) for x in str(e.mmsis).split(";")]
    # 1. centre
    def pos_of(m, a, b):
        la, lo = [], []
        for dd in days:
            if dd in missing:
                continue
            d = buf[dd]
            i0, i1 = np.searchsorted(d["mmsi"], m), np.searchsorted(d["mmsi"], m, side="right")
            tt = d["t"][i0:i1]
            k = (tt >= a) & (tt < b)
            la.append(d["lat"][i0:i1][k])
            lo.append(d["lon"][i0:i1][k])
        return np.concatenate(la), np.concatenate(lo)
    la, lo = map(np.concatenate, zip(*[pos_of(m, T - 24 * 3600, T) for m in inc_mmsi]))
    csrc = "incident_main_window"
    if len(la) == 0:
        la, lo = map(np.concatenate, zip(*[pos_of(m, t0, t1) for m in inc_mmsi]))
        csrc = "incident_span"
    if len(la):
        clat, clon = float(np.median(la)), float(np.median(lo))
    else:
        clat, clon, csrc = float(e.ref_lat), float(e.ref_lon), "reference_point"
    # 2. box
    dlat = BOX_KM / 111.0 + 0.01
    dlon = BOX_KM / (111.0 * max(np.cos(np.radians(clat)), 0.05)) + 0.01
    boxm = set(inc_mmsi)
    for dd in days:
        if dd in missing:
            continue
        d = buf[dd]
        k = ((d["t"] >= t0) & (d["t"] < t1) & (np.abs(d["lat"] - clat) <= dlat)
             & (np.abs(((d["lon"] - clon + 180) % 360) - 180) <= dlon))
        if k.any():
            kk = np.flatnonzero(k)
            near = hav_np(clat, clon, d["lat"][kk], d["lon"][kk]) <= BOX_KM
            boxm.update(np.unique(d["mmsi"][kk[near]]).tolist())
    boxa = np.array(sorted(boxm), np.int32)
    parts = []
    for dd in days:
        if dd in missing:
            continue
        d = buf[dd]
        k = np.isin(d["mmsi"], boxa) & (d["t"] >= t0) & (d["t"] < t1)
        parts.append({f: v[k] for f, v in d.items()})
    P = {f: np.concatenate([p[f] for p in parts]) for f in aisday.FIELDS}
    o = np.lexsort((P["t"], P["mmsi"]))
    P = {f: v[o] for f, v in P.items()}
    # span-level vessel attributes
    sst, sen = groups(P["mmsi"])
    span_attr = {}
    for a, b in zip(sst, sen):
        m = int(P["mmsi"][a])
        ty = P["type"][a:b]
        ty = ty[ty > 0]
        ln = P["length"][a:b]
        ln = ln[np.isfinite(ln) & (ln > 0)]
        im = P["imo"][a:b]
        im = im[im > 0]
        span_attr[m] = (int(np.bincount(ty).argmax()) if len(ty) else -1,
                        float(np.median(ln)) if len(ln) else np.nan,
                        int(_mode(im)) if len(im) else 0)
    # candidate exclusion: MMSI or IMO in candidates.csv for an incident within 30 days of T
    cts, cmm, cim = cands
    near = np.abs(cts - T) <= 30 * 86400
    cand_m, cand_i = set(cmm[near].tolist()), set(cim[near & (cim > 0)].tolist())
    # 5. fleet reference
    rday = day_of(T - 12 * 3600)
    ref = refs[rday]
    rows = []
    for w, (ha, hb) in WINDOWS.items():
        a, b = T + ha * 3600, T + hb * 3600
        k = (P["t"] >= a) & (P["t"] < b)
        W = {f: v[k] for f, v in P.items()}
        st, en = groups(W["mmsi"])
        excl = ref.excluded(W["lat"], W["lon"])
        S = vessel_stats(W["t"], W["lat"], W["lon"], W["sog"], W["cog"], excl, st, en)
        off = ref.off_lane(W["mmsi"], cell01(W["lat"], W["lon"]), st)
        mlat = np.array([np.median(W["lat"][x:y]) for x, y in zip(st, en)])
        mlon = np.array([np.median(W["lon"][x:y]) for x, y in zip(st, en)])
        gap = ref.gap_ratio(S[:, 5], mlat, mlon) if len(st) else np.array([])
        ifs = -ref.iforest.score_samples(FleetRef.features(S, off)) if len(st) else np.array([])
        have = {int(W["mmsi"][x]): j for j, x in enumerate(st)}
        for m in boxa.tolist():
            sty, sln, simo = span_attr.get(m, (-1, np.nan, 0))
            r = {"event_id": e.event_id, "scenario": scen, "T_utc": datetime.fromtimestamp(T, timezone.utc)
                 .strftime("%Y-%m-%d %H:%M"), "window": w, "mmsi": m, "imo": simo or "",
                 "is_incident": m in inc_mmsi}
            j = have.get(m)
            if j is None:
                r.update(n_pos=0, hours=0.0, dist_km=0.0, ais_type=sty, length_m=sln)
            else:
                x, y = st[j], en[j]
                ty = W["type"][x:y]
                ty = ty[ty > 0]
                ln = W["length"][x:y]
                ln = ln[np.isfinite(ln) & (ln > 0)]
                r.update(n_pos=int(S[j, 0]), hours=round(S[j, 1], 4), dist_km=round(S[j, 2], 3),
                         ais_type=int(np.bincount(ty).argmax()) if len(ty) else sty,
                         length_m=float(np.median(ln)) if len(ln) else sln,
                         med_lat=round(mlat[j], 5), med_lon=round(mlon[j], 5),
                         dist_centre_km=round(float(hav_np(clat, clon, mlat[j], mlon[j])), 3))
                if S[j, 0] >= MIN_POS:
                    r.update({DET[0]: S[j, 3], DET[1]: S[j, 10], DET[2]: gap[j], DET[3]: off[j], DET[4]: ifs[j]})
            r["type_group"] = type_group(r["ais_type"])
            r["candidate_excluded"] = (m in cand_m) or (simo in cand_i)
            rows.append(r)
    df = pd.DataFrame(rows)
    for c in ["med_lat", "med_lon", "dist_centre_km"] + DET:
        if c not in df:
            df[c] = np.nan
    df["d6_tars"] = np.nan
    df["centre_lat"], df["centre_lon"], df["centre_source"] = round(clat, 5), round(clon, 5), csrc
    df["fleet_day"], df["fleet_n"] = ref.day, ref.n_fleet
    for k_, v in ref.thr.items():
        df[k_] = v
    df["after_days_missing"] = ";".join(str(x) for x in days if x in missing)
    df["code_version"] = version
    cols = ["event_id", "scenario", "T_utc", "window", "mmsi", "imo", "is_incident", "candidate_excluded",
            "n_pos", "hours", "dist_km", "ais_type", "type_group", "length_m", "med_lat", "med_lon",
            "dist_centre_km"] + DET + ["d6_tars", "centre_lat", "centre_lon", "centre_source", "fleet_day",
                                       "fleet_n"] + list(ref.thr) + ["after_days_missing", "code_version"]
    for c in DET:
        df[c] = df[c].astype(float).round(6)
    return df[cols], csrc, len(boxa)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=150)
    ap.add_argument("--no-git", action="store_true")
    args = ap.parse_args()
    start = time.time()
    os.makedirs(OUTDIR, exist_ok=True)
    version = git("log", "-1", "--format=%h", "--", "stage_b").stdout.strip()
    ev = pd.read_csv(EVENTS, dtype={"mmsis": str, "imo": str})
    st = load_state()
    todo = scenario_list(ev, st)
    print(f"{len(todo)} event-scenarios to do, code {version}", flush=True)
    order = []  # days in order of first need
    for _, _, _, _, T in todo:
        for d in span_days(T)[0]:
            if d not in order:
                order.append(d)
    order_pos = {d: i for i, d in enumerate(order)}
    cands = candidate_lists()
    buf, refs, missing, procs = {}, {}, set(), {}

    def ensure(d):
        if d in buf or d in missing:
            return
        i = order_pos[d]
        for nd in order[i:i + 4]:  # this day and a prefetch of the next three
            if nd not in buf and nd not in missing and nd not in procs:
                procs[nd] = aisday.start_download(nd)
        p = procs.pop(d)
        rc = 0 if p is None else p.wait()
        path = aisday.raw_path(d)
        if rc == 44:
            missing.add(d)
            print(d, "not on the AIS host (404)", flush=True)
            return
        if rc != 0 or not os.path.exists(path):
            raise RuntimeError(f"download failed {d}")
        t = time.time()
        day = aisday.read_day(path)
        os.remove(path)
        print(f"  read {d}: {len(day['mmsi'])} positions in {time.time() - t:.0f}s", flush=True)
        if len(day["mmsi"]) < MIN_DAY_POS:  # national file nearly empty (data outage)
            missing.add(d)
            st.setdefault("short_days", {})[str(d)] = int(len(day["mmsi"]))
            print(d, "treated as missing: national file has too few positions", flush=True)
            return
        buf[d] = day

    n_done = 0
    for wstart, key, e, scen, T in todo:
        if (time.time() - start) / 60 > args.max_minutes:
            break
        days, req = span_days(T)
        sd = days[0]
        for d in [x for x in buf if x < sd]:
            del buf[d]
        for d in [x for x in refs if x < sd]:
            del refs[d]
        try:
            for d in days:
                ensure(d)
        except RuntimeError as ex:
            print(key, "skipped this run:", ex, flush=True)
            continue
        miss_req = [str(d) for d in req if d in missing]
        if miss_req:
            st["impossible"][key] = f"AIS day(s) not available or nearly empty: {';'.join(miss_req)}"
            save_state(st)
            if not args.no_git:
                commit([STATE], f"B2: {key} impossible (no AIS)")
            print(key, "impossible", miss_req, flush=True)
            continue
        rday = day_of(T - 12 * 3600)
        if rday not in refs:
            t = time.time()
            refs[rday] = FleetRef(buf[rday], rday)
            print(f"  fleet ref {rday}: {refs[rday].n_fleet} vessels, {refs[rday].n_stat} stationary cells, "
                  f"{time.time() - t:.0f}s", flush=True)
        t = time.time()
        df, csrc, nbox = process(key, e, scen, T, buf, refs, missing, cands, version)
        f = os.path.join(OUTDIR, f"{key}.csv.gz")
        df.to_csv(f, index=False, compression={"method": "gzip", "mtime": 0})
        st["done"][key] = {"file": f, "box_vessels": nbox, "rows": len(df), "centre_source": csrc,
                           "fleet_day": str(rday), "code_version": version}
        save_state(st)
        n_done += 1
        print(f"{key}: {nbox} box vessels, centre {csrc}, {time.time() - t:.0f}s "
              f"[{(time.time() - start) / 60:.1f} min, {len(buf)} days in memory]", flush=True)
        if not args.no_git:
            commit([f, STATE], f"B2: window file {key}")
    for d, p in procs.items():
        if p:
            p.terminate()
        for x in (aisday.raw_path(d), aisday.raw_path(d) + ".tmp"):
            if os.path.exists(x):
                os.remove(x)
    print(f"done this run: {n_done}; total done {len(st['done'])}, impossible {len(st['impossible'])}", flush=True)


if __name__ == "__main__":
    main()
