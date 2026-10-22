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
