"""Rebuild the authors' pickle format from gtn/preprocess.py's compact files.

usage: <gtn python> gtn/unpack.py <region> <out dir>
Each stored row (the even rows of a 5-minute sequence) is written twice, so the authors'
loader, which takes rows [::2], reads exactly the stored rows; the first row carries the
MMSI and start time, the last row the end time. Columns not read by the loader are 0.
"""
import os
import pickle
import sys

import numpy as np

region, out = sys.argv[1], sys.argv[2]
src = "data/gtn/sets/" + region
os.makedirs(out, exist_ok=True)
for part in ("train", "valid"):
    z = np.load("%s/%s_%s.npz" % (src, region, part))
    D, pos = {}, 0
    for k, n in enumerate(z["n"]):
        x = z["x"][pos:pos + n].astype(np.float64)
        pos += n
        v = np.zeros((2 * n, 9))
        v[:, :4] = np.repeat(x, 2, axis=0)
        v[:, 8] = z["mmsi"][k]
        v[:, 7] = z["t0"][k]
        v[-1, 7] = z["t1"][k]
        D[k] = v
    pickle.dump(D, open("%s/%s_%s.pkl" % (out, region, part), "wb"))
pickle.dump(pickle.load(open(src + "/mean.pkl", "rb")), open(out + "/mean.pkl", "wb"))
print(region, "unpacked to", out)
