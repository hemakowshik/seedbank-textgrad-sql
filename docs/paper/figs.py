"""Figures for the paper. Fig. 3 uses germ.json (exported from data/seedbank.db: store, years since regeneration, rate)."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams.update({"font.family": "Carlito", "font.size": 8})
INK, MUTED, EDGE = "#1F1E1D", "#6B6B6B", "#B9B5AA"

# ---------------------------------------------------------------- Fig. 1 architecture
fig, ax = plt.subplots(figsize=(6.8, 3.1), dpi=300)
ax.set_xlim(0, 140); ax.set_ylim(0, 62); ax.axis("off")
ax.text(0.5, 60, "Failed checks rewrite the prompt; queries that pass go to the user", fontsize=10, weight="bold", color=INK, va="top")
ax.text(0.5, 55.3, "Green steps are plain code and never see the gold answer. Blue steps are LLM calls.", fontsize=7.5, color=MUTED, va="top")
GREEN, BLUE, WHITE = "#EEF4EC", "#E9F0F8", "#FFFFFF"

def box(x, y, w, h, title, sub, fc, ec=EDGE, lw=0.8):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h * 0.70, title, ha="center", va="center", fontsize=7.4, weight="bold", color=INK)
    ax.text(x + w / 2, y + h * 0.31, sub, ha="center", va="center", fontsize=5.9, color=MUTED, linespacing=1.15)

def arr(x1, y1, x2, y2, label=None, lx=None, ly=None, ha="center", ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#8A877F", mutation_scale=7, linestyle=ls))
    if label:
        ax.text(lx, ly, label, fontsize=6.0, color=MUTED, ha=ha, va="center")

W, H, Y, G = 17.4, 12, 30, 2.7
xs = [0.6 + i * (W + G) for i in range(7)]
box(xs[0], Y, W, H, "Question", "plain language", WHITE)
box(xs[1], Y, W, H, "Intent", "latest? threshold?\nstock? years?", GREEN)
box(xs[2], Y, W, H, "Generator", "writes SQL from\nprompt p + schema", BLUE)
box(xs[3], Y, W, H, "Executor", "read-only SQLite,\nrows or error", GREEN)
box(xs[4], Y, W, H, "Validator", "13 domain rules +\nmetamorphic tests", GREEN)
box(xs[5], Y, W, H, "Evaluator", "textual loss from\nvalidator evidence", BLUE)
box(xs[6], Y, W, H, "Answer", "rows to the user", WHITE)
for i in range(6):
    arr(xs[i] + W + 0.35, Y + H / 2, xs[i + 1] - 0.35, Y + H / 2)
ax.text(xs[6] + W / 2, Y + H + 2.4, "PASS and no findings", fontsize=6.0, color=MUTED, ha="center")
d = (0, (2, 1.5))
ax.plot([xs[1] + W / 2] * 2, [Y + H + 0.4, Y + H + 4], color="#8A877F", lw=0.7, ls=d)
ax.plot([xs[1] + W / 2, xs[4] + W / 2], [Y + H + 4] * 2, color="#8A877F", lw=0.7, ls=d)
arr(xs[4] + W / 2, Y + H + 4, xs[4] + W / 2, Y + H + 0.5, ls=d)
ax.text((xs[2] + xs[4] + W) / 2, Y + H + 5.6, "the intent decides which rules and tests run", fontsize=6.0, color=MUTED, ha="center")

Y2 = 7
box(xs[2], Y2, W, H, "Prompt p", "the trainable\nvariable", WHITE, ec="#2C5D8F", lw=1.2)
box(xs[3], Y2, W, H, "Rule memory", "lessons by rule ID\n(prompt-level mode)", GREEN)
box(xs[4], Y2, W, H, "TGD step", "rewrites p into\na new prompt", BLUE)
box(xs[5], Y2, W, H, "Typed gradient", "one fix per rule,\ne.g. [TEMP-LATEST]", BLUE)
arr(xs[5] + W / 2, Y - 0.4, xs[5] + W / 2, Y2 + H + 0.4, "FAIL or a\nvalidator finding", xs[5] + W / 2 + 1.5, (Y + Y2 + H) / 2, ha="left")
for i in (5, 4, 3):
    arr(xs[i] - 0.35, Y2 + H / 2, xs[i - 1] + W + 0.35, Y2 + H / 2)
arr(xs[2] + W / 2, Y2 + H + 0.4, xs[2] + W / 2, Y - 0.4, "next iteration,\nup to K = 4", xs[2] + W / 2 - 1.5, (Y + Y2 + H) / 2, ha="right")
ax.text(0.5, 1.8, "The loop stops at PASS with no validator findings, or after K = 4 iterations. Each refinement costs four LLM calls.",
        fontsize=6.4, color=MUTED)
fig.savefig("fig1_architecture.png", bbox_inches="tight", pad_inches=0.04, facecolor="white")
plt.close(fig)

# ---------------------------------------------------------------- Fig. 2 validator detection
data = [("wrong-join-key", 17, 100, 18), ("drop-group-by", 21, 100, 0), ("global-latest", 15, 100, 0),
        ("earliest-not-latest", 15, 100, 47), ("drop-latest", 14, 100, 57), ("threshold-off-by-one", 7, 100, 0),
        ("threshold-direction", 7, 86, 71), ("or-to-and", 3, 100, 33), ("double-count-stock", 2, 100, 0),
        ("drop-stock", 2, 100, 100), ("drop-date-bound", 1, 100, 100), ("drop-no-retest", 1, 100, 100)][::-1]
fig, ax = plt.subplots(figsize=(6.0, 3.1), dpi=300)
ys = range(len(data))
b1 = ax.barh([y + 0.2 for y in ys], [d[2] for d in data], 0.38, color="#2C5D8F", label="Caught by static rules")
b2 = ax.barh([y - 0.2 for y in ys], [d[3] for d in data], 0.38, color="#C9820A", label="A metamorphic test also failed")
ax.bar_label(b1, fmt="%d%%", fontsize=6, padding=2, color=INK)
ax.bar_label(b2, fmt="%d%%", fontsize=6, padding=2, color=INK)
ax.set_yticks(list(ys), [f"{d[0]} ({d[1]})" for d in data], fontsize=7)
ax.set_xlim(0, 115); ax.tick_params(axis="x", labelsize=7)
ax.set_xlabel("Share of mutants of this type (%)", fontsize=7.5, color=INK)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=2)
fig.tight_layout(); fig.savefig("fig2_validator.png", facecolor="white"); plt.close(fig)

# ---------------------------------------------------------------- Fig. 3 germination decline by store
rows = json.load(open("germ.json"))
stores = ["Cold Room A", "Cold Room B", "Village Hub - Mandya", "Clay Pot Store", "Ambient Shelf"]
cols = ["#2C5D8F", "#6A93BF", "#5F9E83", "#C9820A", "#B3372F"]
fig, ax = plt.subplots(figsize=(6.0, 2.9), dpi=300)
for s, c in zip(stores, cols):
    pts = sorted((t, g) for st, t, g in rows if st == s)
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=7, color=c, alpha=0.75, label=f"{s} ({len(pts)} tests)", lw=0)
    n = len(pts); mx = sum(p[0] for p in pts) / n; my = sum(p[1] for p in pts) / n
    b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sum((p[0] - mx) ** 2 for p in pts)
    xx = [min(p[0] for p in pts), max(p[0] for p in pts)]
    ax.plot(xx, [my + b * (x - mx) for x in xx], color=c, lw=1.1)
ax.axhline(75, color=INK, lw=0.8, ls=(0, (4, 2)))
ax.text(14.2, 76.2, "75% retest threshold", fontsize=6.5, ha="right", color=INK)
ax.set_xlabel("Years since the lot was regenerated", fontsize=7.5); ax.set_ylabel("Germination rate (%)", fontsize=7.5)
ax.tick_params(labelsize=7); ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=6.3, frameon=False, loc="lower left", ncol=2)
ax.set_ylim(10, 102)
fig.tight_layout(); fig.savefig("fig3_germination.png", facecolor="white"); plt.close(fig)

# ---------------------------------------------------------------- Fig. 4 benchmark composition
cats = ["Temporal", "Domain", "Aggregation", "Join", "Retrieval"]
t = {1: [1, 1, 2, 0, 6], 2: [4, 5, 7, 5, 0], 3: [12, 8, 3, 6, 0]}
fig, ax = plt.subplots(figsize=(6.0, 2.2), dpi=300)
left = [0] * 5
for tier, c in zip((1, 2, 3), ("#C9D8E8", "#6A93BF", "#2C5D8F")):
    bars = ax.barh(cats[::-1], t[tier][::-1], left=left[::-1], color=c, label=f"Tier {tier}")
    for bar, v in zip(bars, t[tier][::-1]):
        if v:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2, str(v), ha="center", va="center",
                    fontsize=6.5, color="white" if tier > 1 else INK)
    left = [a + b for a, b in zip(left, t[tier])]
ax.set_xlabel("Number of questions", fontsize=7.5); ax.tick_params(labelsize=7)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=7, frameon=False, loc="lower right")
fig.tight_layout(); fig.savefig("fig4_benchmark.png", facecolor="white"); plt.close(fig)
