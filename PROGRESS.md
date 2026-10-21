# Progress

Plan: "AIS Exposure-Matched Study: Plan" doc (Claude Docs). Stage A = experiments 1–2,
Janice's review, Stage B = experiments 3–8.

| Date | Stage | Done | Next |
| --- | --- | --- | --- |
| 2026-10-21 | Pilot | Feasibility pilot, power analysis, demo review page | Stage A, experiment 1: full incident set 2015–2025 |
| 2026-10-21 | Stage A, exp. 1 | NRC reports downloaded for 2015, 2016, 2018–2024 and 2026 (`tools/chunked_get.sh`, 2 MB ranges, because the NRC server drops long transfers); GeoNames US gazetteer for place lookup | Retry NRC 2017 and 2025, then build the incident table |
| 2026-10-21 | Stage A, exp. 1–2 | Exp. 1 done: all NRC files CY15–CY25 downloaded, `data/incidents.csv` has 1,247 incidents (797 NRC, 450 IncidentNews), rule counts in `data/incidents_nrc_excluded_counts.csv`, summary in `results/exp1/summary.md`. Exp. 2 started: `stage_a/match_ais.py` scanned 699 of 1,751 needed AIS days (2015-01-04 to 2019-06-08); 497 incidents have both days scanned, giving 435 candidates in `data/candidates.csv` (275 auto-rejected > 100 km, 160 for review). `stage_a/REVIEW_RULES.md` written; Claude reviewed 149 of the 160 in `data/claude_review.csv`: 108 yes, 36 no, 5 unsure. Data issues for Janice in `stage_a/ISSUES.md` (duplicates, IncidentNews UTC window, name prefixes, berth cases). | Continue the scan (`python3 -I stage_a/match_ais.py scan --max-minutes 150`; 1,052 days left, about 4 days a minute), then `match_ais.py candidates` and review the 11 unreviewed and all new candidates (`stage_a/show_case.py`) |
