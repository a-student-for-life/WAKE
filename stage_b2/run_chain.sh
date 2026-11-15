#!/bin/bash
# waits for the IncidentNews noon rebuild, then runs the NTSB-time windows and prior24 windows
cd /home/claude/wake
while pgrep -f "incidentnews_time.py windows" >/dev/null; do sleep 30; done
echo "== ntsb windows $(date -u)"; python3 -I gap_checks/ntsb_time.py windows --max-minutes 120
echo "== prior24 real $(date -u)"; python3 -I stage_b2/windows_prior24.py real --max-minutes 400
echo "== prior24 placebo $(date -u)"; python3 -I stage_b2/windows_prior24.py placebo30 placebo60 --max-minutes 400
echo "== chain done $(date -u)"
