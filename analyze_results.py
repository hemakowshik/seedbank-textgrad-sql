"""Statistics for a finished run: confidence intervals, run-to-run variance and paired McNemar tests.

    python analyze_results.py results/<run_id>

Writes results/<run_id>/stats.md (and prints it). run_experiments.py calls this automatically.

- Execution accuracy and temporal robust accuracy get 95% Wilson confidence intervals.
- With --repeats > 1 the mean and standard deviation across repeats are shown.
- Two methods are compared on the SAME questions with the exact McNemar test: only the questions where
  one method is right and the other is wrong count (b = only A right, c = only B right).
  p = two-sided binomial probability of a split at least this uneven, given b + c discordant questions.
  Holm's correction is applied across all comparisons in the table.
"""
import json
import math
import os
import statistics
import sys
from collections import defaultdict

try:
    from seedsql.methods import LABELS
except Exception:  # keep the script usable on its own
    LABELS = {}

PAIRS = [("vg_textgrad", "textgrad"), ("vg_textgrad", "vg_retry"), ("vg_textgrad", "vg_textgrad_static"),
         ("vg_textgrad", "few"), ("vg_textgrad", "zero"), ("textgrad", "selfcorr"), ("textgrad", "few"),
         ("textgrad", "zero"), ("few", "zero"), ("selfcorr", "zero")]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * max(0.0, c - h), 100 * min(1.0, c + h))


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def load(run_dir):
    recs = [json.loads(l) for l in open(os.path.join(run_dir, "records.jsonl"), encoding="utf-8") if l.strip()]
    recs = [r for r in recs if "failed" not in r]
    cfg_path = os.path.join(run_dir, "config.json")
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    return recs, cfg


def analyze(run_dir, write=True):
    recs, cfg = load(run_dir)
    if not recs:
        raise SystemExit("no successful records in " + run_dir)
    methods = [m for m in cfg.get("methods", []) if any(r["method"] == m for r in recs)] or \
        sorted({r["method"] for r in recs})
    lab = lambda m: LABELS.get(m, m)
    out = [f"# Statistics for {os.path.basename(run_dir.rstrip('/'))}", ""]
    if cfg.get("provider") == "mock":
        out += ["> **MOCK PROVIDER: pipeline test only. Do not report these numbers.**", ""]
    out += [f"Model(s) used: {', '.join(cfg.get('models_used') or [cfg.get('model_resolved', '?')])} · "
            f"repeats: {cfg.get('repeats', 1)} · questions: {len({r['qid'] for r in recs})}", ""]
    if cfg.get("model_switches"):
        out += [f"Model switches during the run: {cfg['model_switches']}", ""]

    out += ["## Accuracy with 95% confidence intervals", "",
            "| Method | n | Exec. accuracy [95% CI] | Temporal robust acc. [95% CI] | Rule compliance | First-attempt acc. | Avg. LLM calls | Exec. acc. mean ± sd over repeats |",
            "|---|---|---|---|---|---|---|---|"]
    for m in methods:
        rs = [r for r in recs if r["method"] == m]
        n = len(rs)
        k, kr = sum(r["correct"] for r in rs), sum(r["robust"] for r in rs)
        lo, hi = wilson(k, n)
        rlo, rhi = wilson(kr, n)
        reps = defaultdict(list)
        for r in rs:
            reps[r["rep"]].append(r["correct"])
        per = [100 * sum(v) / len(v) for v in reps.values()]
        var = f"{statistics.mean(per):.1f} ± {statistics.stdev(per):.1f}" if len(per) > 1 else "single run"
        out.append(f"| {lab(m)} | {n} | {100*k/n:.1f}% [{lo:.1f}, {hi:.1f}] | {100*kr/n:.1f}% [{rlo:.1f}, {rhi:.1f}] | "
                   f"{100*sum(r['rule_compliant'] for r in rs)/n:.1f}% | {100*sum(r['first_correct'] for r in rs)/n:.1f}% | "
                   f"{statistics.mean(r['calls'] for r in rs):.1f} | {var} |")

    for metric, title in (("correct", "execution accuracy"), ("robust", "temporal robust accuracy")):
        idx = {(r["method"], r["rep"], r["qid"]): r[metric] for r in recs}
        rows = []
        for a, b in PAIRS:
            if a not in methods or b not in methods:
                continue
            keys = [(rep, q) for (m, rep, q) in idx if m == a and (b, rep, q) in idx]
            only_a = sum(1 for k in keys if idx[(a,) + k] and not idx[(b,) + k])
            only_b = sum(1 for k in keys if idx[(b,) + k] and not idx[(a,) + k])
            rows.append([a, b, len(keys), only_a, only_b, mcnemar_exact(only_a, only_b)])
        if not rows:
            continue
        for row, p in zip(rows, holm([r[5] for r in rows])):
            row.append(p)
        out += ["", f"## Paired comparison on {title} (exact McNemar test, Holm-corrected)", "",
                "| A vs B | paired items | only A right | only B right | p | p (Holm) | significant at 0.05 |",
                "|---|---|---|---|---|---|---|"]
        for a, b, n, oa, ob, p, ph in rows:
            out.append(f"| {lab(a)} vs {lab(b)} | {n} | {oa} | {ob} | {p:.4f} | {ph:.4f} | {'yes' if ph < 0.05 else 'no'} |")

    cats = sorted({str(r.get("category")) for r in recs})
    out += ["", "## Execution accuracy by question category", "",
            "| Method | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for m in methods:
        cells = []
        for c in cats:
            rs = [r for r in recs if r["method"] == m and str(r.get("category")) == c]
            cells.append(f"{100*sum(r['correct'] for r in rs)/len(rs):.1f}% ({len(rs)})" if rs else "-")
        out.append(f"| {lab(m)} | " + " | ".join(cells) + " |")
    text = "\n".join(out) + "\n"
    if write:
        with open(os.path.join(run_dir, "stats.md"), "w", encoding="utf-8") as f:
            f.write(text)
    print(text)
    return text


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    analyze(sys.argv[1])
