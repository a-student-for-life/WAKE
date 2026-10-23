# Stage B notes

## Detector 6 (TARS layers)

Left empty (`d6_tars` is blank in every window file). The spec asks to attach
`a-student-for-life/TARS-triage` read-only with `add_repo`; in the session of 22 Oct 2026
(B1/B2 start) no `add_repo` or `list_repos` tool was available, and the session's GitHub
access is scoped to the WAKE repository only, so the TARS code could not be attached.
As the spec allows, detector 6 is left empty; the main analysis (detectors 1–5) does not
depend on it. A later session that can attach the repository may fill it in.

## Implementation choices in B2 not fixed by the plan or spec

Written before any window file was produced; also in the docstring of
`stage_b/windows.py`.

- Windows are half-open: pre-T windows [start, end), after12 [T, T+12 h).
- Days covering T-48 h..T are required; a day missing from the AIS hosts (HTTP 404, e.g.
  2014, which has no daily files) makes the event-scenario impossible, recorded in
  `data/stage_b/state.json`. Days that only cover (T, T+12 h] are optional; when missing,
  after12 and the box use what exists and `after_days_missing` names the day.
- Hours observed sum gaps <= 1 h; distance sailed sums all consecutive great-circle steps;
  speed-drop and turn-rate pairs need 0 < gap <= 10 min.
- Speed drop = max(0, largest fall), 0 when no qualifying pair.
- Loitering: runs of consecutive positions with SOG < 2 kn, each within 1 km of the run's
  first position, broken by a gap > 1 h, a position within 3 km of a stationary place, or
  a position at >= 2 kn; score = longest run (hours).
- AIS gap: longest silence starting at SOG >= 3 kn (hours) divided by the gap norm of the
  0.25-degree cell of the vessel's median position (day median for the fleet, window
  median for windows); 0 when the vessel has no such silence. The norm uses vessels with
  at least one such silence that day.
- Off-lane: per position -log(1 + other vessels in the 0.01-degree cell on the reference
  day), "other" = distinct vessels there that day minus the vessel itself if it was there;
  mean over positions.
- Isolation Forest features without a defined value (no valid SOG, fewer than 2
  turn-rate pairs) are set to 0. Turn rate = wrapped COG change per minute.
- Type group and length per window, falling back to the vessel's value over the whole
  T-48 h..T+12 h span when the window has none (type 0 counts as missing).
- Candidate exclusion uses every row of `data/candidates.csv` (including auto-rejected
  ones) whose incident time (time_utc, else date_local 00:00) is within 30 days of T,
  matched on MMSI or on the vessel's most common AIS IMO.
- Box vessels with no positions in a window still get a row (n_pos 0, no scores); the
  incident vessel always gets rows, even with no AIS.
- A national day file with fewer than 1,000,000 positions is treated as missing
  (DEVIATIONS.md #4; first case 2015-03-15 with 5,049 positions).

## Implementation choices in B3 (matching)

Written before any detector score was loaded; also in the docstring of `stage_b/match.py`.

- Window `main` only; the same matched sets are used for the other windows in B4.
- Pool for every definition: box vessels, not the incident vessel, not candidate-excluded,
  at least 10 positions (30 in `M4_min30`), positions within 25% of the incident vessel's.
- M1: whole box, log positions. M2: + log(1 + hours). M3: + exact type group and log
  length. M4 (main): M3 within 50 km (median main-window position), widened to the whole
  box (150 km) when fewer than 10 qualify. `M4_k5`, `M4_k20`, `M4_min30` for the checks.
- Mahalanobis covariance from the qualifying pool (pseudo-inverse). Length left out when
  the incident vessel has none; a control without length is compared on the other
  variables. Ties in distance broken by MMSI.
- Fewer than 5 controls, or an incident vessel below the position minimum: the set is
  dropped and its reason written to `data/stage_b/matched/sets.csv`.
