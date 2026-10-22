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
