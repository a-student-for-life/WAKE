# Claude's review rules (Stage A)

Written before any candidate is reviewed. Claude applies these to every row of
`data/candidates.csv` that is not auto-rejected, one case at a time, after reading the
row's facts, the incident record in `data/incidents.csv` (description, place, time) and
the track in `data/tracks/<incident_id>_<mmsi>.csv.gz`. Decisions and a one-sentence
reason go to `data/claude_review.csv` (incident_id, mmsi, decision, reason, checks)
and nowhere else: nothing here feeds Janice's blind review page.

The question for each case: **is this MMSI the vessel named in the incident report?**

## The five checks (same as the demo review page)

1. **Name.** The AIS name matches the report after normalisation. Punctuation, spacing
   and prefixes (M/V, F/V, TUG) do not matter. A `loose` match (report name contained
   in a longer AIS name) passes only if the extra characters are a plausible suffix
   (a hull number, "II", a company prefix) and nothing else contradicts it.
2. **Type.** The AIS ship type fits the reported type: fishing 30; towing 31/32/52;
   tug/tow boat 31/32/52 (or 0/blank, which is common on small US working boats);
   tanker 80–89; cargo/freight/container/bulk 70–79; passenger/ferry/cruise 60–69;
   offshore supply 90–99 or 52/0. A clear contradiction (report fishing vessel,
   AIS cargo ship; report tanker, AIS pleasure craft 37) counts against.
   Marine Cadastre files before 2018 often carry the older 1001–1025 codes. Only
   the clear ones are used: 1001 commercial fishing, 1004 freight ship, 1019
   recreational. 1025 appears on tugs and fishing vessels alike and is treated as
   unknown (neutral); other 10xx codes are treated as weak evidence only.
3. **Size.** AIS length within about 15% of the reported length (feet converted to
   metres). Missing length on either side is neutral. A difference over 30% counts
   against; 15–30% is weak evidence against.
4. **Place and time.** The vessel was near the reference point around the report time.
   - `exact` reference: closest approach within 5 km (open water) or 3 km (river)
     supports; 5–25 km is weak; beyond 25 km counts against unless the track is
     clearly heading to or from the spot and AIS ends before reaching it.
   - `town` / `town+offset` reference: within about 15 km of the town on a river or
     coast supports, up to 40 km is weak, further counts against unless the
     description places the incident offshore of that town (then up to the reported
     offset plus 20 km).
   - `none` reference: place is judged from the report's state and place text against
     where the track is. Without a place match a `none` case cannot be yes.
   - The report time is assumed local and converted to UTC (`time_assumed_local`);
     a one-hour DST slip or a report filed hours after the event is not a mismatch.
     IncidentNews has only a date; then the two scanned days are the window.
5. **Behaviour.** The track fits what happened: a grounding or sinking should end or
   stop near the spot (SOG near 0, or AIS ends); a collision/allision should show a
   stop or abrupt change near the spot; a vessel underway when a discharge is
   reported should be moving there. Behaviour that clearly contradicts the event
   (steaming past at full speed long after a reported sinking) counts against.

## Missing AIS near the report time

Gaps are common on rivers, offshore and for small vessels, and AIS often stops when
a vessel sinks or loses power. A gap is **not** a no by itself. If the track ends or
starts within about 12 hours of the report time and the nearest position is
consistent with the place, the place-and-time check is weak support, not a failure.
If the nearest-in-time position is more than 12 hours away, place-and-time rests on
the closest approach alone and the case can be at most unsure unless name, type and
size all fit and the vessel was within the supporting distance.

## Decisions

- **yes**: name passes, place and time supports (or weak support with a gap as
  above), and no other check counts against. Type and size must not contradict;
  missing type/size is acceptable when place and time is strong (under 5 km at
  an exact reference, or the vessel stopped where the report says).
- **no**: any clear contradiction that cannot be explained: wrong place (beyond
  the distances above with no route to the spot), wrong vessel type, size off by
  more than 30% with a common name, or another vessel with the same name fits
  clearly better (then the better one may be yes and this one no).
- **unsure**: the facts point both ways, or they are too thin (a `none`
  reference with only a state match, weak place support with missing type and
  size, two same-name vessels both near).

At most one MMSI per incident is yes. If two candidates both pass, both are
unsure unless one is clearly better on place and time.

Each decision gets one sentence naming the deciding facts (distance, type, length,
gap), so Janice can later compare her reasons with Claude's.
