# Stage A spec (experiments 1–2)

Every working session follows this file. Read `PROGRESS.md` first, do the next
unfinished step, log it, commit, push. Never skip ahead to Stage B.

## Ground rules

- Commit as `Janice Miranda <38janice10b@gmail.com>`. **No `Co-Authored-By` or other
  attribution lines** in commit messages, and add no collaborators: Janice adds
  contributors herself later.
- `git pull --rebase origin main` before every push. Commit after every finished
  unit of work (a year of incidents, a batch of AIS days), so a cut-off session
  loses little.
- Raw downloads go in `data/raw/` (git-ignored). Commit only derived tables and code.
- Every number written to `PROGRESS.md` or `results/` must come from a file in the repo.
- Stop a session after about 3 hours of work, at a clean commit.
- Keep Claude's match decisions in `data/claude_review.csv` only. Never put them in
  anything that feeds Janice's review page: her review is blind.

## Experiment 1: incident table (`stage_a/build_incidents.py` -> `data/incidents.csv`)

Years: 2015–2025 (incident dates). 2026 is out of scope.

**NRC** (`https://nrc.uscg.mil/FOIAFiles/CY<yy>.xlsx`; download with
`tools/chunked_get.sh`, which retries 2 MB ranges because the server drops long
transfers). Sheets: CALLS, INCIDENT_COMMONS, VESSELS_DETAIL, MATERIAL_INVOLVED,
joined on SEQNOS. Older years have fewer VESSELS_DETAIL columns (no FLAG,
IS_VESSEL_AGROUND); handle missing columns. Keep a record when all hold:

1. VESSEL_NAME present and not unknown/N/A.
2. VESSEL_TYPE not PLEASURE CRAFT, MILITARY, UNKNOWN, OTHER, BARGE, or MODU.
3. A material matching OIL|DIESEL|FUEL|GASOLINE|HYDRAULIC|LUBE|BUNKER|PETROLEUM|CRUDE
   with IF_REACHED_WATER = yes.
4. DESCRIPTION_OF_INCIDENT matches AGROUND|GROUND|COLLI|ALLISION|UNDERWAY|UNDER WAY|
   TRANSIT|STRUCK|SANK|SINK|CAPSIZ.
5. Neither DESCRIPTION_OF_INCIDENT **nor INCIDENT_LOCATION** matches
   MOORED|PIER|DOCK|BERTH|MARINA|SHIPYARD|REFUEL|FUELING|DRYDOCK|SLIP (the pilot
   missed a pier named only in INCIDENT_LOCATION).

Also write `data/incidents_nrc_excluded_counts.csv`: how many records each rule
removed, per year.

**IncidentNews** (`https://incidentnews.noaa.gov/raw/incidents.csv`): records from
2015–2025 whose name or description names a vessel (prefixes M/V, F/V, T/V, M/T, S/V,
P/V, R/V, OSV, tug, towboat, tank vessel, tank barge, cargo vessel, container ship,
fishing vessel). Keep every extracted name as a candidate. Exclude records tagged
Pipeline, Wellhead, Railcar or Hurricane.

**Positions.** NRC LAT/LONG degrees-minutes-seconds to decimal when present and inside
US waters (lat 17–72, lon -180 to -64); `ref_method = exact`. Otherwise geocode
LOCATION_NEAREST_CITY + LOCATION_STATE with the GeoNames US gazetteer
(`https://download.geonames.org/export/dump/US.zip`, feature class P first, then
H/L/S names such as passes, sounds and harbours), and apply DISTANCE_FROM_CITY and
DIRECTION_FROM_CITY when given; `ref_method = town` or `town+offset`. Unresolvable:
`ref_method = none` (kept; matched on name and state only, flagged).

**Times.** NRC INCIDENT_DATE_TIME is assumed to be local time at the incident. Convert
to UTC with the state's main IANA time zone (zoneinfo, DST-aware). Keep the local time,
the zone used and `time_assumed_local = true`. IncidentNews has dates only.

**Coding.** `incident_type` by keywords: grounding, collision_allision, sinking_capsize,
fire_explosion, discharge, equipment_failure, other. `setting`: inland if
INCIDENT_LOCATION or description names a RIVER, BAYOU, CANAL, LOCK or LAKE, else sea.
Spill amount and units as given.

**Duplicates.** Same normalised vessel name within 2 days across sources = one
incident; keep the NRC record as primary and list the IncidentNews id.

Output columns at least: incident_id, source, source_id, linked_ids, vessel_name,
name_norm, vessel_type_reported, length_ft, flag, aground, date_local, time_local, tz,
time_utc, state, place_text, ref_lat, ref_lon, ref_method, incident_type, setting,
material, amount, units, description. Summary counts by source, year, type and setting
in `results/exp1/summary.md`.

## Experiment 2: AIS matching (`stage_a/match_ais.py`)

For each incident, search the national AIS for the incident's UTC day and the day
before (2015–2024 zips at `coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/`; 2025
`.csv.zst` at `noaaocm.blob.core.windows.net/ais/csv2/csv2025/`; `pip install
zstandard`). Download each needed day once, read it in chunks (the full day does not
fit in memory), keep only rows whose normalised VesselName matches a needed name,
delete the raw file. Track progress in `data/stage_a_state.json` (days done), commit
after every 10 days.

Name normalisation: upper case, drop prefixes (M/V, MV, F/V, FV, M/T, MT, T/V, TUG,
OSV, S/V), keep A–Z and 0–9 only. Exact matches are candidates; "loose" matches (needed
name contained in the AIS name, at most 4 extra characters, needed name at least 5
characters) are candidates flagged `loose`.

For each candidate (incident, MMSI) save its track for both days to
`data/tracks/<incident_id>_<mmsi>.csv.gz` (MMSI, time, lat, lon, SOG, COG, heading,
name, type, length, status) and compute: closest distance to the reference point,
distance at the report time (or at the nearest-in-time position, with the gap in
hours), AIS type and length against the report, and how many other vessels with the
same name were heard that day and how far away.

Auto-reject, with the reason recorded: closest distance above 100 km when
`ref_method` is exact, town or town+offset. Everything else goes to review.
Write `data/candidates.csv` (one row per candidate, all facts, no decisions).

## Claude's review (`data/claude_review.csv`)

Write `stage_a/REVIEW_RULES.md` before reviewing anything: the five checks from the
demo page (name, type, size, place and time, behaviour), what makes a case yes, no or
unsure, and how to treat missing AIS near the report time. Then review every
candidate in `data/candidates.csv` one case at a time, reading its facts and track,
and record decision (yes / no / unsure) and a one-sentence reason. Do not hand the
decisions to a script that applies a threshold: the point is a considered judgement
per case.

## When Stage A is done

Stage A is done when `data/incidents.csv`, `data/candidates.csv`,
`data/claude_review.csv` and `stage_a/REVIEW_RULES.md` exist and are complete. Then:

1. Write `results/stageA_summary.md`: incidents by source and year, candidates,
   auto-rejections by reason, Claude's yes / no / unsure counts, and the projected
   number of confirmed vessels.
2. Update `PROGRESS.md`: "Stage A complete. Waiting for Janice: analysis plan approval
   and blind review." 
3. Send Janice a short notification saying Stage A is done and what the projected
   sample size is.
4. Later sessions that find Stage A complete do nothing else: they log a one-line
   check in `PROGRESS.md` only if something changed, and stop. The review page is
   built in a session with Janice, because her answers need to be stored where Claude
   can read them.
