"""Why one database state is not enough (offline, no LLM, reproducible).

    python eval_robustness.py   -> results/robustness_eval/summary.md

For every gold query we generate the same injected mistakes as eval_validator.py and keep the mutants that
execute and return EXACTLY the gold answer on the benchmark database. Ordinary execution accuracy would
score these wrong queries as correct. Temporal robust accuracy (TRA) re-runs gold and mutant on changed
database states (seedsql/perturb.py); a mutant that diverges on any state is a hidden mistake.
Also checks that TRA never rejects a correct query: all gold queries and all correct rewrites must pass.
"""
import json
import os
import sys
import time
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from seedsql.db import SeedBankDB, results_match
from seedsql.intent import extract_intent
from seedsql.methods import applicable_rules
from seedsql.mutants import mutants
from seedsql.perturb import robust_match
from seedsql.prompts import BENCH
from seedsql.validator import validate

STATES = 5


def main():
    db = SeedBankDB()
    qs = BENCH["questions"]
    out = ["# Temporal robustness and validator coverage (offline, no LLM)", ""]

    hidden, flagged, equivalent, per_op = [], [], 0, Counter()
    for q in qs:
        gold = db.run(q["gold_sql"])
        for op_id, cat, sql in mutants(q["gold_sql"]):
            res = db.run(sql)
            if not res["ok"] or not results_match(gold, res):
                continue
            base, robust, _ = robust_match(db, q["gold_sql"], sql, n_states=STATES, seed=7)
            if base and not robust:
                hidden.append((q["id"], op_id))
                flagged.append(not validate(q["question"], sql, db, res=res).ok)
                per_op[op_id] += 1
            else:
                equivalent += 1
    out += [f"Mutants that return exactly the gold answer on the benchmark database: {len(hidden) + equivalent}",
            f"- diverge from gold on at least one of {STATES} changed states (hidden mistakes, counted correct by "
            f"ordinary execution accuracy, rejected by TRA): **{len(hidden)}** in {len({h[0] for h in hidden})} questions",
            f"- of these hidden mistakes, flagged by the gold-free validator: {sum(flagged)}/{len(hidden)}",
            f"- same answer on every changed state (no evidence of a mistake): {equivalent}", ""]
    if per_op:
        out += ["| Mistake type | Hidden mistakes |", "|---|---|"] + [f"| {k} | {v} |" for k, v in per_op.most_common()] + [""]
    if hidden:
        out += ["Questions: " + ", ".join(sorted({h[0] for h in hidden})), ""]

    # TRA must accept correct queries
    gold_ok = sum(robust_match(db, q["gold_sql"], q["gold_sql"], n_states=STATES, seed=3)[1] for q in qs)
    rew = json.load(open(os.path.join("data", "equivalent_rewrites.json"), encoding="utf-8"))["rewrites"]
    qmap = {q["id"]: q for q in qs}
    pairs = [(qid, s) for qid, ss in rew.items() for s in ss]
    rew_ok = sum(robust_match(db, qmap[qid]["gold_sql"], s, n_states=STATES, seed=3)[1] for qid, s in pairs)
    out += [f"Correct queries accepted by TRA: gold {gold_ok}/{len(qs)}, correct rewrites {rew_ok}/{len(pairs)}", ""]

    # how the intent extractor routes questions to rules
    cov = Counter()
    for q in qs:
        for r in applicable_rules(extract_intent(q["question"])) - {"JOIN-KEY", "DOM-DOUBLECOUNT", "SCHEMA"}:
            cov[r] += 1
    out += ["## Questions for which each question-dependent rule is activated by intent extraction", "",
            "| Rule | Questions |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(cov.items())] + [""]

    # metamorphic tests and validator cost on the gold queries
    t0, n_tests, with_tests = time.perf_counter(), 0, 0
    for q in qs:
        rep = validate(q["question"], q["gold_sql"], db)
        k = getattr(rep, "tests_run", 0) or 0
        n_tests += k
        with_tests += 1 if k else 0
    ms = 1000 * (time.perf_counter() - t0) / len(qs)
    out += [f"Metamorphic tests run on the gold queries: {n_tests} in total; questions with at least one test: "
            f"{with_tests}/{len(qs)}; mean validator time per query: {ms:.0f} ms (static + metamorphic)", ""]

    os.makedirs(os.path.join("results", "robustness_eval"), exist_ok=True)
    with open(os.path.join("results", "robustness_eval", "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
