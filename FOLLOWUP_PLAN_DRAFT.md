# Follow-up plan (DRAFT): benchmark release, timed incidents, second human rater

Drafted 3 Nov 2026 for Janice. Nothing here has been run apart from drawing the rater sample.

## 1. WAKE benchmark release (needs Janice's Zenodo login)

Contents, all already in this repository:

- `data/incidents.csv` (1,247 incidents) and the NRC exclusion counts;
- `data/candidates.csv`, `data/claude_review.csv`, `data/janice_review.csv`,
  `data/second_look.csv`, `data/confirmed.csv`, `data/event_coding.csv`,
  `data/confirmed_events.csv`;
- `data/stage_b/events.csv`, `data/stage_b/matched/` (M1-M4 and robustness sets),
  `data/stage_b/windows/` (per-vessel window scores);
- `data/gtn/regions.csv`, `data/gtn/train_days.csv`, training curves, `data/gtn/scores/`;
- the plan, both addenda, `DEVIATIONS.md` and all code.

Licence: the inputs are U.S. government public data (NRC, IncidentNews, Marine Cadastre); a
CC BY 4.0 licence for the derived files and MIT for the code are common choices (Janice to
decide). Steps: connect the repository to Zenodo through Zenodo's GitHub integration, make a
GitHub release (e.g. `v1.0-paper`), and Zenodo mints a DOI for that release. The DOI then goes
into the paper's Data Availability section and gives the plan a third-party time stamp.

## 2. Independently timed incidents

Aim: for a subset of events, an incident time that does not come from the NRC call or the
IncidentNews date, to separate behaviour before an incident from the incident itself.
Candidate sources: U.S. federal marine accident investigation reports and briefs, which state
the time of a grounding or collision. Steps: search those reports for the vessel names of the
257 events, record the stated time with its source, then rerun the main window and early3
ending at that time on the existing M4 sets (descriptive unless at least 40 events are found).
Source coverage and access need to be checked before this is promised in the paper.

## 3. Human second rater

`stage_a/second_rater_sample.csv` lists 100 of the 410 reviewed cases, drawn with seed 20261022
in proportion to how the first two raters answered: 65 both-yes, 33 disagreements, 1 both-no,
1 both-unsure. A second person reviews them on a copy of the review page, blind to both earlier
answers, using `stage_a/REVIEW_RULES.md`. Report Cohen's kappa against Janice's answers (yes
against not-yes) beside the existing human-model kappa of 0.69.
