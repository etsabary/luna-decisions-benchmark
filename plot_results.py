#!/usr/bin/env python3
"""Regenerate publication figures from the public aggregate summary."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "figures"
S = json.loads((ROOT / "analysis/summary.json").read_text())
OUT.mkdir(exist_ok=True)
COLORS = {"jev": "#176b87", "luna": "#b64829", "unanswered": "#aeb7c0"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "none", "svg.hashsalt": "luna-jev-benchmark-20261010",
                     "savefig.facecolor": "white"})

def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", metadata={"Date": None})
    fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 3.8))
for y, model in enumerate(["luna", "jev"]):
    m = S["primary"][model]
    left = 0
    for key, color, label in [("correct", COLORS[model], "correct"), ("wrong_valid", "#eadbd4", "wrong"), ("unanswered", COLORS["unanswered"], "unanswered")]:
        n = m[key]
        ax.barh(y, n, left=left, color=color, height=.48)
        if n > 40:
            ax.text(left + n / 2, y, f"{n} {label}", ha="center", va="center", color="white" if key == "correct" else "#26313b")
        left += n
ax.annotate("17 unanswered", (991.5, 0), (785, -.65), arrowprops={"arrowstyle": "-", "color": "#65717c"}, fontsize=10)
ax.set_yticks([0, 1], ["Luna Decisions\n2026-10-06 snapshot", "Jev\nSept. 22 provider mix"])
ax.set_xlim(0, 1000); ax.set_ylim(-.95, 1.65)
ax.set_xlabel("Questions out of the exact same 1,000")
ax.set_title("Matched benchmark: 61.2% Luna vs 81.7% Jev", loc="left", fontweight="bold", pad=18)
fig.text(.02, -.035, "17 Luna questions refused on all five HTTP attempts each. Refusals remain in the denominator.", fontsize=10, color="#52606b")
save(fig, "overall_results")

families = sorted(S["by_family"], key=lambda f: (f["luna"]["accuracy_attempted"], f["family"]))
fig, ax = plt.subplots(figsize=(11, 11))
y = np.arange(len(families))
for offset, model, label in [(-.16, "jev", "Jev (historical provider mix)"), (.16, "luna", "Luna Decisions (2026-10-06)")]:
    ax.barh(y + offset, [100 * f[model]["accuracy_attempted"] for f in families], height=.29, color=COLORS[model], label=label)
ax.set_yticks(y, [f["family"] + f"  (n={f['luna']['attempted']})" for f in families], fontsize=10)
ax.set_xlim(0, 105); ax.set_xticks([0, 20, 40, 60, 80, 100]); ax.set_xlabel("Correct / all attempted questions (%)")
ax.xaxis.grid(True, alpha=.15); ax.set_axisbelow(True)
ax.legend(loc="lower right", frameon=False, fontsize=9)
ax.set_title("Strengths and weaknesses across 25 families", loc="left", fontweight="bold", pad=18)
fig.text(.02, -.018, "32–52 questions per family; includes related robustness variants. Small groups are descriptive, not rankings of general capability.", fontsize=9, color="#52606b")
save(fig, "family_comparison")

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for model, label in [("jev", "Jev"), ("luna", "Luna Decisions")]:
    curve = S["confidence"][model]
    axes[0].plot([100 * p["coverage_attempted"] for p in curve], [100 * p["accuracy"] for p in curve], "o-", color=COLORS[model], label=label)
    c = next(p for p in curve if p["threshold"] == .8)
    axes[0].annotate(f"confidence ≥ .8\n{c['retained']}/1,000 retained", (100*c["coverage_attempted"], 100*c["accuracy"]), (100*c["coverage_attempted"]+3, 100*c["accuracy"]-12), fontsize=9, color=COLORS[model], arrowprops={"arrowstyle": "-", "color": COLORS[model]})
    bins = S["probability_quality_paired_valid"][model]["calibration_bins"]
    axes[1].plot([b["mean_selected_probability"] for b in bins], [b["accuracy"] for b in bins], "o-", color=COLORS[model], label=label)
axes[0].set(xlim=(0, 103), ylim=(55, 102), xlabel="Coverage of all 1,000 questions (%)", ylabel="Accuracy on retained decisions (%)", title="Confidence filtering")
axes[0].legend(frameon=False)
axes[1].plot([0,1], [0,1], "--", color="#8b9299", linewidth=1)
axes[1].set(xlim=(0,1), ylim=(0,1.03), xlabel="Mean probability of selected option", ylabel="Observed accuracy", title="Option probability calibration (983 paired)")
for ax in axes: ax.grid(alpha=.15)
fig.suptitle("Useful confidence signals, with a coverage tradeoff", fontweight="bold", y=1.03)
fig.tight_layout()
fig.text(.02, -.04, "Reported confidence and option probability are separate API fields. Threshold results are exploratory on this same sample.", fontsize=9, color="#52606b")
save(fig, "confidence_and_calibration")
print("Wrote three SVG/PNG figure pairs from analysis/summary.json")
