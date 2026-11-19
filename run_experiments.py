"""Run the benchmark: compare zero-shot, few-shot, error-retry and TextGrad on the seed-bank questions.

Examples
  python run_experiments.py --provider groq                       # all methods, all tiers
  python run_experiments.py --provider gemini --methods zero few textgrad --tiers 3
  python run_experiments.py --provider ollama --model qwen2.5-coder:7b --max-iters 5
  python run_experiments.py --provider openai --methods textgrad_lib   # official textgrad package
  python run_experiments.py --provider mock                       # offline pipeline smoke test (fake model)
  python run_experiments.py --provider groq --repeats 3           # repeat to measure variance

Outputs go to results/<run_id>/: records.jsonl (full traces), summary.csv, summary.md, charts/*.png
"""
import sys, os
if hasattr(sys.stdout, "reconfigure"):  # Windows console: avoid UnicodeEncodeError, enable colours
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
if os.name == "nt":
    os.system("")

import argparse
import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict

from seedsql.db import SeedBankDB, error_category, results_match
from seedsql.methods import RuleMemory
from seedsql.perturb import robust_match
from seedsql.validator import validate
from seedsql.llm import LLM
from seedsql.methods import LABELS, run_method
from seedsql.prompts import BASE_INSTRUCTIONS, BENCH

ERROR_CATS = ["Syntax error", "Unknown column", "Unknown table", "Ambiguous column", "Aggregation misuse",
              "Other execution error", "Invalid / non-SELECT", "Wrong result", "Wrong result (empty)"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--methods", nargs="+", default=["zero", "few", "selfcorr", "textgrad", "vg_textgrad"],
                    choices=["zero", "few", "selfcorr", "textgrad", "textgrad_lib", "vg_retry", "vg_textgrad_static", "vg_textgrad"],
                    help="ablations: vg_retry (validator feedback without TextGrad), vg_textgrad_static (no metamorphic tests)")
    ap.add_argument("--categories", nargs="+", default=None,
                    help="question categories to run: retrieval aggregation join temporal domain (default: all)")
    ap.add_argument("--states", type=int, default=5, help="changed database states for temporal robustness accuracy")
    ap.add_argument("--tiers", nargs="+", type=int, default=[1, 2, 3])
    ap.add_argument("--max-iters", type=int, default=4)
    ap.add_argument("--carry", action="store_true",
                    help="prompt-level optimisation: carry TextGrad's optimised prompt across questions")
    ap.add_argument("--repeats", type=int, default=1,
                    help="run every method N times; use 3 for the paper so run-to-run variance can be reported")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--min-interval", type=float, default=0.0, help="seconds between LLM calls (rate limits)")
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    db = SeedBankDB()
    llm = LLM(args.provider, args.model, temperature=args.temperature, base_url=args.base_url,
              min_interval_s=args.min_interval)
    qs = [q for q in BENCH["questions"] if q["tier"] in args.tiers
          and (not args.categories or q.get("category") in args.categories)]
    for q in qs:
        q["gold"] = db.run(q["gold_sql"])
        assert q["gold"]["ok"], q["id"]

    run_id = time.strftime("%Y%m%d-%H%M%S") + f"_{args.provider}_{(llm.model or '').replace('/', '-').replace(':', '-')}"
    out_dir = os.path.join(args.out, run_id)
    os.makedirs(os.path.join(out_dir, "charts"), exist_ok=True)
    with open(os.path.join(out_dir, "config.json"), "w") as f:
        json.dump(vars(args) | {"model_resolved": llm.model, "n_questions": len(qs)}, f, indent=2)
    if args.provider == "mock":
        print("!! MOCK PROVIDER: a fake model used only to test the pipeline. These are NOT experimental results.")

    records = []
    rec_path = os.path.join(out_dir, "records.jsonl")
    total = len(qs) * len(args.methods) * args.repeats
    n = 0
    t0 = time.time()
    with open(rec_path, "w", encoding="utf-8") as rf:
        for rep in range(args.repeats):
            for m in args.methods:
                carried = BASE_INSTRUCTIONS
                memory = RuleMemory() if (args.carry and m.startswith("vg_textgrad")) else None
                for q in qs:
                    n += 1
                    try:
                        out = run_method(m, q["question"], llm, db, max_iters=args.max_iters,
                                         initial_instructions=carried if (args.carry and m.startswith("textgrad")) else BASE_INSTRUCTIONS,
                                         carry=args.carry, memory=memory)
                    except Exception as e:  # keep going; record the failure
                        print(f"[{n}/{total}] {m:12s} {q['id']}  FAILED: {e}", file=sys.stderr)
                        if "HTTP 401" in str(e) or "HTTP 403" in str(e):
                            print("Stopping: authentication/access error - every call would fail.", file=sys.stderr)
                            sys.exit(1)
                        rec = {"rep": rep, "qid": q["id"], "tier": q["tier"], "method": m, "failed": str(e)}
                        rf.write(json.dumps(rec) + "\n")
                        continue
                    if args.carry and out.get("final_instructions"):
                        carried = out["final_instructions"]
                    first, fin = out["iterations"][0]["res"], out["final"]["res"]
                    fc, lc = results_match(q["gold"], first), results_match(q["gold"], fin)
                    _, robust, _ = robust_match(db, q["gold_sql"], out["final"]["sql"], n_states=args.states, seed=n)
                    sem = validate(q["question"], out["final"]["sql"], db, res=fin)   # gold-free semantic audit
                    rec = {"rep": rep, "qid": q["id"], "tier": q["tier"], "category": q.get("category"), "method": m, "model": llm.model,
                           "question": q["question"], "correct": lc, "robust": robust, "rule_compliant": sem.ok,
                           "final_semantic_categories": sem.categories(), "executed": fin["ok"], "first_correct": fc, "first_executed": first["ok"],
                           "iterations": len(out["iterations"]), "calls": out["calls"],
                           "first_error": error_category(first, fc), "final_error": error_category(fin, lc),
                           "final_sql": out["final"]["sql"], "final_instructions": out.get("final_instructions"),
                           "rule_memory": out.get("memory"),
                           "trace": [{k: v for k, v in it.items() if k != "res"} |
                                     {"ok": it["res"]["ok"], "error": it["res"].get("error"),
                                      "rows": len(it["res"]["values"]) if it["res"]["ok"] else None,
                                      "matches_gold": results_match(q["gold"], it["res"])}
                                     for it in out["iterations"]]}
                    records.append(rec)
                    rf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    rf.flush()
                    mark = "OK " if lc else ("RUN" if fin["ok"] else "ERR")
                    print(f"[{n}/{total}] {LABELS[m]:18s} {q['id']}  {mark}  iters={rec['iterations']} "
                          f"calls={rec['calls']}  {time.time() - t0:5.0f}s")

    if not records:
        print("\nNo successful runs - nothing to summarise. Fix the error above and rerun.")
        return
    # record the model(s) actually used, including any automatic fallback switch
    cfg_path = os.path.join(out_dir, "config.json")
    cfg = json.load(open(cfg_path))
    cfg |= {"model_final": llm.model, "model_switches": getattr(llm, "model_switches", []),
            "models_used": sorted({r["model"] for r in records}), "llm_calls_total": llm.calls}
    json.dump(cfg, open(cfg_path, "w"), indent=2)
    write_summary(records, args, llm, out_dir)
    try:
        from analyze_results import analyze
        analyze(out_dir)               # paired McNemar tests, confidence intervals, paper-ready tables
    except Exception as e:             # statistics must never lose a finished run
        print(f"(statistics step skipped: {e})")
    print(f"\nDone. {llm.calls} LLM calls. Results in {out_dir}/")


def _agg(rs):
    n = len(rs)
    pct = lambda k: 100.0 * sum(1 for r in rs if r[k]) / n
    return {"n": n, "execution_accuracy": pct("correct"), "temporal_robust_accuracy": pct("robust"),
            "rule_compliance": pct("rule_compliant"), "successful_query_rate": pct("executed"),
            "avg_iterations": statistics.mean(r["iterations"] for r in rs),
            "avg_llm_calls": statistics.mean(r["calls"] for r in rs),
            "first_attempt_accuracy": pct("first_correct"),
            "errors_first": sum(1 for r in rs if r["first_error"]),
            "errors_final": sum(1 for r in rs if r["final_error"])}


def write_summary(records, args, llm, out_dir):
    groups = defaultdict(list)
    for r in records:
        groups[(r["method"], r["tier"])].append(r)
        groups[(r["method"], "all")].append(r)
        groups[(r["method"], "cat:" + str(r.get("category")))].append(r)
    cats = sorted({str(r.get("category")) for r in records})
    rows = []
    for m in args.methods:
        for t in ["all"] + sorted(args.tiers) + ["cat:" + c for c in cats]:
            if groups.get((m, t)):
                rows.append({"method": LABELS[m], "tier": t} | _agg(groups[(m, t)]))
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})

    # error categories (first attempt vs final)
    err = {m: {"first": Counter(r["first_error"] for r in records if r["method"] == m and r["first_error"]),
               "final": Counter(r["final_error"] for r in records if r["method"] == m and r["final_error"])}
           for m in args.methods}

    md = [f"# Results: {llm.provider} / {llm.model}", "",
          f"Questions per run: {len(set(r['qid'] for r in records))} · repeats: {args.repeats} · "
          f"max iterations: {args.max_iters} · carry prompt: {args.carry}", ""]
    if args.provider == "mock":
        md += ["> **MOCK PROVIDER: pipeline test only, not experimental results.**", ""]
    md += ["Exec. accuracy = final result matches gold on the benchmark database. Temporal robust accuracy = matches gold on the "
           "original AND on every changed database state. Rule compliance = no finding from the gold-free validator (for the VG "
           "methods this is partly circular, because they were optimised against it).", "",
           "| Method | Tier / category | n | Exec. accuracy | Temporal robust acc. | Rule compliance | Successful query rate | Avg. iterations | Avg. LLM calls | First-attempt acc. | Errors first→final |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['method']} | {str(r['tier']).replace('cat:', '')} | {r['n']} | {r['execution_accuracy']:.1f}% | "
                  f"{r['temporal_robust_accuracy']:.1f}% | {r['rule_compliance']:.1f}% | "
                  f"{r['successful_query_rate']:.1f}% | {r['avg_iterations']:.2f} | {r['avg_llm_calls']:.1f} | "
                  f"{r['first_attempt_accuracy']:.1f}% | {r['errors_first']}→{r['errors_final']} |")
    sem = {m: Counter(c for r in records if r["method"] == m for c in r.get("final_semantic_categories", [])) for m in args.methods}
    md += ["", "## Remaining semantic issues in final answers (gold-free validator, by category)", "",
           "| Method | schema | join | temporal | domain | aggregation | execution |", "|---|---|---|---|---|---|---|"]
    for m in args.methods:
        md.append(f"| {LABELS[m]} | " + " | ".join(str(sem[m].get(c, 0)) for c in ("schema", "join", "temporal", "domain", "aggregation", "execution")) + " |")
    md += ["", "## Error categories (first attempt → final answer)", "",
           "| Method | " + " | ".join(ERROR_CATS) + " |", "|---|" + "---|" * len(ERROR_CATS)]
    for m in args.methods:
        md.append(f"| {LABELS[m]} | " + " | ".join(f"{err[m]['first'].get(c, 0)}→{err[m]['final'].get(c, 0)}"
                                                    for c in ERROR_CATS) + " |")
    md += ["", "## Per-question outcome (✓ correct · ✗ wrong result · E execution error)", "",
           "| Question | Tier | " + " | ".join(LABELS[m] for m in args.methods) + " |",
           "|---|---|" + "---|" * len(args.methods)]
    for qid in sorted(set(r["qid"] for r in records)):
        cells = []
        for m in args.methods:
            rs = [r for r in records if r["qid"] == qid and r["method"] == m]
            cells.append(" ".join(("✓" if r["correct"] else "✗" if r["executed"] else "E") +
                                  (f"({r['iterations']})" if r["iterations"] > 1 else "") for r in rs))
        tier = next(r["tier"] for r in records if r["qid"] == qid)
        md.append(f"| {qid} | {tier} | " + " | ".join(cells) + " |")
    with open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n" + "\n".join(md[:len(rows) + 6]))
    make_charts(records, args, err, out_dir)


def make_charts(records, args, err, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed: skipping charts)")
        return
    colors = {"zero": "#9aa5a0", "few": "#2c5d8f", "selfcorr": "#c9820a", "textgrad": "#5f9e83",
              "textgrad_lib": "#6a4c93", "vg_retry": "#d9a441", "vg_textgrad_static": "#8c6bb1", "vg_textgrad": "#1f5c45"}
    tiers = sorted(args.tiers)
    metrics = [("execution_accuracy", "Execution accuracy (%)", 100), ("temporal_robust_accuracy", "Temporal robust accuracy (%)", 100),
               ("successful_query_rate", "Successful query rate (%)", 100),
               ("avg_iterations", "Average generate→execute iterations", None)]
    for key, title, ymax in metrics:
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        w = 0.8 / len(args.methods)
        for i, m in enumerate(args.methods):
            vals = []
            for t in tiers:
                rs = [r for r in records if r["method"] == m and r["tier"] == t]
                vals.append(_agg(rs)[key] if rs else 0)
            xs = [j + (i - (len(args.methods) - 1) / 2) * w for j in range(len(tiers))]
            bars = ax.bar(xs, vals, w * 0.92, label=LABELS[m], color=colors.get(m, "#777"))
            ax.bar_label(bars, fmt="%.0f" if ymax else "%.2f", fontsize=8, padding=2)
        ax.set_xticks(range(len(tiers)), [f"Tier {t}" for t in tiers])
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
        if ymax:
            ax.set_ylim(0, ymax * 1.1)
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=9, ncol=len(args.methods), loc="upper center", bbox_to_anchor=(0.5, -0.08))
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "charts", f"{key}.png"), dpi=160)
        plt.close(fig)
    # execution accuracy by question category
    cats = sorted({str(r.get("category")) for r in records})
    fig, ax = plt.subplots(figsize=(max(7.5, 1.4 * len(cats)), 4.2))
    w = 0.8 / len(args.methods)
    for i, m in enumerate(args.methods):
        vals = [_agg([r for r in records if r["method"] == m and str(r.get("category")) == c])["execution_accuracy"]
                if any(r["method"] == m and str(r.get("category")) == c for r in records) else 0 for c in cats]
        xs = [j + (i - (len(args.methods) - 1) / 2) * w for j in range(len(cats))]
        ax.bar(xs, vals, w * 0.92, label=LABELS[m], color=colors.get(m, "#777"))
    ax.set_xticks(range(len(cats)), cats)
    ax.set_ylim(0, 110)
    ax.set_title("Execution accuracy by question category (%)", fontsize=12, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, ncol=min(4, len(args.methods)), loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "charts", "accuracy_by_category.png"), dpi=160)
    plt.close(fig)
    # error categories stacked
    labels, data = [], {c: [] for c in ERROR_CATS}
    for m in args.methods:
        for stage in ("first", "final"):
            labels.append(f"{LABELS[m]}\n{stage}")
            for c in ERROR_CATS:
                data[c].append(err[m][stage].get(c, 0))
    fig, ax = plt.subplots(figsize=(max(7.5, 1.1 * len(labels)), 4.4))
    bottom = [0] * len(labels)
    palette = ["#b3372f", "#d9654f", "#e8a07a", "#8c6bb1", "#6a4c93", "#7a7a7a", "#444444", "#c9820a", "#e6c26e"]
    for c, col in zip(ERROR_CATS, palette):
        if any(data[c]):
            ax.bar(labels, data[c], bottom=bottom, label=c, color=col)
            bottom = [b + v for b, v in zip(bottom, data[c])]
    ax.set_title("Error categories: first attempt vs final answer", fontsize=12, fontweight="bold", loc="left")
    ax.set_ylabel("questions")
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8, bbox_to_anchor=(1.01, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "charts", "error_categories.png"), dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
