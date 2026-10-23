"""Mean held-out bound per time step for the latest checkpoint (run inside the GeoTrackNet
directory with the GeoTrackNet Python, same flags as training plus --testset_name=<valid>).

Uses the authors' graph: runners.create_dataset_and_model (no shuffle, no repeat) and
runners.create_eval_graph (bound 'elbo', config.num_samples particles); prints
'VALID <global step> <mean ll per time step over all validation sequences>'.
"""
import os
import sys

sys.path.insert(0, os.getcwd())  # the GeoTrackNet directory (run from there)

import numpy as np
import tensorflow as tf

import flags_config  # parses the command-line flags
import runners

config = flags_config.config
with tf.Graph().as_default():
    global_step = tf.train.get_or_create_global_step()
    inputs, targets, mmsis, ts, te, lengths, model = runners.create_dataset_and_model(config, shuffle=False, repeat=False)
    out = runners.create_eval_graph(inputs, targets, lengths, model, config)
    ll_per_t = out[3]
    saver = tf.train.Saver()
    vals = []
    with tf.train.SingularMonitoredSession() as sess:
        if not runners.restore_checkpoint_if_exists(saver, sess, config.logdir):
            sys.exit("no checkpoint")
        step = sess.run(global_step)
        while not sess.should_stop():
            try:
                vals.extend(np.ravel(sess.run(ll_per_t)).tolist())
            except tf.errors.OutOfRangeError:
                break
print("VALID", step, float(np.mean(vals)), len(vals))
