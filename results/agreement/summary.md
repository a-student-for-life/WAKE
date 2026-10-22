# Blind review agreement (first answers, before any discussion)

Generated from `data/janice_review.csv` and `data/claude_review.csv` (410 cases).

Rows: Janice. Columns: Claude.

| | no | unsure | yes |
| --- | --- | --- | --- |
| no | 5 | 0 | 1 |
| unsure | 84 | 5 | 29 |
| yes | 11 | 11 | 264 |

- Yes versus not-yes: agreement 87.3%, Cohen's kappa 0.69.
- All three answers: agreement 66.8%, Cohen's kappa 0.32.
- Both yes (confirmed before the second look): 264.
- Disagreements where one rater said yes (go to the second look): 52 (`second_look_cases.csv`).
- Disagreements between no and unsure only: 84; both answers exclude the case, so inclusion does not depend on them.
