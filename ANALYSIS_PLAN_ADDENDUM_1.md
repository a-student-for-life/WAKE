# Analysis plan addendum 1: GeoTrackNet as a learned detector

Status: **approved by Janice on 23 Oct 2026**, with two changes agreed that day (the
training stop rule below, and scoring only after the OSF registration). Written 23 Oct 2026. Results of the
main plan already exist (`results/stageB/`); this addendum is logged as DEVIATIONS.md #7 and
everything it produces is reported, whatever it shows.

## Why

Detectors 1-5 are simple versions of common ideas (plan section 8a). Reviewers will ask
whether a published, learned AIS anomaly detector does better. GeoTrackNet (Nguyen et al.,
IEEE T-ITS 2021) is the most widely cited one with public code, and it was built for Marine
Cadastre data. The TARS cascade (planned detector 6) is dropped from the study at Janice's
decision (23 Oct 2026); the paper does not test it.

## Code

The authors' code, `CIA-Oceanix/GeoTrackNet` (TensorFlow 1), run unchanged except for
environment fixes, which are listed in `geotracknet/PATCHES.md` (so far: the `log_dir` flag
clashes with absl's flag of the same name and is guarded). Environment: Python 3.7,
TensorFlow 1.15.5, dm-sonnet 1.36, tensorflow-probability 0.8.0, absl-py 0.9.0, CPU only.
A smoke test on the authors' sample data trained at about 3.8 steps a second.

## Regions

GeoTrackNet learns normal traffic for one fixed region. Regions are the 2 x 3 degree grid
cells (latitude floor(lat/2), longitude floor(lon/3)) of the main-window centre of the 197
matched events, keeping the **16 cells with at least 4 events (122 events)**. Each model's
region is its cell plus a 0.5 degree buffer on every side (3 x 4 degrees), so that most of
each event's 150 km box lies inside it. The cell list is fixed from
`data/stage_b/windows/*_real.csv.gz` centres before any training.

## Training data (normal traffic only)

- Days: 4 per year from 2015 to 2025, drawn with seed 20261022 from all days of the year,
  leaving out any day within 7 days of any incident in `data/incidents.csv` whose reference
  point lies in that region. The same drawn days serve all regions where allowed.
- Vessels: all types (the original paper used cargo and tankers only; our incident vessels
  are mostly tugs, fishing and cargo vessels, so a cargo-only model would not describe them).
- Tracks: the authors' preprocessing (`data/dataset_preprocessing.py`), in its order:
  positions inside the region and at most 30 kn; tracks split at gaps over 2 hours; tracks
  with fewer than 20 messages or shorter than 4 hours removed; outlier messages removed
  (`utils.detectOutlier`); interpolated every 5 minutes; split into sequences of at most
  24 hours, keeping those of at least 4 hours; sequences more than 70% moored or at anchor
  (navigational status 5 or 1), with top speed under 1 kn, or more than 80% below 2 kn
  removed; latitude, longitude, speed and course normalised to the region. Navigational
  status comes from the Marine Cadastre status field (text values mapped to the AIS codes).
  Mean four-hot vector from `data/calculate_AIS_mean.py`.
- 90% of tracks for training, 10% held out for the validation ELBO, split by MMSI.

## Model and training

Paper settings: latent size 100, batch 32, 16 samples, learning rate 0.0003, ELBO bound,
one-hot resolution 0.01 degree, 1 kn, 5 degrees. The validation ELBO (per time step) is
computed every 1,000 steps. **Stop rule:** training stops at the first check, at or after
20,000 steps, where the validation ELBO has improved by less than 0.5% of its absolute
value over the last 5,000 steps; it stops at 60,000 steps in any case (the code default is
80,000). The checkpoint at the stopping step is used. The rule is applied mechanically and
the curves are reported; nothing else is tuned. If a region's training fails twice, that
region is dropped and counted.

## Scoring

For every vessel in a matched set (M4, the sets already built; no new matching), the part
of its track inside the model's region in the window is preprocessed with the same cleaning
steps (region, speed, 2-hour gap split, outlier removal, 5-minute interpolation, sequences
of at least 4 hours). The three track-removal filters (moored, top speed under 1 kn, mostly
below 2 kn) are not applied at scoring, so that slow vessels are scored rather than dropped.
Each sequence is scored, and a vessel's score in a window is that of its most anomalous
sequence:

- per position, the model's log-probability (mean over the 16 particles), compared with
  the kernel density of log-probabilities of the held-out normal-traffic tracks in the same
  0.1 degree cell (`local_logprob` mode, outliers removed with `utils.remove_gaussian_outlier`);
  a position is abnormal if its value is below the 10th percentile of that density, or if its
  cell holds fewer than 2 values (both as in the authors' `contrario_detection` mode); the
  first 12 time steps of a sequence are skipped as in the authors' code;
- the authors' a-contrario test over sliding windows of 24 time steps
  (`contrario_utils.NFA`, with p = 0.1 and the factor 300);
- **score (primary)** = -log10 of the smallest number of false alarms (NFA) over all windows
  and sub-segments of the vessel's sequences; higher = more anomalous;
- **flag** = the paper's decision, smallest NFA below epsilon = 1e-9 (the code default).

The authors' test skips the first 12 time steps (2 hours at the 10-minute steps the model
reads) and then needs a full 24-step window, so a sequence shorter than 6 hours cannot be
tested and counts as not scored. A vessel with no sequence of at least 6 hours inside the
region in that window gets no score,
as for detectors 1-5 with fewer than 10 positions. Windows: main, early3, w6; dates: true,
placebo30, placebo60.

## Tests and reading rules

- Main: pooled AUC on the M4 sets (true date, main window) of the 122 events where the
  incident vessel and at least one control are scored; permutation p (10,000), bootstrap
  interval (5,000), seed 20261022. GeoTrackNet is one pre-specified test at alpha 0.05,
  outside the Holm family of detectors 1-5.
- Reading rules as plan section 6: useful if p < 0.05 and AUC >= 0.60; no useful signal if
  the interval's upper end is below 0.60; otherwise inconclusive.
- Same-subset comparison: detectors 1-5 recomputed on exactly the sets GeoTrackNet scores,
  and the paired difference GeoTrackNet minus each, with a bootstrap of events.
- Supporting, as plan section 7: flag rate (the 1e-9 decision) by conditional logistic
  regression; early3 and w6 windows; placebo30 and placebo60 on the sets that exist.

## Order of work

Training uses only normal-traffic days and may start at once. Scoring of incident vessels
and their controls starts only after this addendum, `ANALYSIS_PLAN.md` and `DEVIATIONS.md`
are registered on OSF; the registration link is added here when it exists.

## Compute and schedule

Scheduled cloud sessions with the Stage B session lock (`RUNNING.md`), committing after
every finished region or event: (1) training-data extraction, one pass over the 44 drawn
national days, about 1 hour; (2) training, 16 regions x about 2-4 hours; (3) scoring, one
pass over the AIS days of the scored event-scenarios, about 6 hours; (4) analysis. Commits
as Janice Miranda, no attribution lines. Raw AIS deleted after use.

## What changes in the paper

A seventh table and one figure row: GeoTrackNet against the five simple detectors on the
same 122 events. The conclusion is rewritten only as far as the GeoTrackNet result requires.
