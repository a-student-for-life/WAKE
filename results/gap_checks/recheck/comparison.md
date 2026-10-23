# Independent recheck vs repo

## Main test (M4, real, main window, 197 sets / 1854 pairs each)

| detector | mine AUC | mine 95% CI | mine p | mine Holm | repo AUC | repo 95% CI | repo p | repo Holm | agree |
|---|---|---|---|---|---|---|---|---|---|
| d1_speed_drop | 0.6098 | 0.565-0.651 | 0.0001 | 0.0005 | 0.6098 | 0.567-0.653 | 0.0001 | 0.0005 | yes |
| d2_loiter_h | 0.4933 | 0.450-0.535 | 0.7659 | 0.7659 | 0.4933 | 0.453-0.536 | 0.7700 | 0.7700 | yes |
| d3_gap_ratio | 0.5863 | 0.546-0.628 | 0.0002 | 0.0008 | 0.5863 | 0.546-0.627 | 0.0003 | 0.0009 | yes |
| d4_off_lane | 0.5874 | 0.546-0.629 | 0.0003 | 0.0009 | 0.5874 | 0.546-0.629 | 0.0002 | 0.0008 | yes |
| d5_iforest | 0.5744 | 0.532-0.617 | 0.0009 | 0.0018 | 0.5744 | 0.532-0.617 | 0.0007 | 0.0014 | yes |

## early3 and placebo (AUC + bootstrap CI)

| scenario/window | detector | sets/pairs | mine AUC | mine CI | repo sets/pairs | repo AUC | repo CI | agree |
|---|---|---|---|---|---|---|---|---|
| real/early3 | d1_speed_drop | 197/1847 | 0.5615 | 0.518-0.605 | 197/1847 | 0.5615 | 0.519-0.603 | yes |
| placebo30/main | d1_speed_drop | 120/1172 | 0.5183 | 0.463-0.571 | 120/1172 | 0.5183 | 0.465-0.572 | yes |
| placebo60/main | d1_speed_drop | 119/1174 | 0.5162 | 0.463-0.570 | 119/1174 | 0.5162 | 0.462-0.571 | yes |
| real/early3 | d2_loiter_h | 197/1847 | 0.5095 | 0.468-0.552 | 197/1847 | 0.5095 | 0.468-0.552 | yes |
| placebo30/main | d2_loiter_h | 120/1172 | 0.5371 | 0.481-0.593 | 120/1172 | 0.5371 | 0.481-0.594 | yes |
| placebo60/main | d2_loiter_h | 119/1174 | 0.5038 | 0.452-0.554 | 119/1174 | 0.5038 | 0.454-0.554 | yes |
| real/early3 | d3_gap_ratio | 197/1847 | 0.5433 | 0.499-0.587 | 197/1847 | 0.5433 | 0.501-0.587 | yes |
| placebo30/main | d3_gap_ratio | 120/1172 | 0.5235 | 0.474-0.573 | 120/1172 | 0.5235 | 0.470-0.575 | yes |
| placebo60/main | d3_gap_ratio | 119/1174 | 0.5315 | 0.480-0.582 | 119/1174 | 0.5315 | 0.478-0.585 | yes |
| real/early3 | d4_off_lane | 197/1847 | 0.5950 | 0.554-0.636 | 197/1847 | 0.5950 | 0.553-0.637 | yes |
| placebo30/main | d4_off_lane | 120/1172 | 0.5098 | 0.452-0.565 | 120/1172 | 0.5098 | 0.452-0.566 | yes |
| placebo60/main | d4_off_lane | 119/1174 | 0.5460 | 0.491-0.601 | 119/1174 | 0.5460 | 0.491-0.602 | yes |
| real/early3 | d5_iforest | 197/1847 | 0.5544 | 0.510-0.599 | 197/1847 | 0.5544 | 0.510-0.598 | yes |
| placebo30/main | d5_iforest | 120/1172 | 0.5533 | 0.500-0.605 | 120/1172 | 0.5533 | 0.500-0.606 | yes |
| placebo60/main | d5_iforest | 119/1174 | 0.4855 | 0.431-0.540 | 119/1174 | 0.4855 | 0.431-0.541 | yes |

## Sanity checks
- Main-sample events: 257 (283 total, 26 main_exclude). Of these, 197 have a real M4 set (M4 has 220 real sets over all 283 events); 120 placebo30 and 119 placebo60 sets in the main sample.
- Every set has exactly 1 incident row; 5-10 controls (real), 6-10 (placebo60).
- Every M4 member has a main-window row; the M4 incident mmsi has is_incident True in the windows file in every set, and no other vessel is flagged incident.
- No duplicate (event, scenario, mmsi, window) rows in windows; no duplicate (event, scenario, mmsi) in M4.
- In the main window no member lacks a d1-d5 score (197 sets / 1854 pairs per detector); early3 loses 7 pairs.

## Notes on stage_b/analyse.py (read after the comparison)
- Method matches the description: same win counting (ties half, self excluded), within-set permutation with fixed denominator, two-sided |AUC-0.5| rule with 1e-12 tolerance, set-level percentile bootstrap, correct Holm step-down.
- No bug affecting the reported numbers. Minor: the same seed is reused for every detector and for both permutation and bootstrap, so the random draws are identical across detectors (harmless; Holm holds under dependence). fmtp prints the floor value p = 1/10001 = 0.00009999 as "< 0.0001", which slightly overstates it; "p <= 0.0001" would be accurate.
- Interpretation caution, not a bug: d1 is the only detector meeting the "useful signal" rule (Holm p < 0.05 and AUC >= 0.60), and its AUC 0.6098 is just over the 0.60 cut with a 95% interval of about 0.57-0.65; the 5-control variant gives 0.594 and early3 gives 0.561.
