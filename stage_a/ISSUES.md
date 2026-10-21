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
