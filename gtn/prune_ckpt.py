"""Keep only the latest checkpoint of a region's model directory (before a commit).
usage: python3 gtn/prune_ckpt.py <region>"""
import glob
import os
import re
import sys

d = glob.glob("data/gtn/models/%s/elbo-*" % sys.argv[1])
for m in d:
    steps = sorted({int(re.search(r"ckpt-(\d+)\.", f).group(1)) for f in glob.glob(m + "/model.ckpt-*")})
    for s in steps[:-1]:
        for f in glob.glob(m + "/model.ckpt-%d.*" % s):
            os.remove(f)
    if steps:
        open(m + "/checkpoint", "w").write('model_checkpoint_path: "model.ckpt-%d"\nall_model_checkpoint_paths: "model.ckpt-%d"\n' % (steps[-1], steps[-1]))
        print(m, "kept step", steps[-1])
