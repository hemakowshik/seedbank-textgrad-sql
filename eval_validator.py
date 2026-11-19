"""Offline evaluation of the domain/temporal validator (no LLM, no API key, fully reproducible).

  python eval_validator.py            -> results/validator_eval/{mutants.csv, summary.md}

1. False-alarm rate: the validator is run on every gold query; any finding is a false alarm.
2. Detection rate (recall): realistic semantic mistakes are injected into the gold queries
   (seedsql/mutants.py). A mutant is kept only if it executes and returns a different answer from gold,
   i.e. it is wrong but execution feedback alone would accept it. We report how many the validator flags
   with static rules only and with static rules + metamorphic tests, per mistake type.
"""
import csv
import os
import sys
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from seedsql.db import SeedBankDB, results_match
from seedsql.mutants import mutants
from seedsql.prompts import BENCH
from seedsql.validator import validate


def main():
    db = SeedBankDB()
    out_dir = os.path.join("results", "validator_eval")
    os.makedirs(out_dir, exist_ok=True)
    qs = BENCH["questions"]

    false_alarms = []
    for q in qs:
        rep = validate(q["question"], q["gold_sql"], db)
        if not rep.ok:
            false_alarms.append((q["id"], [f.rule for f in rep.findings]))

    # false alarms on correct queries written in a different style from the gold SQL
    import json
    rew = json.load(open(os.path.join("data", "equivalent_rewrites.json"), encoding="utf-8"))["rewrites"]
    qmap = {q["id"]: q for q in qs}
    rew_total, rew_alarms, rew_notequiv = 0, [], []
    for qid, sqls in rew.items():
        gold = db.run(qmap[qid]["gold_sql"])
        for sql in sqls:
            res = db.run(sql)
            if not results_match(gold, res):
                rew_notequiv.append(qid)
                continue
            rew_total += 1
            rep = validate(qmap[qid]["question"], sql, db, res=res)
            if not rep.ok:
                rew_alarms.append((qid, [f.rule for f in rep.findings]))

    rows = []
    for q in qs:
        gold = db.run(q["gold_sql"])
        for op_id, cat, sql in mutants(q["gold_sql"]):
            res = db.run(sql)
            if not res["ok"] or results_match(gold, res):
                continue  # crashes are caught by execution feedback; equivalent mutants are not mistakes
            st = validate(q["question"], sql, db, res=res, mode="static")
            full = validate(q["question"], sql, db, res=res, mode="full")
            rows.append({"qid": q["id"], "operator": op_id, "category": cat, "static_flagged": not st.ok,
                         "full_flagged": not full.ok, "metamorphic_flagged": any(f.source == "metamorphic" for f in full.findings),
                         "rules": ";".join(sorted({f.rule for f in full.findings})), "sql": sql})
    with open(os.path.join(out_dir, "mutants.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["qid"])
        w.writeheader()
        w.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["operator"]].append(r)
    pct = lambda a, b: f"{100 * a / b:.0f}%" if b else "-"
    n = len(rows)
    s_all = sum(r["static_flagged"] for r in rows)
    f_all = sum(r["full_flagged"] for r in rows)
    lines = ["# Validator evaluation (offline, no LLM)", "",
             f"Gold queries: {len(qs)} · false alarms on gold: {len(false_alarms)} ({pct(len(false_alarms), len(qs))})", "",
             f"Correct rewrites in other SQL styles: {rew_total} · false alarms: {len(rew_alarms)} ({pct(len(rew_alarms), rew_total)})"
             + (f" · rewrites that did not match gold (excluded): {rew_notequiv}" if rew_notequiv else ""), "",
             f"Wrong-but-executing mutants: {n} · detected by static rules: {s_all} ({pct(s_all, n)}) · "
             f"detected by static + metamorphic: {f_all} ({pct(f_all, n)})", "",
             "| Mistake injected | Category | Mutants | Static rules | Static + metamorphic | Metamorphic tests fired |",
             "|---|---|---|---|---|---|"]
    for op, rs in sorted(by.items()):
        k = len(rs)
        lines.append(f"| {op} | {rs[0]['category']} | {k} | {pct(sum(r['static_flagged'] for r in rs), k)} | "
                     f"{pct(sum(r['full_flagged'] for r in rs), k)} | {pct(sum(r['metamorphic_flagged'] for r in rs), k)} |")
    missed = [r for r in rows if not r["full_flagged"]]
    lines += ["", f"Missed mutants: {len(missed)}"] + [f"- {r['qid']} / {r['operator']}" for r in missed]
    if false_alarms or rew_alarms:
        lines += ["", "False alarms:"] + [f"- {a}: {b}" for a, b in false_alarms + rew_alarms]
    lines += ["", "Note: the rules were developed on this benchmark, so these figures are optimistic. "
              "An independent question set is needed for an unbiased estimate."]
    text = "\n".join(lines) + "\n"
    open(os.path.join(out_dir, "summary.md"), "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
