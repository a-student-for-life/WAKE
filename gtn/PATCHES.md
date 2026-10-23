# Changes to the authors' GeoTrackNet code

Code: https://github.com/CIA-Oceanix/GeoTrackNet, commit 7797b16a2fafcf273ff0249eb51add1f52c16ce3
(5 Oct 2020), run with Python 3.7 and the packages in `requirements-gtn37.txt`
(TensorFlow 1.15.5, dm-sonnet 1.36, tensorflow-probability 0.8.0, absl-py 0.9.0).

1. `flags_config.py`: the flag `log_dir` is also defined by absl's logging module in these
   package versions, which stops the program at start-up. The patch keeps the authors' flag
   and default when absl has already defined it (`geotracknet_compat.patch`). No change to
   the model, training, data pipeline or detection code.

Our own code around it (`gtn/`): data extraction and the authors' preprocessing steps
(`preprocess.py`), the compact storage and its exact unpacking (`unpack.py`), the training
driver with the stop rule (`train_region.py`), the held-out bound (`eval_valid.py`, built
from `runners.create_eval_graph`), and scoring (`score_prep.py`, `score_seqs.py`,
`score_region.py`, `contrario_score.py`, which calls `contrario_utils.NFA`).
