"""Scoring preprocessing for one event-scenario (GeoTrackNet Python).

usage: <gtn python> gtn/score_seqs.py <region> <raw npz> <out npz> <GeoTrackNet dir>
Per window (main T-24h..T, early3 T-27h..T-3h, w6 T-6h..T) and vessel: positions in the window
and region at most 30 kn; split at gaps over 2 h; pieces with fewer than 20 messages or
shorter than 4 h dropped; utils.detectOutlier; utils.interpolate every 5 minutes; split into
sequences of at most 24 h keeping those of at least 4 h; normalised to the region. The
moored / top-speed / low-speed removal filters are NOT applied (addendum, Scoring).
Output: compact arrays like gtn/preprocess.py plus window and vessel per sequence.
"""
import csv
import sys

import numpy as np

region, rawf, outf, gdir = sys.argv[1:5]
sys.path.insert(0, gdir)
import utils  # noqa: E402

LAT, LON, SOG, COG, HEADING, ROT, NAV_STT, TIMESTAMP, MMSI = list(range(9))
R = [r for r in csv.DictReader(open("data/gtn/regions.csv")) if r["region"] == region][0]
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = (float(R[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max"))
z = np.load(rawf)
m, T = z["m"], float(z["T"])
WIN = {"main": (-24, 0), "early3": (-27, -3), "w6": (-6, 0)}
rows, n, full, win, mmsis, t0s, t1s = [], [], [], [], [], [], []
for w, (a, b) in WIN.items():
    x = m[(m[:, TIMESTAMP] >= T + a * 3600) & (m[:, TIMESTAMP] < T + b * 3600) & (m[:, SOG] <= 30)]
    for mm in np.unique(x[:, MMSI]):
        v = x[x[:, MMSI] == mm]
        v = v[np.argsort(v[:, TIMESTAMP], kind="mergesort")]
        idx = np.where((v[1:, TIMESTAMP] - v[:-1, TIMESTAMP]) > 2 * 3600)[0]
        for piece in (np.split(v, idx + 1) if len(idx) else [v]):
            if len(piece) < 20 or piece[-1, TIMESTAMP] - piece[0, TIMESTAMP] < 4 * 3600:
                continue
            try:
                o_r, o_c = utils.detectOutlier(piece[:, [TIMESTAMP, LAT, LON, SOG]], speed_max=30)
                if o_r.all() or o_c.all():
                    continue
                piece = piece[np.invert(o_r)]
                piece = piece[np.invert(o_c)]
            except Exception:
                continue
            samp = []
            for t in range(int(piece[0, TIMESTAMP]), int(piece[-1, TIMESTAMP]), 300):
                s = utils.interpolate(t, piece)
                if s is None:
                    samp = None
                    break
                samp.append(s)
            if not samp:
                continue
            sv = np.vstack(samp)
            for sub in np.split(sv, np.arange(0, len(sv), 12 * 24)[1:]):
                if len(sub) < 12 * 4:
                    continue
                q = sub.copy()
                q[:, LAT] = (q[:, LAT] - LAT_MIN) / (LAT_MAX - LAT_MIN)
                q[:, LON] = (q[:, LON] - LON_MIN) / (LON_MAX - LON_MIN)
                q[:, SOG] = np.minimum(q[:, SOG], 30) / 30.0
                q[:, COG] = q[:, COG] / 360.0
                q = np.clip(q, 0, 0.99999)
                r = q[::2, [LAT, LON, SOG, COG]].astype(np.float32)
                rows.append(r); n.append(len(r)); full.append(len(q)); win.append(w)
                mmsis.append(int(mm)); t0s.append(sub[0, TIMESTAMP]); t1s.append(sub[-1, TIMESTAMP])
np.savez_compressed(outf, x=np.concatenate(rows) if rows else np.zeros((0, 4), np.float32),
                    n=np.array(n, np.int32), full_len=np.array(full, np.int32), window=np.array(win),
                    mmsi=np.array(mmsis, np.int64), t0=np.array(t0s), t1=np.array(t1s))
print(outf, len(n), "sequences")
