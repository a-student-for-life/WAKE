# WAKE: Were Anomalies Known Early?

Data and code for the paper *WAKE (Were Anomalies Known Early?): An Exposure-Matched Evaluation
of AIS Anomaly Detectors Against Confirmed Oil-Incident Vessels* (Janice Miranda, Department of
Computer Engineering, Don Bosco Institute of Technology, Mumbai; manuscript under review).

The study asks whether AIS anomaly detectors single out vessels involved in oil incidents once
each incident vessel is compared with vessels of the same type and similar AIS exposure, in the
same area and over the same 24 hours. It covers 1,247 oil-related vessel incidents in U.S. waters
from 2015 to 2025, 297 vessel matches confirmed through a blind two-rater review, 197
exposure-matched sets, five simple detectors (speed drop, loitering, AIS gap, off-lane, Isolation
Forest) and the learned detector GeoTrackNet in 16 regions.

The analysis plan (`ANALYSIS_PLAN.md`, approved 22 Oct 2026) was fixed before any detector was run
on an incident vessel, and the GeoTrackNet addendum (`ANALYSIS_PLAN_ADDENDUM_1.md`, approved
23 Oct 2026) before any GeoTrackNet model was trained. Neither was lodged with an external
registry; their dates rest on the repository history (`git_history.txt` in the archived release).
Every departure from them is listed with its date in `DEVIATIONS.md`.

## Layout

| Path | What it holds |
| --- | --- |
| `ANALYSIS_PLAN.md`, `ANALYSIS_PLAN_ADDENDUM_1.md` | Analysis plan and GeoTrackNet addendum, as approved |
| `DEVIATIONS.md` | Dated log of every deviation from the plan and addendum |
| `STAGE_A_SPEC.md`, `STAGE_B_SPEC.md`, `GTN_SPEC.md` | Specifications for building the incident set, the main analysis and GeoTrackNet |
| `GTN_PRE_PHASE4_NOTES.md` | Reporting decisions fixed before any GeoTrackNet score was opened |
| `PROGRESS.md` | Stage-by-stage working log |
| `pilot/` | 21 Oct 2026 feasibility pilot: incident counts, NRC filters, AIS name matching, power analysis |
| `stage_a/` | Incident table, AIS name matching, report-time check; `REVIEW_RULES.md` are the written review rules both raters followed |
| `review_page/` | The blind review page and second-look page, and the scripts that build them |
| `stage_b/` | Vessel events, window scores for the five simple detectors, matching (M1-M4) and the main tests |
| `gtn/` | GeoTrackNet: region and training-day selection, preprocessing, training with the stop rule, scoring and tests; `PATCHES.md` lists the one change to the authors' code |
| `gap_checks/` | Checks added after the main results (see `DEVIATIONS.md` 6 and 9) |
| `paper/make_figures.py` | Draws the three figures of the paper from the files in this repository |
| `data/incidents.csv` | Combined incident table (1,247 incidents) |
| `data/candidates.csv` | AIS name candidates for each incident |
| `data/janice_review.csv`, `data/claude_review.csv`, `data/second_look.csv` | Blind review answers of the two raters and the second look |
| `data/confirmed.csv`, `data/event_coding.csv`, `data/confirmed_events.csv` | Confirmed matches, exclusion coding and vessel events |
| `data/ais_hits/`, `data/tracks/` | AIS extracts used to build the review pages |
| `data/stage_b/` | Event table, per-vessel window scores (`windows/`) and matched sets (`matched/`) |
| `data/gtn/` | GeoTrackNet regions, training days, training curves and checkpoints (`models/`), and scores (`scores/`) |
| `results/` | Result tables and notes: `stageB/` (simple detectors), `gtn/` (GeoTrackNet), `gap_checks/`, `agreement/` (rater agreement) |

## Data sources

All inputs are public:

- U.S. Coast Guard National Response Center annual reports: `https://nrc.uscg.mil/FOIAFiles/CY<yy>.xlsx`
- NOAA ORR IncidentNews: `https://incidentnews.noaa.gov/raw/incidents.csv`
- BOEM/NOAA Marine Cadastre national AIS:
  2015-2024 `https://coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/AIS_<yyyy>_<mm>_<dd>.zip`,
  2025 onward `https://noaaocm.blob.core.windows.net/ais/csv2/csv<year>/ais-<yyyy>-<mm>-<dd>.csv.zst`
- GeoNames gazetteer (geocoding named places): `https://www.geonames.org/`
- Natural Earth 1:50m land (map only): `https://github.com/nvkelso/natural-earth-vector`

Raw source files go in `data/raw/` and are not included (the national AIS files are about 300 MB a
day); they can be downloaded again from the addresses above.

## Reproducing the results

1. Stage A (incident table, matching, review): `stage_a/build_incidents.py`, `stage_a/match_ais.py`,
   `review_page/build_review.py`, `stage_a/summarize.py`, `stage_a/time_check.py`.
2. Stage B (simple detectors): `stage_b/build_events.py`, `stage_b/windows.py`, `stage_b/match.py`,
   `stage_b/analyse.py`. Tables are written to `results/stageB/tables/`.
3. GeoTrackNet: `bash gtn/setup_env.sh` builds the environment (Python 3.7, TensorFlow 1.15.5,
   authors' code at commit 7797b16a with `gtn/geotracknet_compat.patch`); then
   `gtn/regions_days.py`, `gtn/extract_train.py`, `gtn/preprocess.py`, `gtn/train_region.py`,
   `gtn/score_prep.py`, `gtn/score_region.py`, `gtn/analyse_gtn.py`. Tables are written to
   `results/gtn/tables/`.
4. Later checks: the scripts in `gap_checks/`, run from the repository root.
5. Figures: `python3 paper/make_figures.py . figures`.

The order of work and every run are recorded in `PROGRESS.md`.

## Use of a language model

A large language model (Claude, Anthropic) acted as the second rater in the blind review, under the
same written rules as the author (`stage_a/REVIEW_RULES.md`), and assisted with code. Its answers are
in `data/claude_review.csv`.

## Licence

Code: MIT (`LICENSE`). Derived data, tables and documentation: CC BY 4.0 (`LICENSE-DATA.md`).
GeoTrackNet itself is not included; `gtn/geotracknet_compat.patch` modifies the authors' code, which
is available under MIT or CeCILL-C.

## Citation

See `CITATION.cff`. Please also cite GeoTrackNet (Nguyen et al., 2022, IEEE Transactions on
Intelligent Transportation Systems 23(6), 5655-5667) when using the `gtn/` code.
