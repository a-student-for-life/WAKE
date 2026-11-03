# GeoTrackNet: reporting decisions fixed before phase 4

Written 2026-11-03, after phases 1-3 finished and **before any GeoTrackNet score was opened,
printed or summarised** (the score CSVs in `data/gtn/scores/` have only been checked to exist).
These decisions only fix how already-produced results are reported. Nothing in the addendum's
models, settings, main test or reading rules changes, and per the addendum ("Order of work") no
model or setting can change now that incident vessels are scored.

## 1. R14 and R15: validation declining at the stop

Both regions stopped at the first stop check (20,000 steps) because the held-out bound per step
got worse over the previous 5,000 steps, which the rule treats as "improvement under 0.5%".

| Region | Events | Best held-out bound (step) | At stop (20,000) |
| --- | --- | --- | --- |
| R14 | 4 (11, 28, 38, 74) | -8.779 (9,000) | -9.682 |
| R15 | 4 (25, 27, 53, 155) | -10.081 (8,000) | -10.954 |

Both curves fall steadily from their best point to step 20,000, consistent with overfitting on the
two smallest training sets; the 20,000-step minimum of the stop rule kept them training past the
peak. (Curves: `data/gtn/models/R14/curve.csv`, `R15/curve.csv`.)

Decision:
- **Main analysis unchanged**: R14 and R15 stay in, with their committed (step-20,000) models,
  exactly as the addendum specifies.
- **Reported**: both curves and this note, in the methods or supplement.
- **Descriptive sensitivity only**: the main pooled AUC also computed without the events of
  R14 and R15. It is reported next to the main result, is not a separate test, and is not used by
  the reading rules.

## 2. One national AIS day missing

After the one-time retry (`data/gtn/score_retry.json`), one day could still not be read:
2015-03-15. It affects one event-scenario, **R08/203_real** (11 vessels), whose T-27 h..T window
was prepared without that day.

Decision:
- **Main analysis unchanged**: R08/203_real stays in, as the addendum's handling of missing days
  implies.
- **Reported**: listed as scored with one day of AIS missing.
- **Descriptive sensitivity only**: the main pooled AUC also computed without event 203. Same
  status as above: reported, not a test, not used by the reading rules.

## 3. Where and how phases 1-3 ran (methods sentence)

Phase 1: R01 steps 0-45,000 on the cloud scheduled sessions; all other training on Janice's
laptop (WSL2, AMD Ryzen 7 250, CPU only) with the same pinned environment (`gtn/setup_env.sh`,
TensorFlow 1.15.5, GeoTrackNet commit 7797b16a with `gtn/geotracknet_compat.patch`). Phases 2-3 on
the same laptop. One code change: `gtn/score_region.py` path fix (commit 976d8a37) after the first
phase-3 attempt failed before writing any score; it does not affect how scores are computed.

## 4. Phase 4

Phase 4 (Opus) implements the addendum's "Tests and reading rules" unchanged, plus the two
descriptive sensitivity numbers above, clearly labelled as such.
