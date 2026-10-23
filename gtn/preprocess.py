"""GeoTrackNet addendum: the authors' preprocessing for one region (run with the GeoTrackNet
Python 3.7 environment, from any directory).

usage: <gtn python> gtn/preprocess.py <region> <GeoTrackNet dir>
reads  data/raw/gtn/<region>/*.npz (gtn/extract_train.py), data/gtn/regions.csv
writes data/gtn/sets/<region>/<region>_train.npz, <region>_valid.npz (compact; gtn/unpack.py
       rebuilds the authors' pickle format), mean.pkl, prep_counts.json

Follows GeoTrackNet data/dataset_preprocessing.py step by step (same order, thresholds and
utils.detectOutlier / utils.interpolate), with the region as ROI. Training/validation split
90/10 by MMSI (seed 20261022). The four-hot mean is computed with the formula of
data/calculate_AIS_mean.py, using the region's bin counts (0.01 deg, 1 kn, 5 deg).
"""
import csv
import glob
import json
import math
import os
import pickle
import sys

import numpy as np

region, gdir = sys.argv[1], sys.argv[2]
sys.path.insert(0, gdir)
import utils  # noqa: E402  (GeoTrackNet utils)

LAT, LON, SOG, COG, HEADING, ROT, NAV_STT, TIMESTAMP, MMSI = list(range(9))
R = [r for r in csv.DictReader(open("data/gtn/regions.csv")) if r["region"] == region][0]
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = (float(R[k]) for k in ("lat_min", "lat_max", "lon_min", "lon_max"))
SPEED_MAX = 30.0
DURATION_MAX = 24
OUT = "data/gtn/sets/" + region
os.makedirs(OUT, exist_ok=True)
cnt = {}

# load: one dict per day file, keyed by MMSI (as the authors' per-file dicts)
Vs = dict()
files = sorted(glob.glob("data/raw/gtn/%s/*.npz" % region))
cnt["day_files"] = len(files)
for fn in files:
    m = np.load(fn)["m"]
    if len(m) == 0:
        continue
    m = m[(m[:, LAT] <= LAT_MAX) & (m[:, LAT] >= LAT_MIN) & (m[:, LON] <= LON_MAX) & (m[:, LON] >= LON_MIN)]
    m = m[m[:, SOG] <= SPEED_MAX]
    ids, start = np.unique(m[:, MMSI], return_index=True)
    for k, mm in zip(np.split(m, start[1:]), ids):
        if mm in Vs:
            Vs[mm] = np.concatenate((Vs[mm], k), axis=0)
        else:
            Vs[mm] = k
for mm in Vs:
    Vs[mm] = Vs[mm][np.argsort(Vs[mm][:, TIMESTAMP], kind="mergesort")]
cnt["vessels"] = len(Vs)

voyages, count = dict(), 0
for mm in list(Vs.keys()):
    v = Vs[mm]
    idx = np.where((v[1:, TIMESTAMP] - v[:-1, TIMESTAMP]) > 2 * 3600)[0]
    for t in (np.split(v, idx + 1) if len(idx) else [v]):
        voyages[count] = t
        count += 1
del Vs
for k in list(voyages.keys()):
    if len(voyages[k]) < 20 or (voyages[k][-1, TIMESTAMP] - voyages[k][0, TIMESTAMP]) < 4 * 3600:
        voyages.pop(k, None)
cnt["voyages_4h"] = len(voyages)

err = 0
for k in list(voyages.keys()):
    track = voyages[k][:, [TIMESTAMP, LAT, LON, SOG]]
    try:
        o_report, o_calcul = utils.detectOutlier(track, speed_max=30)
        if o_report.all() or o_calcul.all():
            voyages.pop(k, None)
        else:
            voyages[k] = voyages[k][np.invert(o_report)]
            voyages[k] = voyages[k][np.invert(o_calcul)]
    except Exception:
        voyages.pop(k, None)
        err += 1
cnt["after_outliers"], cnt["outlier_errors"] = len(voyages), err

Vs, count = dict(), 0
for k in list(voyages.keys()):
    v = voyages[k]
    samp = []
    for t in range(int(v[0, TIMESTAMP]), int(v[-1, TIMESTAMP]), 300):
        tmp = utils.interpolate(t, v)
        if tmp is None:
            samp = None
            break
        samp.append(tmp)
    if samp:
        Vs[count] = np.vstack(samp)
        count += 1
del voyages

Data, count = dict(), 0
for k in list(Vs.keys()):
    v = Vs[k]
    for sub in np.split(v, np.arange(0, len(v), 12 * DURATION_MAX)[1:]):
        if len(sub) >= 12 * 4:
            Data[count] = sub
            count += 1
cnt["sequences"] = len(Data)
for k in list(Data.keys()):
    L = float(len(Data[k]))
    if np.count_nonzero(Data[k][:, NAV_STT] == 1) / L > 0.7 or np.count_nonzero(Data[k][:, NAV_STT] == 5) / L > 0.7 \
            or np.max(Data[k][:, SOG]) < 1.0:
        Data.pop(k, None)
cnt["after_moored"] = len(Data)
for k in list(Data.keys()):
    if np.count_nonzero(Data[k][:, SOG] < 2) / float(len(Data[k])) > 0.8:
        Data.pop(k, None)
cnt["after_low_speed"] = len(Data)
for k in list(Data.keys()):
    v = Data[k]
    v[:, LAT] = (v[:, LAT] - LAT_MIN) / (LAT_MAX - LAT_MIN)
    v[:, LON] = (v[:, LON] - LON_MIN) / (LON_MAX - LON_MIN)
    v[:, SOG][v[:, SOG] > SPEED_MAX] = SPEED_MAX
    v[:, SOG] = v[:, SOG] / SPEED_MAX
    v[:, COG] = v[:, COG] / 360.0

mmsis = sorted(set(int(Data[k][0, MMSI]) for k in Data))
rng = np.random.RandomState(20261022 % (2 ** 32))
val = set(rng.choice(mmsis, max(1, int(round(0.1 * len(mmsis)))), replace=False).tolist())
train = {i: v for i, v in enumerate(v for k, v in Data.items() if int(v[0, MMSI]) not in val)}
valid = {i: v for i, v in enumerate(v for k, v in Data.items() if int(v[0, MMSI]) in val)}
cnt.update(train_sequences=len(train), valid_sequences=len(valid), train_mmsi=len(mmsis) - len(val),
           valid_mmsi=len(val))


def compact(D, path):
    # The authors' loader (data/datasets.py) reads raw_data[k][::2, [LAT, LON, SOG, COG]] and the
    # first MMSI, first and last TIMESTAMP of each sequence; nothing else. Store exactly that.
    rows = [D[k][::2, [LAT, LON, SOG, COG]].astype(np.float32) for k in range(len(D))]
    np.savez_compressed(path, x=np.concatenate(rows) if rows else np.zeros((0, 4), np.float32),
                        n=np.array([len(r) for r in rows], np.int32),
                        full_len=np.array([len(D[k]) for k in range(len(D))], np.int32),
                        mmsi=np.array([int(D[k][0, MMSI]) for k in range(len(D))], np.int64),
                        t0=np.array([D[k][0, TIMESTAMP] for k in range(len(D))], np.float64),
                        t1=np.array([D[k][-1, TIMESTAMP] for k in range(len(D))], np.float64))


compact(train, OUT + "/%s_train.npz" % region)
compact(valid, OUT + "/%s_valid.npz" % region)

# four-hot mean, formula of data/calculate_AIS_mean.py with this region's bins
lat_bins = math.ceil((LAT_MAX - LAT_MIN) / 0.01)
lon_bins = math.ceil((LON_MAX - LON_MIN) / 0.01)
sog_bins, cog_bins = math.ceil(SPEED_MAX / 1), math.ceil(360 / 5)
s = np.zeros(lat_bins + lon_bins + sog_bins + cog_bins)
n = 0
for k in train:
    tmp = train[k][:, [LAT, LON, SOG, COG]].copy()
    tmp[tmp == 1] = 0.99999
    np.add.at(s, (tmp[:, 0] * lat_bins).astype(int), 1)
    np.add.at(s, (tmp[:, 1] * lon_bins).astype(int) + lat_bins, 1)
    np.add.at(s, (tmp[:, 2] * sog_bins).astype(int) + lat_bins + lon_bins, 1)
    np.add.at(s, (tmp[:, 3] * cog_bins).astype(int) + lat_bins + lon_bins + sog_bins, 1)
    n += len(tmp)
pickle.dump(s / n, open(OUT + "/mean.pkl", "wb"))
json.dump(cnt, open(OUT + "/prep_counts.json", "w"), indent=1)
print(region, cnt)
