# Gap-closing checks (23 Oct 2026, after Stage B)

Run after the Stage B results existed. Check 1 was pre-registered (plan section 8) but
not run in B4; checks 2 and 3 are additions decided after seeing the results and are
labelled exploratory (DEVIATIONS.md #6). Check 4 is a verification, not an analysis.
Code in `gap_checks/`; numbers below come from the CSV files named.

## 1. Unsure cases added back (plan section 8) — `unsure_added_back.csv`

The 8 matches that ended "unsure" after the second look became 8 events (ids 1001–1008,
`data/gap_checks/unsure_events.csv`), coded with the same exclusion rules
(`data/gap_checks/unsure_coding.csv`): 2 excluded (N1410714 hurricane, N1443121 sank at
its moorage), 6 added to the main sample. Window files and M4 sets were built with the
Stage B code unchanged (real date only). 3 of the 6 got a matched set (2 had too few
controls, 1 too few positions), so the test uses 200 sets instead of 197.

| Detector | Main (197 sets) | Unsure added back (200 sets) |
| --- | --- | --- |
| 1 Speed drop | 0.610 (0.567–0.653) | 0.602 (0.558–0.643) |
| 2 Loitering | 0.493 (0.453–0.536) | 0.493 (0.452–0.535) |
| 3 AIS gap | 0.586 (0.546–0.627) | 0.580 (0.538–0.619) |
| 4 Off-lane | 0.587 (0.546–0.629) | 0.583 (0.542–0.623) |
| 5 Isolation Forest | 0.574 (0.532–0.617) | 0.573 (0.529–0.615) |

No change of conclusion; speed drop stays just above 0.60.

## 2. Placebo dates on the same events (exploratory) — `placebo_same_events.csv`, `placebo_paired_difference.csv`

Only 104 main-sample events have both a real and a placebo30 set (100 for placebo60),
because the incident vessel often had no AIS 30 or 60 days earlier. On those events:

| Detector | Real | Placebo30 | Real − placebo30 (95% CI) | Real | Placebo60 | Real − placebo60 (95% CI) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 Speed drop | 0.571 | 0.533 | +0.037 (−0.035 to 0.112) | 0.565 | 0.510 | +0.056 (−0.031 to 0.142) |
| 2 Loitering | 0.516 | 0.533 | −0.017 (−0.101 to 0.063) | 0.496 | 0.496 | 0.000 (−0.080 to 0.078) |
| 3 AIS gap | 0.587 | 0.530 | +0.057 (−0.019 to 0.128) | 0.591 | 0.524 | +0.068 (−0.017 to 0.152) |
| 4 Off-lane | 0.609 | 0.501 | +0.108 (0.039 to 0.180) | 0.598 | 0.536 | +0.062 (−0.009 to 0.134) |
| 5 Isolation Forest | 0.578 | 0.561 | +0.017 (−0.060 to 0.091) | 0.583 | 0.483 | +0.099 (0.019 to 0.175) |

Reading: the placebo AUCs stay close to 0.5, but with about 100 events the real-minus-
placebo differences are mostly not distinguishable from zero. Only off-lane (vs
placebo30) and Isolation Forest (vs placebo60) differ clearly. The placebo check is
therefore weaker evidence than the separate 197-vs-120 comparison suggests, and the
paper should report it this way. Speed drop is also lower on this subset (0.57) than in
the full main test (0.61): the events with a placebo set are a selected group (vessels
tracked 30–60 days earlier too).

## 3. When the largest speed drop happens (exploratory, descriptive) — `drop_timing.csv`

Incident vessels and their M4 controls, real date, main window (T−24 h to T). "Last 3 h"
means the main-window speed drop is larger than the early3 (T−27 h to T−3 h) speed drop.

| Group | Incident vessels | Largest drop in last 3 h: incident | control | Drop ≥ 5 kn in last 3 h: incident | control |
| --- | --- | --- | --- | --- | --- |
| All | 197 | 23.4% | 10.2% | 10.2% | 2.4% |
| Groundings | 69 | 36.2% | 11.2% | 18.8% | 2.3% |
| NRC (reported clock time) | 120 | 29.2% | 10.2% | 15.0% | 3.5% |
| IncidentNews (T = 00:00 local) | 77 | 14.3% | 10.3% | 2.6% | 0.7% |

Reading: the speed-drop signal is concentrated in the last 3 hours before the reported
time, above all for groundings and NRC records with a clock time, where the report may
come shortly after the event. IncidentNews, whose T is set deliberately early, shows
almost no excess. Together with the early3 result (0.561), this supports describing the
speed drop as largely registering the incident itself (or report delay), not an early
warning. Off-lane does not fall under early3 (0.595), so it is the detector least
affected by this.

## 4. Independent recheck — `recheck/`

A separate agent rewrote the main test from the method description without reading
`stage_b/analyse.py` or the results first. All AUCs and set/pair counts match to 4
decimals for the main test, early3 and both placebo dates; intervals and p-values
differ only by Monte Carlo noise. No bug found. Two notes: the same seed is used for
every detector (harmless), and the smallest attainable permutation p is 1/10,001, so
"< 0.0001" in the results should read "≤ 0.0001".
