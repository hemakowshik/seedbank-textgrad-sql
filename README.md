# SeedSQL: Intent-Conditioned Metamorphic Validation for Validation-Guided TextGrad Text-to-SQL

Seed-bank staff ask questions like *"Which lots have a most recent germination rate below 75%?"*. An LLM
writes the SQL. The hard errors are queries that **run and look plausible but are wrong**: they use every
test instead of the latest one, double-count distributed seed, or join on the wrong key. Execution
feedback cannot see these errors.

SeedSQL adds a **gold-free domain and temporal validator** and uses its evidence to drive **TextGrad**
prompt optimisation:

```
question ─► generator LLM (prompt p) ─► SQL ─► read-only SQLite ─► rows / error
                ▲                                     │
                │                     ┌───────────────┴───────────────────────────┐
                │                     │ Validator (no gold answer)                 │
                │                     │  1. intent from the question (no LLM)      │
                │                     │  2. configurable domain/temporal rules     │
                │                     │  3. metamorphic tests: change the database │
                │                     │     in a controlled way, re-run the SQL,   │
                │                     │     check the expected change in its output│
                │                     └───────────────┬───────────────────────────┘
                │                                     ▼ rule-tagged findings
   TGD step ◄── typed gradient [RULE-ID] ◄── LLM loss grounded in findings (validator can veto PASS)
```

Full rationale, research questions and positioning: [`docs/RESEARCH_DIRECTION.md`](docs/RESEARCH_DIRECTION.md).

## What is in the repository

| Path | What it is |
|---|---|
| `data/genesys_icrisat_IND002.csv` | **Real** ICRISAT genebank accession list from Genesys (149,034 accessions, with DOIs) |
| `data/build_real_database.py` | Builds the database: real accessions + simulated lots, tests, storage logs, distributions |
| `data/seedbank.db`, `seedbank.sql` | The database (66 real accessions in 11 crops, 122 lots, 294 tests, 4,004 readings, 152 distributions) |
| `data/benchmark.json` | **60 questions** (retrieval, aggregation, join, temporal, domain; 3 tiers) with verified gold SQL |
| `data/domain_rules.json` | Configurable thresholds, phrases and rules used by the validator |
| `data/equivalent_rewrites.json` | Correct queries in other SQL styles (false-alarm test set) |
| `seedsql/intent.py` | Deterministic question-intent extraction |
| `seedsql/validator.py` | Static rule checks + intent-conditioned metamorphic tests → structured findings |
| `seedsql/methods.py` | Zero-shot, few-shot, error-retry, TextGrad, Validator-retry, VG-TextGrad (static), **VG-TextGrad**; rule memory |
| `seedsql/perturb.py` | Changed database states for temporal robust accuracy (evaluation only) |
| `seedsql/mutants.py` | Injected semantic mistakes for evaluating the validator |
| `eval_validator.py` | Offline validator evaluation (no API key) → `results/validator_eval/` |
| `run_experiments.py` | LLM experiments → `results/<run>/summary.md`, `summary.csv`, `records.jsonl`, `charts/` |
| `app.py` | Local web platform with the validator (`/api/validate`) |
| `ask.py` | One question in the terminal with the full trace |
| `tests/` | Offline tests (`test_eval.py`, `test_validator.py`) |

## Quick start (Windows Command Prompt)

```cmd
cd /d C:\path\to\seedbank-textgrad-sql
python -m pip install matplotlib
python -m tests.test_eval
python -m tests.test_validator
python eval_validator.py
```

Put your key in a file named `.env` in the project folder (never commit it):
```
GROQ_API_KEY=gsk_...
```
Then:
```cmd
python app.py
python ask.py "Which seed lots have a most recent germination rate below 75% and need retesting?" --method vg_textgrad
python run_experiments.py --provider groq --min-interval 2
python run_experiments.py --provider groq --methods vg_retry vg_textgrad_static vg_textgrad --categories temporal domain
python run_experiments.py --provider groq --methods textgrad vg_textgrad --carry
```

## Metrics

| Metric | Meaning |
|---|---|
| Execution accuracy | Final result matches gold on the benchmark database |
| **Temporal robust accuracy** | Matches gold on the original database **and** on every changed state (new retests, stock changes, next year's records) |
| Rule compliance | No finding from the gold-free validator (partly circular for the VG methods; report with care) |
| Successful query rate | Final SQL executes |
| Avg. iterations, avg. LLM calls | Refinement effort and cost |
| Error categories | schema, join, temporal, domain, aggregation, first attempt vs final |

## Validator evaluation so far (offline, `python eval_validator.py`)

0 false alarms on 60 gold queries and 18 correct rewrites; 105 of 105 wrong-but-executing mutants detected
across 12 mistake types. **These are development-set figures**: the rules were refined on this benchmark,
so an independent held-out question set is needed before reporting them. LLM experiments have not been
run yet. See [`docs/validator_eval_summary.md`](docs/validator_eval_summary.md).

## Data honesty

- `SeedVariety` contains real ICRISAT accessions (accession number, DOI, crop from the verified ICRISAT prefix).
- Seed lots, germination tests, storage readings and distributions are **simulated** (fixed seed), because genebanks do not publish per-lot monitoring records.
- Drought tolerance is assigned by a crop-level rule. Thresholds (75% germination, 15 °C, 50% RH) are demonstration assumptions.
- `DATASET/icrisat_ind002_accessions.csv` (added in an earlier commit) **could not be verified**: none of its 144 accession numbers appear in ICRISAT's Genesys list. It is not used by the build.
- `SeedSQL_Complete_Project_Guide.pdf` describes the earlier 18-question version.

## References

Yuksekgonul et al., TextGrad (arXiv:2406.07496, 2024) · Nan et al., Findings of EMNLP 2023 · Mao et al., DART-SQL, Findings of ACL 2024 · Wang et al., MAC-SQL · Yu et al., Spider, EMNLP 2018 · Li et al., BIRD, NeurIPS 2023 · Genesys PGR (genesys-pgr.org). Verify TS-SQL and SQLens details from the full papers.
