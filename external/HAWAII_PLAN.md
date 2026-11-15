# External check on HawaiiCoast_GT (written 15 Nov 2026, before any Hawaii score was computed)

Exploratory replication of the WAKE protocol on an independently built dataset (Henriksen et
al., *Discover Oceans*, 2024; Zenodo record 8253611, v1.0): AIS off Hawaii 2017-2020 curated from
the same Marine Cadastre source, with 208 vessel tracks labelled for 154 documented incidents. Its
incidents are not limited to oil (mostly loss of propulsion, tows, steering failures), so this
tests whether the protocol and the simple detectors transfer, not the oil-incident result itself.
Approved by Janice on 15 Nov 2026 ("go ahead and try them"). Reported whatever it shows.

## Events
- Rows of `incident_data/hawaii_primary_trajectories_of_interest_2017_2020.csv` whose
  `report_vessel_role` is not "Helper vessel" (the vessel the incident happened to).
- T = `report_incident_time_of_interest_hst` converted to UTC where given; otherwise 00:00 HST on
  `report_start_date_of_interest_hst` (the WAKE rule for date-only records). Rows with neither are
  dropped. One event per vessel per incident; rows of the same vessel within three days merged
  (earliest T), as in WAKE.

## Data and detectors
- Daily files are rebuilt from the monthly Hawaii CSVs in the Marine Cadastre column layout and
  read with the unchanged `stage_b/aisday.py`; windows, detectors 1-5 and M4 matching use the
  unchanged `stage_b/windows.py` and `stage_b/match.py`.
- Two settings must change because the data are regional: the fleet references and alarm
  thresholds come from the Hawaii day file rather than a national one, and the minimum positions
  for a usable day is 10,000 (not 1,000,000). Vessels named in any Hawaii incident within 30 days
  are excluded as controls (WAKE's candidate exclusion).
- Scenarios: true date and placebo30.

## Tests
- Main: pooled AUC per detector, main window, M4 sets, permutation p (10,000) and bootstrap
  (5,000 events), seed 20261022, Holm over the five detectors, the WAKE reading rules.
- Supporting: early3 on the same sets; placebo30.
- Descriptive only; this check does not change any WAKE result.
