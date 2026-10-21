# WAKE — Were Anomalies Known Early?

Do standard AIS anomaly detectors single out vessels involved in oil incidents
once they are compared with vessels that were tracked about as heavily?

Most AIS-triggered satellite monitoring, TARS included, assumes that anomalous
vessel behaviour points to polluters. In the TARS replay (55 incidents), an
apparent signal disappeared once vessels were matched on how many AIS reports
they produced (median 381 vs 139). This study tests the question properly:
more incidents, a panel of standard detectors, exposure-matched controls,
placebo dates and a pre-registered analysis.

Private until publication.

## Layout

| Path | What it holds |
| --- | --- |
| `pilot/` | 21 Oct 2026 feasibility pilot: incident counts, NRC filters, AIS name matching, power analysis |
| `review_page/` | Blind match-review page (`demo.html` = five real 2023 cases) and the script that builds it |
| `data/raw/` | Downloaded source files (not committed; see `.gitignore`) |
| `data/` | Small derived tables that are committed (incident list, match table) |
| `results/` | Result files, one folder per experiment |
| `PROGRESS.md` | Stage-by-stage log, so each working session picks up where the last stopped |

## Data sources

- NOAA ORR IncidentNews: `https://incidentnews.noaa.gov/raw/incidents.csv`
- USCG National Response Center annual reports: `https://nrc.uscg.mil/FOIAFiles/CY<yy>.xlsx`
- NOAA/BOEM Marine Cadastre national AIS:
  2015–2024 `https://coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/AIS_<yyyy>_<mm>_<dd>.zip`,
  2025 onward `https://noaaocm.blob.core.windows.net/ais/csv2/csv<year>/ais-<yyyy>-<mm>-<dd>.csv.zst`

Raw AIS days (~300 MB each) are deleted after processing; they can be
downloaded again from the URLs above, so every result is reproducible.
