# Deviations from ANALYSIS_PLAN.md

Each change to the approved plan, with its date and reason. Results are reported
whatever they show.

## 1. Decision rule of the report-time check (section 3a), 22 Oct 2026

Agreed by Janice on 22 Oct 2026, before any detector had been run or any incident-vessel
result seen. Only the time-check data in `results/time_check_cases.csv` had been looked at.

**Old rule.** Keep the reading (local, Eastern, UTC) whose median difference between the
reported time and the AIS stop, over all usable cases, is closest to zero.

**Problem found in the preliminary run.** For incidents in the US Eastern time zone, the
local and Eastern readings are identical, so those cases cannot tell the readings apart.
Several "stops" are vessels already at anchor for hours before being struck, so they are
not the incident. The overall median was pulled by both and picked Eastern (median
+0.74 h against +1.28 h for local), although the cases that can discriminate contradict
it: read as Eastern, 11 of 14 such reports would come before the vessel stopped, which is
impossible for a grounding.

**New rule.** Use only cases where the local and Eastern readings differ (incidents
outside the Eastern time zone at that date) and where the stop is within 6 hours of the
report under at least one reading. Keep the reading with the smallest median absolute
difference. The 2-hour shift rule and the 15-case minimum stay as before, applied to
these cases.

**Effect.** Preliminary run (`results/time_check.md`): 14 such cases; local has median
+0.32 h (median absolute 0.45 h), Eastern -1.09 h (1.54 h), UTC -5.71 h. That is one case
short of the 15-case minimum, so by the rule local time is kept and the check counts as
inconclusive; the cases there are point the same way. Either way T stays the reported
time read as local time, with no shift, which is the assumption Stage A already used. The official run repeats this on the confirmed
matches after the blind review.

## 2. Added robustness check: independent agreement only, 22 Oct 2026

Agreed by Janice on 22 Oct 2026, before any detector had been run or any incident-vessel
result seen.

**Addition.** The main test is repeated on the matches that both raters marked yes
independently in the blind review (264 matches in `data/janice_review.csv` and
`data/claude_review.csv`), leaving out the 33 added at the second look.

**Reason.** At the second look (`data/second_look.csv`) the final answer matched Claude's
first answer in 49 of 52 cases, so the 33 added matches rest mainly on one rater, an LLM.
This check shows whether the result depends on them.

## 3. Event-table gaps not covered by the Stage B spec, 22 Oct 2026

Implementation detail filled in at step B1, before any detector had been run.

**Gap.** 14 vessel events have an earliest report with no reference point, and one of
them (N1414867, SEASPAN KESTREL, Haro Strait, Canada) is an NRC record with a local time
but no time zone and no `time_utc`, so the spec's rules give it no T.

**Rule used.** A missing reference point is replaced by the vessel's median AIS position
on the report's local date, from its Stage A track in `data/tracks/` (`ref_source =
ais_track_median` in `data/stage_b/events.csv`). For N1414867 the zone is taken from that
point with the spec's longitude rule (America/Los_Angeles) and T is the reported local
time in that zone (`T_rule = nrc_local_tz_from_ais`). The reference point only matters
for the time zone and as the last fallback for the window centre.

**Event-level exclusion.** One event (211) has two reports coded differently (berth in
the IncidentNews text, no flag in the NRC record). The spec's count of 257 events in the
main analysis means an event is excluded only when all its matches are flagged, so event
211 stays in the main analysis; `main_exclude_any` marks it so a robustness run can drop it.

## 4. Nearly empty AIS days, 22 Oct 2026

Implementation detail added during step B2, before any incident-versus-control
comparison had been looked at.

**Gap.** Some national Marine Cadastre day files are almost empty: the file for
2015-03-15 holds 5,049 positions (normal days hold 6–10 million), nearly all from the
first hour. A fleet reference cannot be built from it and windows covering it would be
mostly blank, which the spec does not anticipate.

**Rule used.** A national day file with fewer than 1,000,000 positions is treated like a
missing day: an event-scenario whose required days (T-48 h to T) include it is recorded
as impossible in `data/stage_b/state.json`; a day that only covers the 12 hours after T
is left out of after12. The days concerned and their position counts are listed under
`short_days` in the state file.

## 5. Matching details not fixed by the plan or spec, 23 Oct 2026

Implementation detail filled in at step B3, before any detector score had been loaded or
any incident-versus-control comparison looked at (`stage_b/match.py` reads only the
exposure columns of the window files).

**Gap.** The plan's control pool is vessels with at least one position within 50 km of
the centre in the window; the window files keep each vessel's median window position,
not every position. The plan does not say what M1–M3 use as their area, or whether a
control needs enough positions to be scored.

**Rule used.** The 50 km pool of M4 uses the distance of the vessel's median main-window
position from the centre (widened to the whole 150 km box below 10 qualifying vessels).
M1–M3 draw from the whole 150 km box; M4 adds the 50 km area. Every definition keeps
the 25% positions caliper and requires controls to have at least 10 positions (30 in
the 30-position check), since a vessel with fewer has no score. Full list of choices in
`results/stageB/notes.md`.

## 6. Gap-closing checks after Stage B, 23 Oct 2026

Added after the Stage B results had been seen, at Janice's request. Results in
`results/gap_checks/summary.md`; code in `gap_checks/`. Stage B files are unchanged.

1. **Unsure cases added back** (pre-registered in plan section 8, not run in B4 because
   B1 builds events only from `data/confirmed_events.csv`). The 8 unsure matches were
   made into events and coded for exclusions 1–3 by Claude from the report text and AIS
   track. This coding was done after the main results existed, but before any detector
   was run on these 8 vessels. Windows and M4 sets use the Stage B code unchanged, real
   date only.
2. **Placebo dates on the same events** (exploratory, not pre-registered): real-date
   AUCs restricted to events that also have a placebo set, and the paired difference
   real minus placebo with a bootstrap of events (5,000 resamples, seed 20261022).
3. **Timing of the largest speed drop** (exploratory, descriptive): share of incident
   vessels and controls whose largest main-window speed drop falls in the last 3 or 6
   hours before T, from the existing window scores.
4. **Independent recheck** of the main test, early3 and placebo AUCs by a separate agent
   that wrote its own code (`results/gap_checks/recheck/`). It is a verification, not
   an analysis.
