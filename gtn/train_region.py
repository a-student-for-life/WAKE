"""GeoTrackNet addendum: train one region with the stop rule (ANALYSIS_PLAN_ADDENDUM_1.md).

usage: python3 gtn/train_region.py <region> --gdir <GeoTrackNet dir> --py <GeoTrackNet python>
       --sets <unpacked sets dir> --max-minutes <budget>
Trains in chunks of 1,000 steps with the authors' `geotracknet.py --mode=train` (resuming from
the checkpoint), and after each chunk computes the held-out bound per time step
(gtn/eval_valid.py), appended to data/gtn/models/<region>/curve.csv.
Stop rule: at the first check at or after 20,000 steps where the bound improved by less than
0.5% of its absolute value over the last 5,000 steps, or at 60,000 steps. Writes DONE.json.
Stops early (resumable) when the time budget is used.
"""
import argparse
import csv
import json
import os
import subprocess
import time

A = argparse.ArgumentParser()
A.add_argument("region")
A.add_argument("--gdir", required=True)
A.add_argument("--py", required=True)
A.add_argument("--sets", required=True)
A.add_argument("--max-minutes", type=float, default=150)
a = A.parse_args()
start = time.time()
R = [r for r in csv.DictReader(open("data/gtn/regions.csv")) if r["region"] == a.region][0]
mdir = os.path.abspath("data/gtn/models/" + a.region)
os.makedirs(mdir, exist_ok=True)
curve = os.path.join(mdir, "curve.csv")
done = os.path.join(mdir, "DONE.json")
FLAGS = ["--dataset_dir=" + os.path.abspath(a.sets), "--trainingset_name=%s/%s_train.pkl" % (a.region, a.region),
         "--lat_min=" + R["lat_min"], "--lat_max=" + R["lat_max"], "--lon_min=" + R["lon_min"],
         "--lon_max=" + R["lon_max"], "--latent_size=100", "--batch_size=32", "--num_samples=16",
         "--learning_rate=0.0003", "--log_dir=" + mdir, "--random_seed=20261022", "--summarize_every=500"]


def rows():
    return [(int(r["step"]), float(r["valid_ll_per_t"])) for r in csv.DictReader(open(curve))] if os.path.exists(curve) else []


def stop_check(c):
    s, v = c[-1]
    if s >= 60000:
        return "max 60,000 steps"
    if s >= 20000:
        prev = [x for x in c if x[0] <= s - 5000]
        if prev:
            imp = v - prev[-1][1]
            if imp < 0.005 * abs(v):
                return "improvement %.4f < 0.5%% of |%.4f| over 5,000 steps" % (imp, v)
    return None


if os.path.exists(done):
    print(a.region, "already done"); raise SystemExit
while True:
    c = rows()
    last = c[-1][0] if c else 0
    if (time.time() - start) / 60 > a.max_minutes - 8:
        print("time budget used; resumable at step", last); break
    target = (last // 1000 + 1) * 1000
    t0 = time.time()
    subprocess.run([a.py, "geotracknet.py", "--mode=train", "--max_steps=%d" % (target - 1)] + FLAGS,
                   cwd=a.gdir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t1 = time.time()
    r = subprocess.run([a.py, os.path.abspath("gtn/eval_valid.py"), "--mode=eval_valid",
                        "--testset_name=%s/%s_valid.pkl" % (a.region, a.region)] + FLAGS,
                       cwd=a.gdir, check=True, capture_output=True, text=True)
    line = [l for l in r.stdout.splitlines() if l.startswith("VALID")][-1].split()
    step, ll, n = int(line[1]), float(line[2]), int(line[3])
    new = not os.path.exists(curve)
    with open(curve, "a") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["step", "valid_ll_per_t", "n_valid", "train_sec", "eval_sec"])
        w.writerow([step, "%.5f" % ll, n, int(t1 - t0), int(time.time() - t1)])
    print(a.region, step, ll, "train %.0fs eval %.0fs" % (t1 - t0, time.time() - t1), flush=True)
    why = stop_check(rows())
    if why:
        json.dump({"region": a.region, "stop_step": step, "valid_ll_per_t": ll, "reason": why}, open(done, "w"), indent=1)
        print(a.region, "DONE", why); break
