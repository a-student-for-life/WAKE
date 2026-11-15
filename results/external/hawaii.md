# External check: HawaiiCoast_GT (external/HAWAII_PLAN.md)

Events 145 (T rule: {'report_time': 85, 'midnight_hst': 60}); window files 287; M4 sets on the true date 52 (placebo30 53).

Vessel class of matched events: {'Tug Tow': 22, 'Fishing': 16, 'Passenger': 4, 'Pleasure Craft/Sailing': 3, 'Research Vessel': 2, 'Offshore supply vessel': 1, 'Industrial Vessel': 1, 'Tanker': 1, 'Cargo': 1, 'Other': 1}

AIS evidence of matched events: {'Good evidence': 21, 'High evidence': 15, 'No obvious evidence': 12, 'Some evidence': 4}

| Scenario | Window | Detector | Sets | Pairs | AUC | 95% interval | Perm. p | Holm p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| real | main | 1 Speed drop | 52 | 433 | 0.659 | 0.574-0.744 | 0.0005 | 0.0025 |
| real | main | 2 Loitering | 52 | 433 | 0.535 | 0.459-0.614 | 0.3444 | 0.6887 |
| real | main | 3 AIS gap | 52 | 433 | 0.554 | 0.461-0.653 | 0.1857 | 0.5570 |
| real | main | 4 Off-lane | 52 | 433 | 0.535 | 0.447-0.622 | 0.4405 | 0.6887 |
| real | main | 5 Isolation Forest | 52 | 433 | 0.627 | 0.537-0.713 | 0.0054 | 0.0216 |
| real | early3 | 1 Speed drop | 52 | 433 | 0.574 | 0.492-0.653 |  |  |
| real | early3 | 2 Loitering | 52 | 433 | 0.480 | 0.413-0.553 |  |  |
| real | early3 | 3 AIS gap | 52 | 433 | 0.509 | 0.426-0.594 |  |  |
| real | early3 | 4 Off-lane | 52 | 433 | 0.545 | 0.459-0.633 |  |  |
| real | early3 | 5 Isolation Forest | 52 | 433 | 0.588 | 0.500-0.672 |  |  |
| placebo30 | main | 1 Speed drop | 53 | 486 | 0.505 | 0.417-0.592 | 0.9148 |  |
| placebo30 | main | 2 Loitering | 53 | 486 | 0.442 | 0.388-0.501 | 0.0369 |  |
| placebo30 | main | 3 AIS gap | 53 | 486 | 0.520 | 0.463-0.580 | 0.5416 |  |
| placebo30 | main | 4 Off-lane | 53 | 486 | 0.495 | 0.412-0.581 | 0.9113 |  |
| placebo30 | main | 5 Isolation Forest | 53 | 486 | 0.484 | 0.391-0.576 | 0.7111 |  |
