# Stage B spec (experiments 3–8)

Every working session follows this file and `ANALYSIS_PLAN.md` (with `DEVIATIONS.md`).
The plan defines what is measured and tested; this file fixes how the work is split
into sessions and the implementation choices the plan leaves open. Those choices were
written on 22 Oct 2026, before any detector was run. Any later change to them is logged
in `DEVIATIONS.md` with its date and reason.

## One session at a time

1. After cloning, check for `RUNNING.md`. If it exists and its start time is less than
   4 hours ago, another session is working: stop at once and change nothing.
2. Otherwise write `RUNNING.md` with the current UTC time, commit it ("Session lock")
   and push. If the push is rejected, pull and go back to step 1.
3. Delete `RUNNING.md` in the session's final commit. A lock older than 4 hours belongs
   to a session that died and may be replaced.

## Ground rules

- Commit as `Janice Miranda <38janice10b@gmail.com>`, with **no `Co-Authored-By` or other
  attribution lines** and no collaborators added.
- `git pull --rebase origin main` before every push. Commit after every finished unit
  (one event-scenario's window file, or one analysis step), so a cut-off session loses
  little.
- Stop after about 3 hours of work, at a clean commit, with a row added to
  `PROGRESS.md` (date, stage, what was done with counts from files, what is next), including
  the measured minutes per AIS day this session and the estimated hours of work left).
- Raw AIS goes in `data/raw/` (git-ignored) and is deleted when no longer needed. Commit
  only code and derived tables. Keep every committed file under 50 MB.
- Never look at, print or summarise an AUC, odds ratio, p-value or any comparison of
  incident vessels with controls before step B4. Steps B1–B3 build inputs only.
- Never change `data/confirmed.csv`, `data/event_coding.csv`, the reviews or the plan.

## B1. Event table (`stage_b/build_events.py` -> `data/stage_b/events.csv`)

One row per vessel event in `data/confirmed_events.csv` (283 events; 257 in the main
analysis, the rest flagged by `main_exclude`). For an event with several matches, use
the earliest report and the match whose MMSI transmitted closest to the report time.

- **T, NRC:** `time_utc` from `data/incidents.csv` (local time, confirmed by
  `results/time_check.md`).
- **T, IncidentNews:** 00:00 local time on `date_local`, converted to UTC with the
  record's `tz`. Where `tz` is empty, take the zone from the reference longitude:
  east of -87 New York, -87 to -101 Chicago, -101 to -114 Denver, -114 to -130 Los
  Angeles, west of -130 Anchorage, except Hawaii (lat < 30, lon < -150) Honolulu and
  Puerto Rico / Virgin Islands (lat < 20, lon > -68) Puerto Rico.
- **Scenarios:** `real` (T), `placebo30` (T minus 30 days), `placebo60` (T minus 60
  days). Placebo windows keep the same vessel and are re-matched on their own date.
- Columns: event_id, mmsi(s), imo, T_utc, T_rule, source, setting, incident_type,
  main_exclude, first_pass_both_yes (all matches in the event were both-yes in the blind
  review), the reference point, and the scenario times.

## B2. Window files (`stage_b/windows.py`)

Process event-scenarios in order of window start, so consecutive ones share AIS days.
Keep a cache of at most 20 raw day files on disk; delete the oldest first.

AIS days: Marine Cadastre URLs as in `stage_a/match_ais.py` (2015–2023 zips on
coast.noaa.gov; 2024–2025 `.csv.zst` on noaaocm.blob.core.windows.net). Read in chunks;
a full day does not fit in memory. Treat SOG >= 102.2 as missing, drop positions outside
lat -90..90 / lon -180..180 and at 0,0, drop MMSIs that are not 9 digits.

For each event-scenario:

1. **Centre:** the incident vessel's median position in the main window (T-24 h to T).
   If it has no positions there, its median position in T-48 h to T+12 h; failing
   that, the reference point. Record which was used.
2. **Box:** every vessel with at least one position within 150 km of the centre during
   T-48 h to T+12 h. Keep their positions for that span (in memory only).
3. **Windows**, each computed for every box vessel: `main` T-24 h to T; `w6` T-6 h to
   T; `w48` T-48 h to T; `early3` T-27 h to T-3 h (the 3-hour check added to plan
   section 8 on approval); `after12` T to T+12 h (descriptive only).
4. **Per vessel and window:** positions, hours observed (sum of gaps <= 1 h), distance
   sailed, type group from the most common AIS type (fishing 30 and 1001; tug and
   towing 31, 32, 52 and 1025; cargo 70–79 and 1004; tanker 80–89; passenger 60–69;
   other or unknown otherwise), median length, median position, distance of the median
   position from the centre, and whether the MMSI or IMO appears in
   `data/candidates.csv` for any incident within 30 days of T (such vessels cannot be
   controls).
5. **Fleet reference for the day:** the UTC day that contains T-12 h, computed once per
   day per session from the full national file and cached in memory:
   - stationary places: 0.01-degree cells where at least 20 distinct vessels had SOG
     < 0.5 kn that day (detector 2 excludes time within 3 km of these);
   - traffic density: distinct vessels per 0.01-degree cell that day (detector 4);
   - gap norm: per 0.25-degree cell, the median over vessels of their longest silence
     that starts at SOG >= 3 kn (detector 3); cells with fewer than 10 vessels use the
     national median;
   - Isolation Forest: features per vessel over that UTC day for every vessel with at
     least 10 positions (mean SOG, SOG standard deviation, largest speed drop, longest
     gap, standard deviation of turn rate, share of positions below 0.5 kn, off-lane
     score), scikit-learn `IsolationForest(n_estimators=200, random_state=20261022)`;
   - national thresholds: the 90th, 95th and 99th percentiles of each detector's score
     over that day's fleet, for the flag-rate analysis.
6. **Detector scores** for every box vessel and window, exactly as in plan section 5,
   with the fleet reference of step 5 and the Isolation Forest applied to the vessel's
   window features. A vessel with fewer than 10 positions in a window gets no score in
   that window (empty, not zero).
7. **TARS layers (detector 6):** attach `a-student-for-life/TARS-triage` read-only with
   add_repo and use its Layer 1–3 logic unchanged on the window positions. If the repo
   cannot be attached or the code cannot run on these inputs, leave detector 6 empty and
   record why in `results/stageB/notes.md`; the main analysis does not depend on it.
8. **Write** `data/stage_b/windows/<event_id>_<scenario>.csv.gz`: one row per box vessel
   and window with every field above, plus the centre, the fleet thresholds and the code
   version (git commit). Record progress in `data/stage_b/state.json`.

## B3. Matching (`stage_b/match.py` -> `data/stage_b/matched/`)

Per event-scenario and window `main`, following plan section 4: control pool within
50 km of the centre (widen to 150 km below 10 qualifying vessels), exact type group,
positions within 25% of the incident vessel's, 10 nearest on log positions, log hours
and log length (Mahalanobis, covariance from the pool; length left out where missing),
without replacement. Fewer than 5 controls: the event is dropped for that scenario and
counted. Build the four definitions M1–M4 of plan section 4, and for the robustness
checks 5 and 20 controls and the 30-position minimum. Write the matched sets and a
balance table (standardised mean differences of the matching variables, incident vs
controls, per definition) to `results/stageB/balance.md`. The balance table is
inputs-only and may be inspected; detector scores may not.

## B4. Analysis (`stage_b/analyse.py` -> `results/stageB/`)

Run only when every event-scenario window file exists (or is recorded as impossible,
for example no AIS at all). Then, exactly as plan sections 6–8:

1. Main test, M4, main window, scenario `real`, main sample: AUC per detector,
   permutation p (10,000, within matched sets, two-sided, seed 20261022), Holm over
   detectors 1–5, bootstrap 95% interval (5,000 resamples of events, same seed).
2. Apply the reading rules of plan section 6 literally and state the conclusion per
   detector in one sentence each.
3. Supporting analyses: naive comparison, flag-rate conditional logistic regression
   (statsmodels `ConditionalLogit`) at 1%, 5% and 10%, placebo30 and placebo60,
   windows w6 and w48, after12 described only.
4. Every robustness check in plan section 8 and DEVIATIONS #2, each as one row: AUC and
   interval per detector.
5. Write `results/stageB/results.md` with every table, the numbers of events used and
   dropped at each step and why, and the file each number came from. No interpretation
   beyond the plan's reading rules.

## When Stage B is done

1. `PROGRESS.md`: "Stage B complete. Results in results/stageB/results.md."
2. Send Janice a short push notification: Stage B is done and where the results are.
   Do not put results in the notification.
3. Later sessions that find Stage B complete change nothing and stop.
