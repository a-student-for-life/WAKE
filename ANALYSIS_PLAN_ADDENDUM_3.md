# Analysis plan addendum 3: when within the last day the signal appears

Drafted 15 Nov 2026, after all results for detectors 1-5, GeoTrackNet, the NTSB comparison, the
Hawaii check and addendum 2 (prior24) were known.
**Status: approved by Janice on 15 Nov 2026**, unchanged from the draft committed in b3b2fd9e,
before any code for it was written or run; and its results are reported whatever they show.

## Why

The speed drop loses most of its signal when the last three hours are removed, the off-lane score
keeps it (early3 0.595), and a day earlier neither has any (prior24, off-lane 0.520). This
addendum asks where within the 24 hours before T the signal appears, using four separate 6-hour
slices instead of overlapping windows, so that each slice contains only its own hours.

## What has already been seen

The slices partition the main window, whose results are known. The last slice equals w6, which
is already reported for all events. The NRC-timed subset was reported by source in the main
analysis. These tests are therefore not independent of results already seen; the paper will
call them a pre-specified follow-up, not a confirmation from new data.

## Events

The events in the main analysis with an M4 set on the true date and an NRC report time
(T_rule `nrc_time_utc` or `nrc_local_tz_from_ais`): 120 events. IncidentNews events are left out
because their T is local midnight of a date, an error larger than one slice. True date only.

## Windows

s24 = [T-24 h, T-18 h), s18 = [T-18 h, T-12 h), s12 = [T-12 h, T-6 h), s6 = [T-6 h, T),
half-open as in Stage B. The main window [T-24 h, T) is recomputed in the same run as a check
that the run reproduces the published main-window values for these events.

## Measures

Detectors 1-5 unchanged, computed by the unchanged Stage B window code on each slice; fleet
reference day and thresholds as in the main window (UTC day containing T-12 h). A vessel with
fewer than 10 positions in a slice has no score in that slice. Matched sets: the published M4
sets (matched on the main window), unchanged.

## Tests and reading rules

- **Primary (one test):** off-lane AUC in s24, the slice 18-24 hours before T, on the M4 sets in
  which the incident vessel and at least one control are scored. Permutation p (10,000, within
  sets, two-sided), bootstrap interval (5,000 events), seed 20261022, alpha 0.05. Reading rules
  as the plan: useful if p < 0.05 and AUC >= 0.60; no useful signal if the interval's upper end
  is below 0.60; otherwise inconclusive.
- **Descriptive:** pooled AUC with bootstrap intervals for all five detectors in all four slices;
  for each detector, s6 minus s24 with a bootstrap interval over events (sets scored in both).
- **Conditional:** placebo30 for the off-lane score in s24 is run only if the primary result is
  "useful"; otherwise it has nothing to check and is not run.
- GeoTrackNet is not scored (its environment is not available here).

## Code and order of work

1. `stage_b3/windows_slices.py`: runs the unchanged `stage_b/windows.py` with WINDOWS set to
   main, s24, s18, s12 and s6 and SPAN (-24, 0), on the 120 events. Re-downloads the AIS days
   of the main window (about 1.5 hours of cloud time at the prior24 pace).
2. `stage_b3/analyse_slices.py`: the tests above, an independent recomputation of the primary AUC,
   and the main-window reproduction check.
3. Results reported in full in the paper and in `results/stage_b3/`; deviations logged.
