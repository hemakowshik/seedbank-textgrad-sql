# SeedSQL — research direction (v2)

**Title.** SeedSQL: Intent-Conditioned Metamorphic Validation for Gold-Free, Validation-Guided TextGrad Refinement of Temporal Text-to-SQL

**One-line idea.** A query that runs is not a query that is right. SeedSQL checks *what the question means* (latest test per lot, viability threshold, stock, date range) by changing the database in controlled ways and verifying that the query's answer changes the way the question says it must, without any reference answer. It then turns those failures into rule-tagged textual gradients for TextGrad.

## 1. What changed from the earlier plan, and why it is more novel

| Earlier plan (ChatGPT draft) | SeedSQL v2 (implemented here) | Why it matters |
|---|---|---|
| A rule validator checks SQL against domain rules | **Intent-conditioned rules**: rules fire only when the question's intent (extracted deterministically, no LLM) requires them; thresholds and phrases live in `data/domain_rules.json` | Avoids false alarms on questions where a rule does not apply; configurable without code changes |
| "Temporal test generation" on modified database states (used for evaluation) | **Metamorphic tests used *during inference* as a gold-free oracle**. Each test applies a controlled change (a newer passing test, zero stock, a later retest, a record outside the stated period, an out-of-range reading) and checks an expected *relation* on the query's output that follows from the question alone | The live system gets semantic evidence for queries that execute and look plausible, the case execution feedback and generic LLM judges miss |
| Structured feedback to TextGrad | **Typed textual gradients + validator veto.** Findings are tagged with rule ids; the gradient must give one targeted instruction per rule; a failed rule vetoes an LLM-judge "PASS" | Targets the gradient at the actual error; prevents early stopping on a false PASS |
| (none) | **Intent-conditioned rule memory** for prompt-level optimisation: rule-tagged lessons are stored per rule and re-injected only for questions whose intent needs them | Lets lessons transfer across questions without the prompt growing and drifting |
| Execution accuracy + semantic metrics | **Temporal robust accuracy (TRA)**: final SQL must match gold on the original database *and* on several changed states (new retests, stock changes, next year's records) | Exposes answers that are right only by coincidence on one database state |
| (none) | **Mutation-based evaluation of the validator itself** (precision and recall, no LLM needed) | Shows the semantic signal is reliable *before* it is used to train prompts |

## 2. Research questions and hypotheses

- **RQ1 (signal quality).** How reliably does a gold-free, intent-conditioned validator detect semantic errors in SQL that executes? *Measured offline by mutation testing: detection rate on wrong-but-executing mutants and false-alarm rate on gold and on correct rewrites.*
- **RQ2 (refinement).** Does validation-guided TextGrad (VG-TextGrad) improve execution accuracy and temporal robust accuracy over zero-shot, few-shot, error-retry and standard TextGrad? *H2: gains concentrate on temporal and domain questions.*
- **RQ3 (ablation).** Which part matters: the validator evidence, the TextGrad optimisation, or the metamorphic tests? *Compare VG-TextGrad with Validator-retry (no TextGrad) and VG-TextGrad (static) (no metamorphic tests).*
- **RQ4 (transfer).** Does the intent-conditioned rule memory improve later questions in prompt-level mode compared with carrying the whole prompt?

## 3. Methods compared

| Method | Uses validator | Uses TextGrad | Purpose |
|---|---|---|---|
| Zero-shot, Few-shot | no | no | Static baselines |
| Error-retry | no | no | Execution-feedback baseline |
| TextGrad | no | yes | Standard TextGrad (generic LLM loss) |
| Validator-retry | yes (full) | no | Ablation: evidence without optimisation |
| VG-TextGrad (static) | rules only | yes | Ablation: no metamorphic tests |
| **VG-TextGrad** | rules + metamorphic | yes | **Proposed** |

## 4. Evidence so far (offline, reproducible: `python eval_validator.py`)

On the 60-question benchmark (real ICRISAT accessions, simulated monitoring records):

- **False alarms:** 0 of 60 gold queries; 0 of 18 correct queries written in other SQL styles (CTEs, window functions, NOT EXISTS, `strftime`, `USING`).
- **Detection:** 105 of 105 wrong-but-executing mutants flagged (12 mistake types: dropped latest-record logic, global instead of per-lot latest, earliest instead of latest, dropped retest condition, dropped date bound, threshold off-by-one or reversed, dropped stock filter, OR→AND, double-counted distributions, wrong join key, dropped GROUP BY).
- **Coincidental correctness:** 9 mutants return exactly the gold answer on the benchmark database. The gold-free validator flags 8 of them; random state changes (TRA) expose 5; the remaining 4 are effectively equivalent at the granularity of their question.

**Caveat.** The rules were refined on this same benchmark (development set), so these numbers are optimistic. An independent, held-out question set written by someone else is required before reporting them as results. LLM experiments (RQ2–RQ4) have not been run yet.

## 5. Positioning against prior work (verify against the full papers)

| Work | Their mechanism | Difference in SeedSQL |
|---|---|---|
| TextGrad (Yuksekgonul et al., 2024) | Generic textual loss and gradients | Loss and gradient grounded in validator evidence; typed gradients; validator veto; rule memory |
| SQLPrompt (2023) | Diverse candidates + execution-consistency selection | No candidate voting; a single query is repaired using semantic evidence |
| DART-SQL (2024) | Question rewriting + execution-guided refinement | Evidence goes beyond execution errors to intent-level semantic relations |
| MAC-SQL (2023/2025) | Selector, decomposer, refiner agents | Single generator; specialised validation layer instead of more agents |
| TS-SQL (2025) | LLM-synthesised test data and test code for self-refinement | Test *relations* are derived deterministically from question intent and documented domain rules (no LLM-written oracle); applied to temporal per-entity semantics |
| SQLens (2025) | Fine-grained semantic error detection with database and LLM signals and weak supervision | Narrower, domain-configurable validator whose output is a training signal for prompt optimisation, evaluated by mutation testing |

TS-SQL and SQLens are the closest. Read both in full and state the difference precisely before claiming novelty. The claim is about the combination and its evaluation, not about any single ingredient.

## 6. What remains to be done

1. Run `run_experiments.py` with real models (at least two sizes), 3 repeats, all 7 methods; report EX, TRA, rule compliance, calls, error categories; McNemar tests.
2. Write a held-out set of 30–40 questions (by a teammate who did not write the rules) and re-run `eval_validator.py` and the LLM experiments on it.
3. Measure the validator's effect on the evaluator: how often it overturns a false PASS.
4. Prompt-level runs with `--carry` for RQ4.
5. Test portability: re-express the rules for a second temporal domain (e.g. equipment maintenance logs).
