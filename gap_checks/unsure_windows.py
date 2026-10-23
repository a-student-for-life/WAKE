"""Gap check 1: window files for the unsure-match events, real date only.

usage: python3 -I gap_checks/unsure_windows.py
Runs stage_b/windows.py unchanged, pointed at data/gap_checks/unsure_events.csv, writing
data/gap_checks/windows/<event_id>_real.csv.gz and data/gap_checks/state.json.
The placebo scenarios are not needed for this robustness check (plan section 8 asks
for the main test with the unsure cases added back).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stage_b"))
import windows  # noqa: E402

windows.EVENTS = "data/gap_checks/unsure_events.csv"
windows.OUTDIR = "data/gap_checks/windows"
windows.STATE = "data/gap_checks/state.json"
windows.SCEN = ["real"]
sys.argv = [sys.argv[0], "--no-git", "--max-minutes", "120"]
windows.main()
