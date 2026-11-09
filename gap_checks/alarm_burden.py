"""Approximate national alarm burden per incident vessel flagged (exploratory, descriptive).

Added after all results were known (DEVIATIONS.md 9). Not a test.

Assumptions, stated in the paper:
- national fleet per day = median `fleet_n` over the fleet reference days of the real-date
  windows (vessels with at least 10 positions in that day's national file, the population whose
  percentiles set the alarm thresholds);
- incidents per year = 1,247 incidents in the combined table / 11 years (2015-2025);
- the incident flag rates measured in the matched sets apply to all incidents;
- detectors 1-5 alarm on the top 1%, 5% or 10% of the national fleet; GeoTrackNet's fleet-wide
  flag rate was not measured, so its control flag rate stands in for it.

usage: python3 gap_checks/alarm_burden.py   (from the repository root)
writes results/gap_checks/alarm_burden.csv
"""
import glob

import pandas as pd

N_INCIDENTS, N_YEARS = 1247, 11

fleet = pd.concat(pd.read_csv(f, usecols=["fleet_day", "fleet_n"]).drop_duplicates()
                  for f in glob.glob("data/stage_b/windows/*_real.csv.gz")).drop_duplicates()
fleet_n = float(fleet.fleet_n.median())
per_year = N_INCIDENTS / N_YEARS

rows = []
fr = pd.read_csv("results/stageB/tables/flag_rates.csv")
for r in fr.itertuples():
    share = float(r.top.rstrip("%")) / 100
    rows.append((r.detector, r.top, share * fleet_n, r.inc_flagged))
g = pd.read_csv("results/gtn/tables/flag_rates.csv").iloc[0]
rows.append(("d7_gtn", "NFA<1e-9", g.ctrl_flagged * fleet_n, g.inc_flagged))

out = pd.DataFrame(rows, columns=["detector", "alarm_level", "alarms_per_day", "incident_flag_rate"])
out["incident_vessels_flagged_per_year"] = out.incident_flag_rate * per_year
out["alarms_per_incident_vessel_flagged"] = (out.alarms_per_day * 365
                                             / out.incident_vessels_flagged_per_year)
out["fleet_n_median"] = fleet_n
out["fleet_days"] = len(fleet)
out["incidents_per_year"] = per_year
out.to_csv("results/gap_checks/alarm_burden.csv", index=False)
print(f"fleet reference days {len(fleet)}, median fleet {fleet_n:,.0f}, incidents/year {per_year:.1f}")
print(out[["detector", "alarm_level", "alarms_per_day", "incident_flag_rate",
           "incident_vessels_flagged_per_year", "alarms_per_incident_vessel_flagged"]]
      .round(3).to_string(index=False))
