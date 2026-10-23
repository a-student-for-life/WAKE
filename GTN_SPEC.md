# GeoTrackNet runs (ANALYSIS_PLAN_ADDENDUM_1.md)

Every scheduled session follows this file and `ANALYSIS_PLAN_ADDENDUM_1.md`. Code is in
`gtn/` (see `gtn/PATCHES.md`). Stage B files are never changed.

## One session at a time

1. After cloning, check `RUNNING.md`. If it exists and its time is less than 4 hours ago,
   stop at once and change nothing.
2. Otherwise write `RUNNING.md` with the current UTC time, commit ("Session lock") and push.
   If the push is rejected, pull and go back to step 1.
3. Delete `RUNNING.md` in the session's final commit.

## Ground rules

- Commit as `Janice Miranda <38janice10b@gmail.com>`, with no `Co-Authored-By` or other
  attribution lines; never add collaborators. `git pull --rebase origin main` before every push.
- Work for about 2 h 50 min at most, then stop at a clean commit with a row added to
  `PROGRESS.md` (date, phase, what was done with counts from files, measured pace, hours left).
- Raw AIS goes in `data/raw/` (git-ignored). Keep every committed file under 50 MB.
- Before committing a model, run `python3 gtn/prune_ckpt.py <region>` (keeps the latest
  checkpoint only). Commit models only when a region is DONE and at the end of a session.
- Save usage while waiting: start long jobs in the background
  (`setsid nohup ... > log 2>&1 &`) and check them with `sleep 540; tail -3 log`, not more often.
- Never look at, print or summarise GeoTrackNet scores of incident vessels against controls
  before phase 4. Phases 1-3 build inputs only.
- Never change the addendum, the plan, `DEVIATIONS.md`, Stage B files, or the M4 sets.

## Model rule (Janice's request, 23 Oct 2026)

Phases 0-3 run on Sonnet. Code in `gtn/` is changed only by an Opus session: a Sonnet
session that hits an error it cannot solve without changing code writes the error in its
`PROGRESS.md` row, sets this scheduled task's model to `claude-opus-5-5`
(update_trigger, trigger `trig_01DfQ7iyHFSrQhVEGoNVnd2R`), and fires it once. An Opus session
that fixes such an error sets the model back to `claude-sonnet-5-5` before it ends, unless
the next phase is phase 4. When phase 3 is complete, a Sonnet session sets the model to
`claude-opus-5-5` and fires once for phase 4.

## Phase 0: environment (every session)

`bash gtn/setup_env.sh` (about 5 minutes), then work in the repo with
`--gdir /tmp/gtn/GeoTrackNet --py /tmp/gtn/env/bin/python`.

## Phase 1: training (regions R01-R16 in order)

For the first region without `data/gtn/models/<region>/DONE.json`:

    /tmp/gtn/env/bin/python gtn/unpack.py <region> /tmp/gtn/sets/<region>
    python3 gtn/train_region.py <region> --gdir /tmp/gtn/GeoTrackNet --py /tmp/gtn/env/bin/python \
        --sets /tmp/gtn/sets --max-minutes <minutes left in the session>

It resumes from the committed checkpoint and writes `curve.csv` and, when the stop rule is
met, `DONE.json`. On DONE: prune, commit the region's model directory, continue with the next
region in the same session if more than 40 minutes remain. A region whose training fails
twice is recorded in `data/gtn/failed.json` with the error and skipped (addendum).

## Phase 2: scoring inputs

Starts when phase 1 is complete (every region has DONE.json or is in failed.json).

    python3 -I gtn/score_prep.py --gpy /tmp/gtn/env/bin/python --gdir /tmp/gtn/GeoTrackNet --max-minutes <left>

Resumable (`data/gtn/score_state.json`); commit `data/gtn/score/` and the state after each
run. Phase 2 is complete when every event-scenario of `gtn/score_prep.py`'s job list is done.

## Phase 3: scoring

For each region without `data/gtn/scores/<region>.csv`:

    /tmp/gtn/env/bin/python gtn/unpack.py <region> /tmp/gtn/sets/<region>
    python3 gtn/score_region.py <region> --gdir /tmp/gtn/GeoTrackNet --py /tmp/gtn/env/bin/python --sets /tmp/gtn/sets

Commit each CSV. Do not open or summarise the CSVs.

## Phase 4: analysis (Opus only)

Write `gtn/analyse_gtn.py` implementing the addendum's "Tests and reading rules" with the
functions of `stage_b/analyse.py` (`set_arrays`, `auc_test`, `members_for` logic): detector
`d7_gtn` from `data/gtn/scores/*.csv` (window main/early3/w6, scenario real/placebo30/
placebo60) joined to the M4 sets on (event_id, scenario, mmsi); main test, reading rule,
same-subset comparison with detectors 1-5 and paired bootstrap differences, flag rates
(`gtn_flag`, conditional logit), early3 and w6, placebo dates; counts of sets used and
dropped at each step. Write `results/gtn/results.md` and tables in `results/gtn/tables/`,
no interpretation beyond the reading rules. Then: `PROGRESS.md` row "GeoTrackNet complete.
Results in results/gtn/results.md.", disable this scheduled task (update_trigger enabled
false), and send Janice a short push notification without results.

## Back-to-back

If this session held the lock, did work, pushed successfully, and the study is not complete
and not waiting for the OSF link, its very last action is fire_trigger on
`trig_01DfQ7iyHFSrQhVEGoNVnd2R` (once). The 4-hourly schedule is only a fallback.
