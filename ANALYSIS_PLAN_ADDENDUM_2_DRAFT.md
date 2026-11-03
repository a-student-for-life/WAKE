# Analysis plan addendum 2 (DRAFT, not approved): where incident vessels were the day before

Drafted 3 Nov 2026, after all results for detectors 1-5 and GeoTrackNet were known.
**Status: a draft for Janice's approval. Nothing below has been run.** Once approved, this
file is renamed `ANALYSIS_PLAN_ADDENDUM_2.md` and committed before any code for it runs, and the
results are reported whatever they show.

## Why

Two detectors kept their signal when the window ended 3 hours before T: the off-lane score
(early3 AUC 0.595 on 197 sets) and GeoTrackNet (0.622 on 115 sets). On identical vessels
(`gap_checks/gtn_early3_same_vessels.py`, exploratory) the speed drop, AIS gap and Isolation
Forest lost signal in early3 and these two did not. One explanation is that incident vessels
were already in places with little other traffic before the incident. This addendum tests that
in a window that ends a full day before T.

## What has already been seen

The new window lies inside w48 (T-48 h to T, already reported: off-lane 0.564) and overlaps
early3 by three hours. The test is therefore not independent of results already seen, and the
paper will say so. It is a pre-specified follow-up test, not a confirmation from new data.

## Window

prior24 = [T-48 h, T-24 h), half-open as in Stage B. Same events, same M4 sets (matched on the
main window, unchanged), true date and both placebo dates.

## Measures

- **Primary:** detector 4, off-lane, unchanged (mean over the vessel's positions of
  -log(1 + other vessels in the same 0.01 degree cell that day)); the fleet reference day is
  the UTC day containing T - 36 h. A vessel with fewer than 10 positions in prior24 has no score.
- **Secondary:** GeoTrackNet in prior24 on the 122 events of its 16 regions, with the committed
  models and scoring code unchanged; a vessel with no 6-hour sequence inside the region has no
  score.
- **Descriptive:** distance between each vessel's median prior24 position and the event centre,
  incident vessels against controls (to separate "already at the incident place" from "on an
  unusual route").

## Tests and reading rules

- Primary: pooled AUC on the M4 sets where the incident vessel and at least one control are
  scored; permutation p (10,000, within sets, two-sided), bootstrap interval (5,000 events),
  seed 20261022. One test at alpha 0.05. Reading rules as the plan (useful if p < 0.05 and
  AUC >= 0.60; no useful signal if the interval's upper end is below 0.60; otherwise
  inconclusive).
- Secondary: GeoTrackNet AUC in prior24, and GeoTrackNet minus off-lane on the same vessels with
  a bootstrap of events; placebo30 and placebo60 for both. Not used to read the primary test.

## Code and order of work

1. New script `stage_b2/windows_prior24.py` that imports the Stage B window code unchanged and
   adds only the prior24 window; Stage B files are not changed. It needs the AIS days from
   T-48 h to T-24 h, which the Stage B run already read, downloaded again (about 5-7 hours of
   cloud time for 840 event-scenarios at the measured Stage B pace).
2. GeoTrackNet scoring in prior24 with `gtn/score_region.py` unchanged apart from the window
   bounds (laptop, as phase 3).
3. Analysis script, independent recomputation of the primary AUC, results reported in full.
