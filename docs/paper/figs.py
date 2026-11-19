import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
plt.rcParams["font.family"] = "Liberation Serif"

# ---------------- Fig. 1: pipeline
fig, ax = plt.subplots(figsize=(3.45, 4.9), dpi=300)
ax.set_xlim(-6, 100); ax.set_ylim(4, 142); ax.axis("off")
def box(x, y, w, h, text, fc="#ffffff", ec="#333333", bold=False, fs=6.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6", fc=fc, ec=ec, lw=0.8))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs, weight="bold" if bold else "normal", linespacing=1.15)
def arrow(x1, y1, x2, y2, text=None, tx=None, ty=None, ha="left"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", lw=0.8, color="#333333", mutation_scale=7))
    if text: ax.text(tx, ty, text, fontsize=5.8, ha=ha, va="center", style="italic", color="#333333")
LLM, DET, OUT = "#e8f0f8", "#eef5ee", "#fdf3e1"
box(25, 131, 50, 8, "Question q in plain English", OUT, bold=True)
box(5, 115, 90, 10, "1. Intent extraction (no LLM)\nlatest test? threshold? stock? years? entity?", DET)
box(5, 99, 90, 10, "2. Generator LLM with prompt p$_k$ + schema\nwrites one SQL query", LLM)
box(5, 83, 90, 10, "3. Run on read-only SQLite\nrows or error message", DET)
box(5, 64, 90, 13, "4. Validator (no gold answer)\nstatic domain rules  +  metamorphic tests\non in-memory copies of the database", DET)
box(5, 48, 90, 10, "5. Evaluator LLM writes the loss\nfrom the evidence; findings veto a PASS", LLM)
box(62, 27, 35, 11, "Return SQL\nand result", OUT, bold=True)
box(3, 30, 50, 11, "6. Gradient LLM: one fix\nper rule, e.g. [TEMP-LATEST]", LLM, fs=6.0)
box(3, 12, 50, 11, "7. TGD step LLM rewrites\nthe prompt: p$_k$ → p$_{k+1}$", LLM)
for y1, y2 in ((131, 125), (115, 109), (99, 93), (83, 77), (64, 58)):
    arrow(50, y1, 50, y2)
arrow(68, 48, 74, 38.6, "PASS + no findings,\nor k = K", 74, 43.3)
arrow(30, 48, 28, 41, "FAIL", 31, 44.5)
arrow(28, 30, 28, 23)
# loop back to generator
ax.plot([3, -3, -3], [17.5, 17.5, 104], color="#333333", lw=0.8)
arrow(-3, 104, 5, 104)
ax.text(-3, 8.5, "loop back: next iteration k + 1", fontsize=5.8, style="italic")
ax.add_patch(FancyBboxPatch((60, 12), 37, 11, boxstyle="round,pad=0.4", fc="white", ec="white"))
ax.text(78.5, 21, "Legend", fontsize=5.8, ha="center", weight="bold")
for i, (c, t) in enumerate(((LLM, "LLM call"), (DET, "deterministic code"), (OUT, "input / output"))):
    ax.add_patch(FancyBboxPatch((62, 16.5 - i*3.6), 3, 2.4, boxstyle="square,pad=0", fc=c, ec="#333333", lw=0.5))
    ax.text(67, 17.7 - i*3.6, t, fontsize=5.6, va="center")
fig.savefig("fig1_pipeline.png", bbox_inches="tight", pad_inches=0.02)
plt.close(fig)

# ---------------- Fig. 2: validator detection by mistake type (results/validator_eval/summary.md)
data = [("wrong-join-key", 17, 100, 100), ("drop-group-by", 21, 100, 100), ("global-latest", 15, 100, 100),
        ("earliest-not-latest", 15, 100, 100), ("drop-latest", 14, 100, 100), ("threshold-off-by-one", 7, 100, 100),
        ("threshold-direction", 7, 86, 100), ("or-to-and", 3, 100, 100), ("double-count-stock", 2, 100, 100),
        ("drop-stock", 2, 100, 100), ("drop-date-bound", 1, 100, 100), ("drop-no-retest", 1, 100, 100)]
mt = {"drop-latest": 57, "earliest-not-latest": 47, "threshold-direction": 71, "or-to-and": 33, "wrong-join-key": 18,
      "drop-stock": 100, "drop-date-bound": 100, "drop-no-retest": 100}
fig, ax = plt.subplots(figsize=(3.45, 2.9), dpi=300)
names = [f"{n} ({k})" for n, k, _, _ in data][::-1]
ys = range(len(data))
st = [s for _, _, s, _ in data][::-1]
mm = [mt.get(n, 0) for n, _, _, _ in data][::-1]
ax.barh([y + 0.2 for y in ys], st, 0.38, color="#2c5d8f", label="caught by static rules (%)")
ax.barh([y - 0.2 for y in ys], mm, 0.38, color="#c9820a", label="a metamorphic test failed (%)")
ax.set_yticks(list(ys), names, fontsize=6)
ax.tick_params(axis="x", labelsize=6)
ax.set_xlim(0, 105)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(fontsize=5.8, frameon=False, loc="lower center", bbox_to_anchor=(0.35, -0.24), ncol=2)
ax.set_xlabel("")
fig.savefig("fig2_mutants.png", bbox_inches="tight", pad_inches=0.02)
