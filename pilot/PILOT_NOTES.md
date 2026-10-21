# Pilot, 21 Oct 2026

## Incident sources

- IncidentNews: 4,946 records in total. Records naming a vessel (regex on name and
  description): 81 (2015), 81 (2016), 84 (2017), 75 (2018), 84 (2019), 88 (2020),
  78 (2021), 68 (2022), 65 (2023), 77 (2024), 65 (2025). (`vessel.py`)
- Earlier TARS replay: 382 IncidentNews incidents naming a vessel (2018–2024) gave
  60 vessels identified in AIS, 55 analysable.
- USCG NRC, commercial vessels (not pleasure, military, barge, MODU, unknown), named,
  oil reaching water, description suggesting a moving or distressed vessel and not
  at a berth or refuelling: 58 (2019), 75 (2023), 89 (2024). (`nrccount.py`)
- NRC files downloaded for 2019, 2023, 2024. CY15, CY16, CY17, CY22 timed out on the
  first attempt; CY18, CY20, CY21 returned headers but did not complete; CY25 exists
  (HTTP 206 on a range request). Retry needed.
- Filter gap found in the demo: the berth filter only reads the description, so a
  vessel sunk "at Johnson Pier" (INCIDENT_LOCATION field) passed. Stage A must also
  read INCIDENT_LOCATION.

## AIS name matching (13 random 2023 NRC cases, one had no name)

Exact name found in that day's national AIS and plausibly near the reported place:
ROBERT T. (Columbus KY), BLUE DOLPHIN (offshore LA), SUPREME VALOR (Sabine Pass),
MISS KARA (Nantucket Sound). Same name but wrong place: CHRISTINE, CRICKET.
Not found: the other six. Rough identification rate about 30%.

## AIS availability

- 2015–2024: daily zips, 365/366 files a year, about 265–320 MB each.
- 2025: `.csv.zst` daily files on the new host, 365 files. 2026 directory exists.
- Download speed from the workspace: about 3.5 MB/s, so 1.5–2 min a day file.

## Power (`power.py`, output in `power_output.txt`)

Ranking test, involved vessel against 10 matched controls, two-sided:

| AUC | n = 90 | 120 | 200 | 300 |
| --- | --- | --- | --- | --- |
| 0.55 | 0.34 | 0.41 | 0.60 | 0.78 |
| 0.60 | 0.86 | 0.95 | 0.99 | 1.00 |
| 0.65 | 1.00 | 1.00 | 1.00 | 1.00 |

At alpha 0.01 (five detectors), AUC 0.60 needs about 120 vessels for 80% power.
A binary flag at a 1% alarm budget is too weak to be the main test.

## Demo review (`review_page/demo.html`)

Janice and Claude agreed on 4 of 5 demo cases; MISS KARA was yes (Janice) vs
unsure (Claude). NRC times are assumed to be local time; this needs checking.
