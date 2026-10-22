# Stage A: issues found while building and reviewing (for Janice)

Recorded as they came up; nothing here changes the spec. Each point names the
cases in `data/claude_review.csv` or `data/incidents.csv` where it showed.

1. **IncidentNews dates and the UTC window.** IncidentNews has only a local date, so
   the AIS window is that date and the day before, read as UTC days. For Hawaii and
   Alaska the local afternoon and evening fall on the next UTC day and are not
   scanned (I8871 NALANI: still in harbour at 23:59 UTC, sinking later that local
   day). Adding the following UTC day for IncidentNews records west of UTC-5 would
   close this.
2. **Name normalisation.** The spec's prefix list does not strip `THE`, `USNS`,
   `MS`, `VESSEL`, `TUG BOAT` or `TOW BOAT`. 37 NRC names start with one of these (e.g. THE
   WESTERLY, VESSEL SEA DRAGON II, TUG BOAT RIKKI S); USNS BLACK POWDER only matched
   loosely.
3. **Duplicates the 2-day name rule misses.** Spelling variants across sources
   (EMILY ANN / EMILY ANNE: N1140536 and I9233_1; GRACIE CLAIR / GRACIE CLAIRE:
   N1188130 and I9553) and two NRC reports of one event (CARMELA: N1157864 and
   N1157868) stay as separate incidents. They should count once in the analysis.
4. **IncidentNews names that are not the incident vessel.** The extraction keeps
   every named vessel, including a tug that only reported a sheen (I9275 ARTHUR
   BRUSCO) and the tug of a grounded barge (I9491 NACHIK). Claude's review answers
   only "is this the named vessel", so these are yes; they may need excluding.
5. **Berth and maintenance events that pass the filters.** HOS BRIMSTONE (propeller
   maintenance, moored), GRANDEUR OF THE SEAS (lifeboat fell at the berth), WILD
   COSMOS, HARBOUR BRIDGE and MOL MAXIM (alongside) are not moving-vessel incidents.
   IncidentNews has no berth filter at all.
6. **Hurricane cases without the tag.** I9671 FERREL (Hurricane Maria) is not tagged
   Hurricane in IncidentNews, so the tag filter misses it.
7. **Wrong reference coordinates.** Several NOAA/NRC coordinates are off while the
   place text is right: I8930 AUBI (141 km), I9183 GLOBAL GOLD (38 km), I9713 MAERSK
   WOLFSBURG (9 km), I9685 OLE BETTS SEA (60 km), N1213882 CAP REINGA (latitude 40.14
   for 40.64). The 100 km auto-reject is safe for these, but a stricter one would not
   be.
8. **`SLIP` in the berth rule** also matches SLIPPED / SLIPPING in descriptions
   (spec rule 5), which may drop some moving-vessel incidents.
9. **2024 AIS source.** Since October 2026 the 2024 daily zips on coast.noaa.gov return
   404 although the directory still lists them. The same days are on NOAA's blob host
   (`noaaocm.blob.core.windows.net/ais/csv2/csv2024/ais-2024-MM-DD.csv.zst`, the 2025
   format), so `match_ais.py` reads 2024 from there.
10. **One ship, two MMSIs.** MASCO ENDEAVOR (N1352613 / N1352623) appears under two
    MMSIs with the same IMO (8987905), one replacing the other the day before the
    incident. Claude marked the MMSI transmitting at the report time yes and the other
    unsure; the analysis should treat them as one vessel.

## Decisions (22 Oct 2026)

All ten are settled; the decisions and their effect are in section 9 of
`ANALYSIS_PLAN.md`. Code changes: `stage_a/names.py` (prefixes, #2),
`stage_a/build_incidents.py` (SLIP rule #8; `berth_flag`, `storm_flag`, and an
`alt_lat/alt_lon` point from the place text, #5–7), `stage_a/match_ais.py` (three UTC
days for date-only records #1; auto-reject needs both points over 100 km #7).
Duplicates, non-source vessels, berth and storm events and two-MMSI ships are handled
at analysis (#3–6, #10). #9 needed no change beyond what is already in `match_ais.py`.
