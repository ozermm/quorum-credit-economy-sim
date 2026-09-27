"""Figures for the Quorum design paper. Reads ../results, writes ../figures."""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e3e3e3",
    "grid.linewidth": 0.6,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})
INK = "#1f2a36"
C = {"Baseline": "#0e5f6b", "No escalation": "#b4532a", "Low responsiveness": "#6a4c93", "Slow growth": "#7a7a7a",
     "Small community": "#2e7d32", "Small community, no escalation": "#8e1b1b"}

series = json.loads((RES / "series.json").read_text())
waits = json.loads((RES / "waits.json").read_text())
days = np.arange(len(series["Baseline"]["members"]))
months = days / 30.44


def band(ax, name, key, label, color, ls="-"):
    m = np.array(series[name][key])
    lo = np.array(series[name + "__p10"][key])
    hi = np.array(series[name + "__p90"][key])
    ax.plot(months, m, color=color, lw=1.6, ls=ls, label=label)
    ax.fill_between(months, lo, hi, color=color, alpha=0.15, lw=0)


# Figure 1: submission lifecycle -------------------------------------------------
fig, ax = plt.subplots(figsize=(6.8, 3.3))
ax.set_axis_off()
ax.set_xlim(0, 11.2)
ax.set_ylim(0, 4.6)
W, H = 1.8, 1.05


def box(x, y, text, w=W, h=H, face="#e3f1f2"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=face, ec=INK, lw=0.8))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.8, color=INK)


def arrow(p1, p2, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=9, lw=0.9, color=INK, connectionstyle=f"arc3,rad={rad}"))


def label(x, y, text, ha="center"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=7, color="#333", bbox=dict(fc="white", ec="none", pad=0.6))


top = 2.95
box(0.1, top, "Submission\n(1 credit or\ngenesis invitation)")
box(2.5, top, "Finding\nreviewers")
box(4.9, top, "Under review\n(3 double-blind\nreports)")
box(7.3, top, "Automatic\ndecision\n(published rules)")
box(9.75, 3.75, "Accepted and\npublished", w=1.35, h=0.75)
box(9.75, 2.2, "Rejected", w=1.35, h=0.75)
box(7.3, 0.55, "Revision by\nthe authors")
box(2.5, 0.55, "Day 7: wider match\nand open call\nDay 30: refunded\nwithdrawal", face="#fbf0d9")

arrow((1.9, top + H / 2), (2.5, top + H / 2))
arrow((4.3, top + H / 2), (4.9, top + H / 2))
label(4.6, top + H / 2 + 0.28, "panel full")
arrow((6.7, top + H / 2), (7.3, top + H / 2))
arrow((9.1, top + 0.8), (9.75, 4.1))
label(9.42, 4.3, "accept")
arrow((9.1, top + 0.25), (9.75, 2.6))
label(9.42, 2.45, "reject")
arrow((8.2, top), (8.2, 0.55 + H))
label(8.2, 2.25, "minor or major")
arrow((7.3, 1.1), (5.8, top), rad=-0.2)
label(6.25, 1.55, "next round,\nsame panel")
arrow((3.2, top), (3.2, 0.55 + H))
arrow((3.8, 0.55 + H), (3.8, top))
label(5.6, 0.18, "A reviewer earns 1 credit for the first report on each paper; re-reviews earn reputation only.")
fig.savefig(FIG / "fig1_lifecycle.png")
plt.close(fig)

# Figure 2: baseline growth ------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 3.2))
band(ax, "Baseline", "members", "Members", "#7a7a7a", "--")
band(ax, "Baseline", "submitted", "Papers submitted", "#0e5f6b")
band(ax, "Baseline", "published", "Papers published", "#b4532a")
ax.axvline(60 / 30.44, color="#999", lw=0.8, ls=":")
ax.text(60 / 30.44 + 0.3, ax.get_ylim()[1] * 0.42, "end of the\ngenesis window", fontsize=7.5, color="#666")
ax.set_xlabel("Months since launch")
ax.set_ylabel("Cumulative count")
ax.legend(frameon=False, loc="upper left")
fig.savefig(FIG / "fig2_baseline_growth.png")
plt.close(fig)

# Figure 3: small community, with and without escalation ------------------------
fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.9))
for name, ls in (("Small community", "-"), ("Small community, no escalation", "--")):
    label = "With day-7 escalation" if "no" not in name else "Without escalation"
    band(axes[0], name, "published", label, C[name], ls)
    band(axes[1], name, "seeking", label, C[name], ls)
axes[0].set_title("Papers published (cumulative)", fontsize=9.5)
axes[1].set_title("Papers waiting for reviewers", fontsize=9.5)
for a in axes:
    a.set_xlabel("Months since launch")
axes[0].legend(frameon=False, loc="upper left", fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "fig3_small_community.png")
plt.close(fig)

# Figure 4: time to a full panel ------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 3.1))
order = ["Baseline", "No escalation", "Low responsiveness", "Slow growth", "Small community", "Small community, no escalation"]
styles = ["-", "--", "-.", ":", "-", "--"]
for name, ls in zip(order, styles):
    w = np.sort(np.array(waits[name]))
    if len(w) == 0:
        continue
    y = np.arange(1, len(w) + 1) / len(w)
    lw = 2.2 if name.startswith("Small") else 1.4
    ax.step(w, y, where="post", ls=ls, lw=lw, color=C.get(name, INK), label=name)
ax.axvline(7, color="#999", lw=0.8, ls=":")
ax.text(7.4, 0.06, "day 7", fontsize=7.5, color="#666")
ax.set_xlim(0, 60)
ax.set_ylim(0, 1.01)
ax.set_xlabel("Days from submission to a full review panel (first round; papers never paneled count as not reached)")
ax.set_ylabel("Share of papers")
ax.legend(frameon=False, fontsize=7.5, loc="lower right")
fig.savefig(FIG / "fig4_time_to_panel.png")
plt.close(fig)

# Figure 5: credits in circulation ----------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 3.0))
for name, ls in (("Baseline", "-"), ("Slow growth", ":"), ("Small community", "--")):
    per = np.array(series[name]["credits_held"]) / np.maximum(1, np.array(series[name]["members"]))
    ax.plot(months, per, ls=ls, lw=1.6, color=C[name], label=name)
ax.set_xlabel("Months since launch")
ax.set_ylabel("Unspent credits per member")
ax.legend(frameon=False, loc="upper left")
fig.savefig(FIG / "fig5_credits.png")
plt.close(fig)
print("figures written to", FIG)
