"""B1: event table (STAGE_B_SPEC.md).

usage: python3 -I stage_b/build_events.py
reads  data/confirmed_events.csv, data/incidents.csv, data/candidates.csv, data/tracks/
writes data/stage_b/events.csv  (one row per vessel event)

Rules (spec B1):
- T, NRC: time_utc from data/incidents.csv (local time, confirmed by results/time_check.md).
- T, IncidentNews: 00:00 local on date_local, converted to UTC with the record's tz; an
  empty tz is taken from the reference longitude (spec rule, `zone_from_point`).
- An event with several reports uses the earliest report (smallest T) and, within it,
  the match whose MMSI transmitted closest to the report time (candidates.csv
  near_report_gap_h).
- Scenarios: real = T, placebo30 = T - 30 d, placebo60 = T - 60 d.
- main_exclude: the event is excluded when every match in it is flagged (gives the 257
  events of the main analysis); main_exclude_any records events with a mixed coding.

Gaps filled (DEVIATIONS.md #3): a report with no reference point takes the vessel's own
median AIS position on the report's local date (data/tracks/) as reference point
(ref_source = ais_track_median). The one NRC record with no time_utc (N1414867, Canada,
no tz) gets its zone from that point with the spec's longitude rule, and T = time_local
in that zone.
"""
import gzip
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

OUT = "data/stage_b/events.csv"


def zone_from_point(lat, lon):
    lat, lon = float(lat), float(lon)
    if lat < 30 and lon < -150:
        return "Pacific/Honolulu"
    if lat < 20 and lon > -68:
        return "America/Puerto_Rico"
    if lon > -87:
        return "America/New_York"
    if lon > -101:
        return "America/Chicago"
    if lon > -114:
        return "America/Denver"
    if lon > -130:
        return "America/Los_Angeles"
    return "America/Anchorage"


def to_utc(local_str, tz):
    t = datetime.strptime(local_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    return t.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def track_median(incident_id, mmsi, day):
    p = f"data/tracks/{incident_id}_{mmsi}.csv.gz"
    if not os.path.exists(p):
        return None
    t = pd.read_csv(gzip.open(p))
    d = t[t.time.str[:10] == day]
    if d.empty:
        d = t
    return float(d.lat.median()), float(d.lon.median())


def report_time(r):
    """(T_utc, T_rule, ref_lat, ref_lon, ref_source, tz_used)"""
    ref_lat, ref_lon, ref_src = r.ref_lat, r.ref_lon, "incident"
    if not ref_lat or not ref_lon:
        m = track_median(r.incident_id, r.mmsi, r.date_local)
        ref_lat, ref_lon, ref_src = (m[0], m[1], "ais_track_median") if m else ("", "", "none")
    if r.source == "NRC":
        if r.time_utc:
            return datetime.strptime(r.time_utc, "%Y-%m-%d %H:%M"), "nrc_time_utc", ref_lat, ref_lon, ref_src, r.tz
        tz = r.tz or zone_from_point(ref_lat, ref_lon)
        return (to_utc(f"{r.date_local} {r.time_local}", tz), "nrc_local_tz_from_ais",
                ref_lat, ref_lon, ref_src, tz)
    if r.tz:
        tz, rule = r.tz, "in_midnight_local_record_tz"
    else:
        tz, rule = zone_from_point(ref_lat, ref_lon), "in_midnight_local_tz_from_lon"
    return to_utc(f"{r.date_local} 00:00", tz), rule, ref_lat, ref_lon, ref_src, tz


def main():
    ev = pd.read_csv("data/confirmed_events.csv", dtype=str, keep_default_na=False)
    inc = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False)
    cand = pd.read_csv("data/candidates.csv", dtype=str, keep_default_na=False)
    gap = {(a, b): (float(g) if g else float("inf"))
           for a, b, g in zip(cand.incident_id, cand.mmsi, cand.near_report_gap_h)}
    keep = ["incident_id", "tz", "time_local", "ref_lat", "ref_lon"]
    m = ev.merge(inc[keep], on="incident_id", how="left", validate="many_to_one")
    assert len(m) == len(ev)

    rows = []
    for r in m.itertuples(index=False):
        T, rule, lat, lon, src, tz = report_time(r)
        rows.append(dict(r._asdict(), Tutc=T, T_rule=rule, rlat=lat, rlon=lon, rsrc=src, tz_used=tz,
                         gap=gap.get((r.incident_id, r.mmsi), float("inf"))))
    m = pd.DataFrame(rows)

    out = []
    for eid, g in m.groupby("event_id", sort=False):
        g = g.sort_values(["Tutc", "gap", "incident_id"])
        first = g[g.Tutc == g.Tutc.iloc[0]].sort_values(["gap", "incident_id"]).iloc[0]
        T = first.Tutc
        out.append({
            "event_id": int(eid),
            "mmsi": first.mmsi,
            "mmsis": ";".join(sorted(set(g.mmsi))),
            "imo": first.imo,
            "incident_id": first.incident_id,
            "incident_ids": ";".join(g.incident_id),
            "n_reports": len(g),
            "T_utc": T.strftime("%Y-%m-%d %H:%M"),
            "T_rule": first.T_rule,
            "tz_used": first.tz_used,
            "source": first.source,
            "sources": ";".join(sorted(set(g.source))),
            "setting": first.setting,
            "incident_type": first.incident_type,
            "main_exclude": bool((g.main_exclude == "True").all()),
            "main_exclude_any": bool((g.main_exclude == "True").any()),
            "first_pass_both_yes": bool((g.route == "both yes, first pass").all()),
            "ref_lat": first.rlat,
            "ref_lon": first.rlon,
            "ref_source": first.rsrc,
            "T_real": T.strftime("%Y-%m-%d %H:%M"),
            "T_placebo30": (T - timedelta(days=30)).strftime("%Y-%m-%d %H:%M"),
            "T_placebo60": (T - timedelta(days=60)).strftime("%Y-%m-%d %H:%M"),
        })
    out = pd.DataFrame(out).sort_values("event_id")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"{len(out)} events, {int((~out.main_exclude).sum())} in the main analysis, "
          f"{int(out.main_exclude.sum())} excluded; T rules: {out.T_rule.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
