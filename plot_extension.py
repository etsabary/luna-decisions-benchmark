#!/usr/bin/env python3
"""Render the frozen two-model baseline with explicit denominators and dates."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = Path(__file__).resolve().parent / "extension_136"
s = json.loads((OUT / "summary.json").read_text())
families = s["by_family"]
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "svg.fonttype":"none", "svg.hashsalt":"jev-reference-1136"})
fig = plt.figure(figsize=(12, 16), facecolor="#f7f9fc")
gs = fig.add_gridspec(2, 1, height_ratios=[4.3,1.4], left=.35, right=.94, top=.88, bottom=.20, hspace=.15)
ax = fig.add_subplot(gs[0])
models = ["jev", "luna"]
values = np.array([[100*f[m]["accuracy_attempted"] for m in models] for f in families])
image = ax.imshow(values, vmin=0, vmax=100, cmap="YlGnBu", aspect="auto")
ax.set_xticks(range(2),["Jev 1.13", "GPT-6 Luna Decisions"],fontweight="bold",fontsize=12)
ax.xaxis.tick_top()
ax.tick_params(axis="both",length=0,pad=10)
ax.set_yticks(range(len(families)),[f["family"] for f in families],fontsize=10)
for i,f in enumerate(families):
    for j,m in enumerate(models):
        r=f[m]
        ax.text(j,i,f"{r['correct']}/{r['attempted']}  ·  {100*r['accuracy_attempted']:.0f}%",
            ha="center",va="center",color="white" if values[i,j]>=62 else "#14283f",fontsize=10,fontweight="bold")
ax.set_xticks(np.arange(-.5,2,1),minor=True)
ax.set_yticks(np.arange(-.5,len(families),1),minor=True)
ax.grid(which="minor",color="white",linewidth=2)
ax.tick_params(which="minor",length=0)
for spine in ax.spines.values():spine.set_visible(False)
bx=fig.add_subplot(gs[1])
labels=["Every option rotation correct", "Both changed-evidence answers correct", "Supplied-candidate checks correct"]
counts={m:[s["diagnostics"][m]["rotation"]["all_five_correct"],s["diagnostics"][m]["contrast"]["both_correct"],s["diagnostics"][m]["candidate_checks"]["checks_correct"]] for m in models}
denoms=[25,25,80]
for offset,m,color in [(-.19,"jev","#087f8c"),(.19,"luna","#7353ba")]:
    v=[100*n/d for n,d in zip(counts[m],denoms)]
    bars=bx.barh(np.arange(3)+offset,v,height=.34,color=color,label="Jev 1.13" if m=="jev" else "Luna Decisions")
    for bar,n,d in zip(bars,counts[m],denoms):
        bx.text(bar.get_width()+1,bar.get_y()+bar.get_height()/2,f"{n}/{d}",va="center",fontsize=10)
bx.set_yticks(range(3),labels,fontsize=10)
bx.invert_yaxis();bx.set_xlim(0,108)
bx.set_xlabel("Correct / all planned cases (%)")
bx.set_xticks([0,25,50,75,100]);bx.grid(axis="x",alpha=.2);bx.set_axisbelow(True)
bx.spines[["top","right","left"]].set_visible(False)
bx.legend(loc="upper center",bbox_to_anchor=(.5,-.25),ncol=2,frameon=False)
fig.text(.06,.965,"Where the two decision models succeed and fail",fontsize=20,fontweight="bold",color="#12263a")
fig.text(.06,.938,"1,136 exact text questions · 25 reasoning families · existing deterministic answer key",fontsize=12,color="#415569")
fig.text(.06,.912,"Jev 1.13: 22 Sep + 14 Oct 2026   |   Luna Decisions: 10 + 14 Oct 2026",fontsize=11,color="#415569")
fig.text(.06,.065,"Snapshots: Jev 1.13.0 / OpenRouter 1.13-20260917 (256 historical alias-only records);\nLuna Decisions 20261006. New Jev calls explicitly requested 1.13. No Jev 1.14 data.\nRefusals remain in denominators. Matched variants are dependent; family totals mix task roles.\nSource: extension_136/summary.json. Key validation is computational, not an independent language audit.",fontsize=9,color="#415569",linespacing=1.6)
for suffix in ["png","svg"]:
    target=OUT/f"abilities_baseline.{suffix}"
    options={"metadata":{"Date":None}} if suffix=="svg" else {}
    fig.savefig(target,dpi=180,facecolor=fig.get_facecolor(),**options)
    if suffix=="svg":
        target.write_text("\n".join(line.rstrip() for line in target.read_text().splitlines())+"\n")
print("Rendered abilities_baseline.png and .svg")
