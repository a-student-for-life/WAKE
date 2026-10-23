"""Smallest a-contrario NFA per scored sequence, with the authors' rules (run inside the
GeoTrackNet directory with its Python).

usage: contrario_score.py <Map_logprob pkl> <save_logprob pkl> <key pkl> <out csv> lat_min lat_max lon_min lon_max
Per position (from step 12): abnormal if the KDE cdf of its cell's held-out log-probabilities
at the position's value is < 0.1, or the cell has < 2 values (as contrario_detection mode).
Over every 24-step window and every sub-segment, NFA = contrario_utils.NFA(length, #abnormal);
score = -log10(min NFA) (min NFA floored at 1e-300); flag = min NFA < 1e-9. Sequences with
fewer than 24 steps after the first 12 are not scored (the authors' loop never tests them).
Output: one row per vessel and window (most anomalous sequence), plus sequence counts.
"""
import csv
import math
import pickle
import sys

import numpy as np
from scipy import stats

import contrario_utils

mapf, lpf, keyf, outf = sys.argv[1:5]
lat_min, lat_max, lon_min, lon_max = map(float, sys.argv[5:9])
lat_bins = math.ceil((lat_max - lat_min) / 0.01)
Map = pickle.load(open(mapf, "rb"))
L = pickle.load(open(lpf, "rb"))
key = pickle.load(open(keyf, "rb"))
kde = {}
NFA_T = {ns: [contrario_utils.NFA(ns, k) for k in range(ns + 1)] for ns in range(1, 25)}
best = {}
for D in L:
    idx = int(D["mmsi"])
    ev, sc, win, mmsi, _ = key[idx]
    seq, lw = D["seq"], D["log_weights"]
    vA = np.zeros(len(seq))
    for t in range(12, len(seq)):
        row = int(seq[t, 0] * 0.01 / 0.1)
        col = int((seq[t, 1] - lat_bins) * 0.01 / 0.1)
        vals = Map.get("%d,%d" % (row, col), [])
        if len(vals) < 2:
            vA[t] = 2
            continue
        k = "%d,%d" % (row, col)
        if k not in kde:
            kde[k] = stats.gaussian_kde(vals)
        if kde[k].integrate_box_1d(-np.inf, float(np.mean(lw[t, :]))) < 0.1:
            vA[t] = 1
    vA = vA[12:]
    if len(vA) < 24:  # the authors' sliding 24-step test never runs: not scored
        continue
    nz = np.concatenate([[0], np.cumsum(vA != 0)])
    mn = np.inf
    for ns in range(1, 25):  # every segment of up to 24 steps lies inside some 24-step window
        k = nz[ns:] - nz[:-ns]
        mn = min(mn, min(NFA_T[ns][int(x)] for x in np.unique(k)))
    b = best.setdefault((ev, sc, win, mmsi), [np.inf, 0])
    b[0] = min(b[0], mn)
    b[1] += 1
with open(outf, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["event_id", "scenario", "window", "mmsi", "n_sequences", "min_nfa", "d7_gtn", "gtn_flag"])
    for (ev, sc, win, mmsi), (mn, n) in sorted(best.items()):
        w.writerow([ev, sc, win, mmsi, n, "%.6g" % mn, "%.6f" % -math.log10(max(mn, 1e-300)), int(mn < 1e-9)])
print(outf, len(best), "vessel-windows")
