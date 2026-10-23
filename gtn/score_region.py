"""GeoTrackNet addendum: score one region's prepared sequences (after training is DONE).

usage: python3 gtn/score_region.py <region> --gdir <GeoTrackNet dir> --py <GeoTrackNet python> --sets <dir>
Steps, all with the authors' code:
1. geotracknet.py --mode=save_logprob on the validation set, then --mode=local_logprob
   (per-cell log-probabilities of held-out normal tracks, 0.1 degree cells);
2. the region's score sequences (data/gtn/score/<region>/*.npz) written in the authors' pickle
   format, with a running index in the MMSI column (mapped back afterwards), then
   --mode=save_logprob on them;
3. gtn/contrario_score.py: per position abnormal if below the 10th percentile of the cell's
   kernel density (or the cell has < 2 values), first 12 steps skipped, the authors' NFA over
   24-step windows; score = -log10(smallest NFA), flag = smallest NFA < 1e-9.
Writes data/gtn/scores/<region>.csv.
"""
import argparse
import csv
import glob
import os
import pickle
import subprocess

import numpy as np

A = argparse.ArgumentParser()
A.add_argument("region")
A.add_argument("--gdir", required=True)
A.add_argument("--py", required=True)
A.add_argument("--sets", required=True)
a = A.parse_args()
reg = a.region
R = [r for r in csv.DictReader(open("data/gtn/regions.csv")) if r["region"] == reg][0]
mdir = os.path.abspath("data/gtn/models/" + reg)
assert os.path.exists(mdir + "/DONE.json"), "training not done"
FLAGS = ["--dataset_dir=" + os.path.abspath(a.sets), "--trainingset_name=%s/%s_train.pkl" % (reg, reg),
         "--lat_min=" + R["lat_min"], "--lat_max=" + R["lat_max"], "--lon_min=" + R["lon_min"],
         "--lon_max=" + R["lon_max"], "--latent_size=100", "--batch_size=32", "--num_samples=16",
         "--learning_rate=0.0003", "--log_dir=" + mdir]

# 2. score set in the authors' format
key, D, i = [], {}, 0
for f in sorted(glob.glob("data/gtn/score/%s/*.npz" % reg)):
    ev, sc = os.path.basename(f)[:-4].split("_")
    z = np.load(f)
    pos = 0
    for k, n in enumerate(z["n"]):
        x = z["x"][pos:pos + n].astype(np.float64)
        pos += n
        v = np.zeros((2 * n, 9))
        v[:, :4] = np.repeat(x, 2, axis=0)
        v[:, 8] = i
        D[i] = v
        key.append((int(ev), sc, str(z["window"][k]), int(z["mmsi"][k]), int(z["full_len"][k])))
        i += 1
pickle.dump(D, open("%s/%s/%s_score.pkl" % (a.sets, reg, reg), "wb"))
print(reg, len(D), "score sequences")


def run(mode, test):
    subprocess.run([a.py, "geotracknet.py", "--mode=" + mode, "--testset_name=%s/%s" % (reg, test)] + FLAGS,
                   cwd=a.gdir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


run("save_logprob", reg + "_valid.pkl")
run("local_logprob", reg + "_valid.pkl")
run("save_logprob", reg + "_score.pkl")
mp = glob.glob(os.path.join(a.gdir, "results", reg, "local_logprob-*%s_valid*" % reg, "Map_logprob-0.1-0.1.pkl"))
lp = glob.glob(os.path.join(a.gdir, "results", reg, "logprob-%s_train.pkl-%s_score.pkl-*.pkl" % (reg, reg)))
assert len(mp) == 1 and len(lp) == 1, (mp, lp)
out = "data/gtn/scores/%s.csv" % reg
os.makedirs(os.path.dirname(out), exist_ok=True)
keyf = "data/gtn/scores/%s_key.pkl" % reg
pickle.dump(key, open(keyf, "wb"))
subprocess.run([a.py, os.path.abspath("gtn/contrario_score.py"), mp[0], lp[0], keyf, out, R["lat_min"], R["lat_max"],
                R["lon_min"], R["lon_max"]], cwd=a.gdir, check=True)
os.remove(keyf)
