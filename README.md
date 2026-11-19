# SeedSQL: TextGrad-Guided Text-to-SQL for Community Seed-Bank Analytics

Iterative prompt refinement for automated SQL query planning via TextGrad, applied to community
seed-bank viability and climate-resilience analytics.

**Research question:** does TextGrad-guided iterative prompt refinement improve Text-to-SQL execution
accuracy and refinement efficiency for seed-bank analytics, compared with static zero-shot and few-shot prompting?

```
question ─► [LLM generator ◄── prompt variable (requires_grad)] ─► SQL ─► SQLite (read-only) ─► rows / error
                       ▲                                                                  │
                       └── TGD step ◄── ∇ gradient (LLM) ◄── loss: LLM evaluator critique ◄┘
stop when: query executes AND evaluator verdict = PASS, or the iteration limit is reached
```

## Contents

| Path | What it is |
|---|---|
| `data/build_database.py` | Generates the synthetic seed-bank DB (5 tables, fixed seed 2026) |
| `data/seedbank.db`, `seedbank.sql` | The database (28 varieties, 82 lots, 200 germination tests, 2,674 storage logs, 104 distributions) |
| `data/benchmark.json` | 18 questions × 3 complexity tiers with gold SQL, plus 4 few-shot examples (not in the test set) |
| `seedsql/prompts.py` | All prompts: generator, loss (evaluator), gradient, TGD step, error-retry |
| `seedsql/db.py` | Read-only execution with a timeout, SQL extraction, execution-accuracy matching, error categories |
| `seedsql/methods.py` | Zero-shot, few-shot, error-retry (ablation), TextGrad loop |
| `seedsql/textgrad_lib.py` | The same loop built on the official `textgrad` package (`--methods textgrad_lib`) |
| `seedsql/llm.py` | Client for any OpenAI-compatible API (Groq, Gemini, OpenAI, Anthropic, Ollama) + offline mock |
| `run_experiments.py` | Runs the benchmark → `results/<run>/records.jsonl`, `summary.csv`, `summary.md`, `charts/*.png` |
| `app.py` | Local web platform: serves the interface and relays LLM calls (key stays on the server) |
| `ask.py` | Ask one question in the terminal and watch the refinement trace |
| `web/index.html` | Browser demo (SQLite runs in the browser; built by `web/build.py`) |
| `tests/test_eval.py` | Offline tests of the evaluation logic |

## Run the platform (web interface)

```cmd
set GROQ_API_KEY=gsk_...          &:: macOS/Linux: export GROQ_API_KEY=...
python app.py                     &:: opens http://localhost:8000 in your browser
```
Tabs: Ask the seed bank (live TextGrad trace) · Benchmark & evaluation (metrics + charts) · Database · Method.
Use `--provider gemini`, `--provider ollama --model qwen2.5-coder:7b`, or `--provider mock` (UI check only).

## Quick start (command line)

```bash
pip install -r requirements.txt           # core needs only matplotlib; textgrad/openai are optional
python -m tests.test_eval                 # offline checks (no API key needed)
python run_experiments.py --provider mock # offline pipeline smoke test (fake model, NOT real results)

# real runs: pick any provider (free tiers: Groq, Gemini; or local Ollama)
export GROQ_API_KEY=...                   # Windows: set GROQ_API_KEY=...
python ask.py "Which seed lots have a most recent germination rate below 75% and need retesting?" --provider groq
python run_experiments.py --provider groq --min-interval 2          # all 4 methods, all tiers
python run_experiments.py --provider gemini --model gemini-2.0-flash --repeats 3
python run_experiments.py --provider ollama --model qwen2.5-coder:7b
python run_experiments.py --provider openai --methods zero few textgrad textgrad_lib
python run_experiments.py --provider groq --methods textgrad --carry   # prompt-level optimisation
```

Smaller models make more SQL mistakes, which leaves room to measure refinement. A very strong model may score
near 100% zero-shot, and that is also a valid finding to report.

## Methods compared

| Method | Description | LLM calls / question |
|---|---|---|
| Zero-shot | instructions + schema + question | 1 |
| Few-shot | + 4 worked examples | 1 |
| Error-retry (ablation) | regenerate with the raw SQLite error until the query executes | 1–k |
| TextGrad | forward → loss → backward (gradient on the prompt) → TGD step, repeated | 2 if the first attempt passes, +4 per refinement |

TextGrad's first iteration uses exactly the zero-shot prompt, so any gain over zero-shot comes from refinement alone.
The loss **never sees the gold query**. It sees only the question, the schema, the SQL and the execution feedback.

## Metrics

- **Execution accuracy:** the final result matches the gold result (same row count; every gold column matched by a
  predicted column with equal values; row order, column order, aliases and extra columns ignored; numbers to 2 d.p.).
- **Successful query rate:** the final SQL executes without error.
- **Average refinement iterations:** generate→execute passes per question.
- **Error reduction:** error categories on the first attempt vs the final answer (syntax, unknown column/table,
  ambiguous column, aggregation misuse, other, wrong result, wrong-and-empty result).

## Query tiers

1. Single-table retrieval (e.g. *Which seed lots are stored in Cold Room A?*)
2. Filtering and aggregation (e.g. *Which 5 lots have the most out-of-range storage readings?*)
3. Multi-table joins and combined conditions (e.g. *Which highly drought-tolerant varieties have viable stock,
   i.e. a lot with quantity > 0 whose most recent germination rate ≥ 75%?*)

## Demo assumptions

Retest threshold 75% germination; recommended storage ≤ 15 °C and ≤ 50% RH; reference date 2026-11-01.
All data is synthetic. Variety names are common Karnataka landrace names, used only for realism.

## Limitations

Decision support only. The data is a small synthetic prototype. A query that executes can still be wrong (hence the gold
comparison). The LLM evaluator can reject correct queries or accept wrong ones. Novelty must be established by a
literature review, not assumed. Report the measured results, including cases where refinement does not help.

## References

- Nan et al. (2023). Enhancing Text-to-SQL Capabilities of LLMs: A Study on Prompt Design Strategies. Findings of EMNLP.
- Mao et al. (2024). DART-SQL: Question Rewriting and Execution-Guided Refinement. Findings of ACL.
- Yuksekgonul et al. (2024). TextGrad: Automatic "Differentiation" via Text. arXiv:2406.07496.
