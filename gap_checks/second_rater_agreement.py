"""Agreement of the human second rater with the first rater and with the model rater.

Planned in FOLLOWUP_PLAN_DRAFT.md section 3, written before any answer was returned.
Descriptive, not a test.

usage: python3 gap_checks/second_rater_agreement.py <second_rater_answers.csv>
       (from the repository root; the CSV is the file downloaded from
       review_page/second_rater.html)
writes data/second_rater_review.csv (the answers as returned) and
       results/agreement/second_rater_agreement.csv

Cohen's kappa is reported for yes against not-yes (the decision that sets a match) and for
the three answers, for each pair of raters on the same 100 cases. The model-rater kappa on
all 410 cases (0.69) is the comparison the paper already reports.
"""
import sys

import numpy as np
import pandas as pd

IDS = ["incident_id", "mmsi"]


def kappa(a, b):
    cats = sorted(set(a) | set(b))
    ix = {k: i for i, k in enumerate(cats)}
    t = np.zeros((len(cats), len(cats)))
    for x, y in zip(a, b):
        t[ix[x], ix[y]] += 1
    n = t.sum()
    po = np.trace(t) / n
    pe = (t.sum(0) * t.sum(1)).sum() / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def boot_ci(a, b, n=2000, seed=20261115):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a), np.asarray(b)
    ks = [kappa(a[i], b[i]) for i in (rng.integers(0, len(a), len(a)) for _ in range(n))]
    return np.nanpercentile(ks, [2.5, 97.5])


h = pd.read_csv(sys.argv[1], dtype={"mmsi": str})
h["decision"] = h.decision.fillna("").str.strip().str.lower()
missing = (~h.decision.isin(["yes", "no", "unsure"])).sum()
if missing:
    sys.exit(f"{missing} of {len(h)} cases have no answer; ask the rater to finish first")
h.to_csv("data/second_rater_review.csv", index=False)

s = pd.read_csv("stage_a/second_rater_sample.csv", dtype={"mmsi": str})
j = pd.read_csv("data/janice_review.csv", dtype={"mmsi": str})[IDS + ["decision"]]
c = pd.read_csv("data/claude_review.csv", dtype={"mmsi": str})[IDS + ["decision"]]
m = (s.merge(h[IDS + ["decision"]].rename(columns={"decision": "human2"}), on=IDS, validate="1:1")
      .merge(j.rename(columns={"decision": "rater1"}), on=IDS, validate="1:1")
      .merge(c.rename(columns={"decision": "model"}), on=IDS, validate="1:1"))
assert len(m) == len(s) == 100, len(m)

rows = []
for x, y in [("human2", "rater1"), ("human2", "model"), ("rater1", "model")]:
    for scale in ("yes vs not-yes", "three answers"):
        a, b = m[x], m[y]
        if scale == "yes vs not-yes":
            a, b = a.eq("yes").map({True: "yes", False: "not"}), b.eq("yes").map({True: "yes", False: "not"})
        lo, hi = boot_ci(a, b)
        rows.append((x, y, scale, len(m), (a == b).mean(), kappa(a, b), lo, hi))
out = pd.DataFrame(rows, columns=["rater_a", "rater_b", "scale", "n", "raw_agreement", "kappa",
                                  "kappa_lo95", "kappa_hi95"])
out.to_csv("results/agreement/second_rater_agreement.csv", index=False)
print(out.round(3).to_string(index=False))
print("\nhuman2 x rater1 (counts):")
print(pd.crosstab(m.human2, m.rater1))
both = m.rater1.eq("yes") & m.model.eq("yes")
print(f"\nof {both.sum()} sampled cases both earlier raters said yes, the second human said yes to "
      f"{(both & m.human2.eq('yes')).sum()}")
