"""Figures for the WAKE manuscript, drawn only from files in the WAKE repository.

usage: python3 paper/make_figures.py <path to WAKE repo> <output folder>

The map needs Natural Earth 1:50m land polygons (public domain), which are not committed:
download ne_50m_land.geojson from https://github.com/nvkelso/natural-earth-vector
(geojson/ne_50m_land.geojson) to data/raw/ne/ne_50m_land.geojson.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

REPO, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.linewidth": 0.6,
                     "pdf.fonttype": 42})

NAMES = {"d1_speed_drop": "1 Speed drop", "d2_loiter_h": "2 Loitering", "d3_gap_ratio": "3 AIS gap",
         "d4_off_lane": "4 Off-lane", "d5_iforest": "5 Isolation Forest", "gtn": "GeoTrackNet"}
GREY, BLUE, LIGHT = "#555555", "#1f5fa8", "#b5b5b5"


def r(path):
    return pd.read_csv(os.path.join(REPO, path))


# ------------------------------------------------------------------ Figure 1: map
def land_polys():
    gj = json.load(open(os.path.join(REPO, "data/raw/ne/ne_50m_land.geojson")))
    for f in gj["features"]:
        g = f["geometry"]
        rings = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in rings:
            yield poly[0]


def draw_land(ax):
    for ring in land_polys():
        xs, ys = zip(*ring)
        ax.fill(xs, ys, color="#e6e6e6", lw=0.3, ec="#9a9a9a", zorder=0)


ev = r("data/stage_b/events.csv")
sets = r("data/stage_b/matched/sets.csv")
excl = ev.main_exclude.astype(str).str.lower() == "true"
ok = set(sets[(sets.definition == "M4") & (sets.scenario == "real") & (sets.status == "matched")].event_id)
E = ev[ev.event_id.isin(ok) & ~excl].copy()
reg = r("data/gtn/regions.csv")
gtn_ids = {int(x) for v in reg.event_ids for x in v.split(";")}
E["gtn"] = E.event_id.isin(gtn_ids)
assert len(E) == 197 and E.gtn.sum() == 122


def plot_events(ax, s=9):
    for src, m in [("NRC", "o"), ("IncidentNews", "^")]:
        for g, c in [(False, GREY), (True, BLUE)]:
            d = E[(E.source == src) & (E.gtn == g)]
            ax.scatter(d.ref_lon, d.ref_lat, s=s, marker=m, c=c, lw=0, alpha=0.85, zorder=3)
    for row in reg.itertuples():
        ax.add_patch(Rectangle((row.lon_min, row.lat_min), row.lon_max - row.lon_min,
                               row.lat_max - row.lat_min, fill=False, lw=0.7, ec=BLUE, ls="--", zorder=2))


fig = plt.figure(figsize=(7.2, 4.2))
ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
draw_land(ax); plot_events(ax)
ax.set_xlim(-127, -64); ax.set_ylim(16.5, 50); ax.set_aspect(1.25); ax.axis("off")
ins = fig.add_axes([0.01, 0.02, 0.30, 0.30])
draw_land(ins); plot_events(ins, 14)
ins.set_xlim(-170, -130); ins.set_ylim(52, 63); ins.set_aspect(2.0)
ins.set_xticks([]); ins.set_yticks([]); ins.set_title("Alaska", fontsize=7, pad=2)
ins2 = fig.add_axes([0.32, 0.02, 0.13, 0.17])
draw_land(ins2); plot_events(ins2, 22)
ins2.set_xlim(-161, -154); ins2.set_ylim(18.5, 22.5); ins2.set_aspect(1.1)
ins2.set_xticks([]); ins2.set_yticks([]); ins2.set_title("Hawaii", fontsize=7, pad=2)
h = [plt.Line2D([], [], ls="", marker="o", color=GREY, ms=4, label="NRC event"),
     plt.Line2D([], [], ls="", marker="^", color=GREY, ms=4, label="IncidentNews event"),
     plt.Line2D([], [], ls="", marker="o", color=BLUE, ms=4, label="Event in a GeoTrackNet region"),
     Rectangle((0, 0), 1, 1, fill=False, ec=BLUE, ls="--", label="GeoTrackNet region (2° × 3° cell)")]
fig.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=4, fontsize=7, frameon=False)
fig.savefig(os.path.join(OUT, "fig_map.pdf"), bbox_inches="tight"); plt.close(fig)

# ------------------------------------------------------------------ Figure 2: forest plot
mt = r("results/stageB/tables/main_test.csv")
mt = mt[mt.detector != "d6_tars"]
rob = r("results/stageB/tables/robustness.csv")
pl = r("results/stageB/tables/placebo.csv")
g_main = r("results/gtn/tables/main_test.csv")
g_win = r("results/gtn/tables/windows.csv")
g_pl = r("results/gtn/tables/placebo.csv")


def first(df, **kw):
    for k, v in kw.items():
        df = df[df[k] == v]
    assert len(df) == 1, (kw, len(df))
    return df.iloc[0]


rows = []
for d in ["d1_speed_drop", "d2_loiter_h", "d3_gap_ratio", "d4_off_lane", "d5_iforest"]:
    m = first(mt, detector=d)
    e3 = first(rob[rob.label.str.contains("early3", regex=False)], detector=d)
    p30 = first(pl[pl.label == "placebo30"], detector=d)
    rows += [(d, "true", m.auc, m.lo, m.hi, int(m.n_sets)), (d, "early3", e3.auc, e3.lo, e3.hi, int(e3.n_sets)),
             (d, "placebo30", p30.auc, p30.lo, p30.hi, int(p30.n_sets))]
gm = g_main.iloc[0]
ge = first(g_win, label="early3")
gp = first(g_pl, label="placebo30")
rows += [("gtn", "true", gm.auc, gm.lo, gm.hi, int(gm.n_sets)), ("gtn", "early3", ge.auc, ge.lo, ge.hi, int(ge.n_sets)),
         ("gtn", "placebo30", gp.auc, gp.lo, gp.hi, int(gp.n_sets))]
F = pd.DataFrame(rows, columns=["det", "cond", "auc", "lo", "hi", "n"])
F.to_csv(os.path.join(OUT, "fig_forest_data.csv"), index=False)
order = (F[F.cond == "true"].sort_values("auc", ascending=False).det.tolist())
style = {"true": (GREY, 1.0, -0.22, "True date, T − 24 h to T"),
         "early3": (BLUE, 1.0, 0.0, "Window ending 3 h before T (early3)"),
         "placebo30": (LIGHT, 1.0, 0.22, "Placebo date, T − 30 days")}
fig, ax = plt.subplots(figsize=(6.6, 3.9))
for i, d in enumerate(order):
    for c, (col, a, off, lab) in style.items():
        q = F[(F.det == d) & (F.cond == c)].iloc[0]
        y = i + off
        ax.plot([q.lo, q.hi], [y, y], color=col, lw=1.4, alpha=a)
        ax.plot(q.auc, y, "o", color=col, ms=4.5, label=lab if i == 0 else None)
ax.axvline(0.5, color="#888", lw=0.7, ls="--"); ax.axvline(0.6, color="#888", lw=0.7, ls=":")
ax.text(0.5, -0.75, "chance", ha="center", fontsize=7, color="#555")
ax.text(0.6, -0.75, "plan threshold", ha="center", fontsize=7, color="#555")
lab = []
for d in order:
    n = F[F.det == d].set_index("cond").n
    lab.append(f"{NAMES[d]}\n({n['true']} / {n['early3']} / {n['placebo30']} sets)")
ax.set_yticks(range(len(order))); ax.set_yticklabels(lab, fontsize=7.5)
ax.set_ylim(len(order) - 0.5, -0.95); ax.set_xlim(0.40, 0.72)
ax.set_xlabel("Pooled AUC with 95% bootstrap interval")
ax.legend(loc="upper center", bbox_to_anchor=(0.45, 1.13), ncol=3, fontsize=7, frameon=False)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_forest.pdf")); plt.close(fig)

# ------------------------------------------------------------------ Figure 3: identical vessels
S = r("results/gap_checks/gtn_early3_same_vessels.csv")
fig, ax = plt.subplots(figsize=(6.0, 3.0))
items = [("gtn", S.auc_gtn_main.iloc[0], S.auc_gtn_early3.iloc[0])] + \
    [(x.detector, x.auc_det_main, x.auc_det_early3) for x in S.itertuples()]
for i, (d, a, b) in enumerate(items):
    col = BLUE if d == "gtn" else GREY
    ax.annotate("", xy=(i, b), xytext=(i, a), arrowprops=dict(arrowstyle="->", color=col, lw=1.3))
    ax.plot(i, a, "o", mfc="white", mec=col, ms=5); ax.plot(i, b, "o", color=col, ms=5)
ax.axhline(0.5, color="#888", lw=0.7, ls="--")
ax.set_xticks(range(len(items))); ax.set_xticklabels([NAMES[d] for d, _, _ in items], fontsize=7.5, rotation=15)
ax.set_ylabel("Pooled AUC"); ax.set_ylim(0.44, 0.67)
ax.plot([], [], "o", mfc="white", mec=GREY, ls="", label="Main window (T − 24 h to T)")
ax.plot([], [], "o", color=GREY, ls="", label="early3 (T − 27 h to T − 3 h)")
ax.legend(fontsize=7, frameon=False, loc="upper right")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_early3.pdf")); plt.close(fig)
print("figures written; sets", int(S.n_sets.iloc[0]), "pairs", int(S.n_pairs.iloc[0]))
