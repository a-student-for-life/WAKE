"""Gap check 1: events for the matches that end as "unsure" (plan section 8, "unsure
cases added back"), which B1 left out because it reads data/confirmed_events.csv only.

usage: python3 -I gap_checks/unsure_events.py
reads  data/second_look.csv, data/incidents.csv, data/candidates.csv,
       data/confirmed_events.csv, data/tracks/
writes data/gap_checks/unsure_coding.csv, data/gap_checks/unsure_events.csv

Same rules as B1 (stage_b/build_events.py, whose T rule is reused unchanged) and as the
event coding of data/event_coding.csv (exclusions 1-3, coded by Claude from the report
text and the AIS track before any detector is run on these vessels). None of the 8
vessels shares an IMO or MMSI with a confirmed event, so each is its own event;
event ids start at 1001 so they never collide with the 283 main events.
"""
import os
import sys
from datetime import timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage_b"))
from build_events import report_time  # noqa: E402

OUT = "data/gap_checks"

# incident_id: (role, context, storm, note) - read from the report text and AIS track
CODING = {
    "I10529": ("source", "moving_or_anchored", "no", "fishing vessel sank 55 NM offshore"),
    "N1410714": ("source", "moving_or_anchored", "yes", "bulk carrier aground in Hurricane Francine"),
    "I9785": ("source", "moving_or_anchored", "no", "fire aboard fishing vessel 38 NM offshore"),
    "I9608": ("source", "moving_or_anchored", "no",
              "tug dragged anchor in heavy waves and grounded; no named storm"),
    "I9574_1": ("source", "moving_or_anchored", "no", "collision of two fishing vessels"),
    "N1407744": ("source", "moving_or_anchored", "no", "fishing vessel sank 100 NM offshore"),
    "I8871": ("source", "moving_or_anchored", "no", "tug sank offshore"),
    "N1443121": ("source", "berth", "no",
                 "sank at its moorage (last AIS stationary in Salmon Bay, Seattle, 32 h "
                 "before); discharge while being raised"),
}


def main():
    sl = pd.read_csv("data/second_look.csv", dtype=str, keep_default_na=False)
    un = sl[sl.final == "unsure"][["incident_id", "mmsi"]]
    inc = pd.read_csv("data/incidents.csv", dtype=str, keep_default_na=False)
    cand = pd.read_csv("data/candidates.csv", dtype=str, keep_default_na=False)
    ce = pd.read_csv("data/confirmed_events.csv", dtype=str, keep_default_na=False)
    assert set(un.incident_id) == set(CODING), "coding table does not cover the unsure matches"
    m = un.merge(inc, on="incident_id", how="left", validate="one_to_one")
    m = m.merge(cand[["incident_id", "mmsi", "ais_imo"]], on=["incident_id", "mmsi"], how="left")
    cod, rows = [], []
    for k, r in enumerate(m.sort_values("incident_id").itertuples(index=False)):
        role, ctx, storm, note = CODING[r.incident_id]
        excl = role in ("not_source", "unclear") or ctx == "berth" or storm == "yes"
        cod.append(dict(incident_id=r.incident_id, mmsi=r.mmsi, role=role, context=ctx,
                        storm=storm, coded_by="Claude, read", note=note, main_exclude=excl))
        imo = r.ais_imo.replace("IMO", "")
        assert not ((ce.mmsi == r.mmsi).any() or (imo and (ce.vkey == imo).any()))
        T, rule, lat, lon, src, tz = report_time(r)
        rows.append({
            "event_id": 1001 + k, "mmsi": r.mmsi, "mmsis": r.mmsi, "imo": imo,
            "incident_id": r.incident_id, "incident_ids": r.incident_id, "n_reports": 1,
            "T_utc": T.strftime("%Y-%m-%d %H:%M"), "T_rule": rule, "tz_used": tz,
            "source": r.source, "sources": r.source, "setting": r.setting,
            "incident_type": r.incident_type, "main_exclude": excl, "main_exclude_any": excl,
            "first_pass_both_yes": False, "ref_lat": lat, "ref_lon": lon, "ref_source": src,
            "T_real": T.strftime("%Y-%m-%d %H:%M"),
            "T_placebo30": (T - timedelta(days=30)).strftime("%Y-%m-%d %H:%M"),
            "T_placebo60": (T - timedelta(days=60)).strftime("%Y-%m-%d %H:%M"),
        })
    os.makedirs(OUT, exist_ok=True)
    pd.DataFrame(cod).to_csv(f"{OUT}/unsure_coding.csv", index=False)
    ev = pd.DataFrame(rows)
    ev.to_csv(f"{OUT}/unsure_events.csv", index=False)
    print(ev[["event_id", "incident_id", "mmsi", "T_utc", "T_rule", "main_exclude"]].to_string(index=False))


if __name__ == "__main__":
    main()
