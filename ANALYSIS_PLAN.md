# WAKE analysis plan

Version 1, drafted 22 Oct 2026, before any detector has been run on incident vessels.
The git history of this file is the record of what was decided before results existed.
Any later change goes in `DEVIATIONS.md` with its date and reason; results are reported
whatever they show.

Status: **approved by Janice on 22 Oct 2026**, with the two additions she agreed that day (section 3a and the last robustness check in section 8).

## 1. Question

Do standard AIS anomaly detectors score vessels involved in oil incidents higher than
vessels that were tracked about as heavily, in the hours before the incident?

**Hypothesis.** For a detector that is useful for triage, the incident vessel ranks
above its exposure-matched controls more often than chance: AUC > 0.5.

**Smallest effect of interest: AUC 0.60.** Below that, a detector would flag too few
extra incident vessels to be worth its alarms.

## 2. Sample

**Confirmed vessel.** A candidate is confirmed when Janice and Claude both answer yes
after the blind review and the second look at disagreements. Cases still disputed are
"unsure": they are left out of the main analysis and added back in a sensitivity run.

**Agreement.** Cohen's kappa between Janice's and Claude's first answers, before any
discussion, on yes versus not-yes and on all three answers.

**Unit: the vessel event.** Reports of the same vessel within 3 days are one event,
dated by the earliest report. "Same vessel" means the same IMO number when both MMSIs
carry one, otherwise the same MMSI. This merges duplicate reports across sources and
spelling variants, and a ship that changed MMSI (ISSUES #3, #10).

**Main-analysis exclusions,** each counted and reported:

1. The named vessel was not the source: a responder, a vessel that reported a sheen,
   or a bystander. A tug towing the barge that spilled counts as the source, because
   barges rarely carry AIS (ISSUES #4).
2. The event happened at a berth, in a shipyard or during maintenance (ISSUES #5).
3. The event was caused by a hurricane or tropical storm (ISSUES #6).
4. Fewer than 10 AIS positions in the analysis window, so no detector can be computed.

Exclusions 1–3 are coded by Claude from the report text and the AIS speed at the report
time, before any detector is run, in `data/event_coding.csv`.

## 3. Time windows

**T** is the incident time: the report's date and time converted to UTC (NRC), or, for
a record with a date only (IncidentNews), 00:00 local time on the report date. The
date-only rule is deliberately early, so no after-the-event behaviour leaks in.

**Main window: the 24 hours before T.** Secondary windows: 6 and 48 hours before T.
The 12 hours after T are described, never counted as detection: a grounded ship
stopping afterwards is a consequence, not a warning.

## 3a. Check of the report-time convention (before Stage B)

NRC times are assumed to be local time at the incident, and to mark the incident rather
than the call. This is checked before any detector is run:

- **Cases:** confirmed groundings and allisions with an exact reported position whose AIS
  track shows the vessel stopping (speed under 1 knot for at least 30 minutes) within
  2 km of that position.
- **Measure:** reported time minus the AIS stop time, under three readings of the
  reported time: local time, US Eastern time, and UTC.
- **Decision rule:** keep the reading whose median difference is closest to zero. If the
  median under that reading is still more than 2 hours after the stop (the time a call
  was made, not the incident), T becomes the reported time minus that median delay.
  With fewer than 15 usable cases, keep local time and report the check as inconclusive.

The result and the rule applied are written to `results/time_check.md` before Stage B.

## 4. Exposure and matched controls

For every vessel in the window: number of AIS positions, hours observed (sum of
intervals between consecutive positions no longer than 1 hour), distance sailed,
vessel type group (fishing; tug and towing; cargo; tanker; passenger; other or
unknown) and length.

**Control pool.** Vessels with at least one position within 50 km of the incident
vessel's median position in the window, in the same window, that are not in the
incident list within 30 days either side.

**Matching (main definition, M4).** Exact on type group. Then the 10 nearest vessels on
log positions, log hours observed and log length (Mahalanobis distance), with positions
within 25% of the incident vessel's. Without length, length is left out of the
distance. If fewer than 10 qualify, the area widens to 150 km; an event with fewer than
5 controls is dropped and counted.

**Other definitions, all reported side by side:** M1 positions only; M2 positions and
hours; M3 adds type and length; M4 adds area and time (main). The naive comparison uses
every vessel in the area with no matching.

## 5. Detectors

Each gives every vessel one score per window. All are computed the same way for
incident vessels and everyone else. Thresholds are fixed here, not tuned.

1. **Speed drop:** the largest fall in speed between consecutive positions at most 10
   minutes apart (knots).
2. **Loitering:** the longest continuous time below 2 knots within a 1 km radius,
   leaving out time within 3 km of a place where at least 20 vessels were stationary
   that day (a port or anchorage, found from the fleet itself).
3. **AIS gap:** the longest silence that starts while the vessel is moving (at least
   3 knots), divided by the median longest silence of vessels in the same 0.25° cell.
4. **Off-lane:** the mean over the vessel's positions of -log(1 + the number of other
   vessels seen in the same 0.01° cell that day). Higher means further from usual
   traffic.
5. **Isolation Forest** on trajectory features (mean and spread of speed, largest speed
   drop, longest gap, spread of turn rate, share of time stationary, off-lane score),
   fitted on the whole national fleet for that day: vessels with at least 10 positions,
   200 trees, fixed random seed. Score = minus the sample score.
6. **TARS layers,** reported separately as a sixth detector and not part of the
   corrected family.

## 6. Main test

For each event and detector, the incident vessel's rank among itself and its controls,
scaled to 0–1 (ties averaged). The AUC is the share of incident-control pairs in which
the incident vessel scores higher (ties count half).

- **Test:** a permutation test that shuffles the incident label within each matched
  set, 10,000 permutations, two-sided.
- **Correction:** Holm across detectors 1–5, family-wise alpha 0.05.
- **Uncertainty:** 95% bootstrap interval for each AUC, resampling events (5,000
  resamples).

**How results are read,** decided now:

| Result | Conclusion |
| --- | --- |
| A detector is significant after Holm and its AUC is at least 0.60 | That detector carries a useful signal |
| The upper end of the interval is below 0.60 for all five | No detector carries a useful signal (a null with enough power to mean something) |
| Anything else | Inconclusive for that detector, reported with its interval |

**Power.** From the pilot simulation, about 250 events give over 95% power for AUC 0.60
at alpha 0.01, and roughly 70% for AUC 0.55 at alpha 0.05.

## 7. Supporting analyses

- **Naive comparison:** the same AUC against every vessel in the area, unmatched. It
  is expected to show a larger signal, which matching removes if exposure drives it.
- **Flag rates:** conditional logistic regression of "flagged" on incident status,
  stratified by matched set, with flagged meaning in the top 1%, 5% or 10% of the
  national fleet that day. Odds ratios with 95% intervals.
- **Placebo dates:** the whole analysis repeated with T moved 30 days and 60 days
  earlier, with controls re-matched on those dates. A real effect should appear at the
  true date and not at the placebo dates.
- **Windows:** 6 and 48 hours, and the 12 hours after T (descriptive only).

## 8. Robustness checks

Sea versus inland incidents; incident type; NRC only and IncidentNews only; unsure
cases added back; berth and storm events added back; only matches both raters marked yes in the blind review (DEVIATIONS.md #2); 5 and 20 controls instead of 10;
a minimum of 30 positions instead of 10; MMSI-only events (no IMO merging); the main window ending 3 hours before T instead of at T, so that behaviour just after an incident cannot drive the result if T is slightly late.

## 8a. Known limitation

The five detectors follow standard ideas, but their exact definitions and thresholds are
set here rather than copied from a published system. They are fixed before any results
exist; the paper states that a differently tuned detector could behave differently.

## 9. Data decisions from Stage A (ISSUES.md)

| # | Issue | Decision |
| --- | --- | --- |
| 1 | IncidentNews has a date but no time | Search the following UTC day too, for every date-only record (done 22 Oct) |
| 2 | Name prefixes not stripped | THE, VESSEL, TUG BOAT, TOW BOAT, TUGBOAT, TOWBOAT, FISHING VESSEL, USNS, M/S, R/V and P/V now stripped. "MS" kept, since it usually means Miss; TowBoatUS kept as a brand (done 22 Oct) |
| 3 | Duplicates across sources and spellings | Merged at analysis into vessel events (section 2) |
| 4 | Named vessel was not the source | Coded and excluded from the main analysis (section 2) |
| 5 | Berth and maintenance events | Flagged from the text for both sources, coded, excluded from the main analysis |
| 6 | Hurricane cases without the tag | Flagged from the text, excluded from the main analysis |
| 7 | Wrong reference coordinates | Auto-reject only if a candidate is over 100 km from both the coordinate and the place named in the text (done 22 Oct) |
| 8 | SLIP matched SLIPPED | Berth rule now matches SLIP and SLIPS only. No incident changed |
| 9 | 2024 AIS moved host | Read from NOAA's blob host; recorded in the README |
| 10 | One ship, two MMSIs | Merged by IMO number (section 2) |
