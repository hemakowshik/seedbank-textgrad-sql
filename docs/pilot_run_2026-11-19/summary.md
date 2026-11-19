# Results: groq / openai/gpt-oss-20b

Questions per run: 8 · repeats: 1 · max iterations: 4 · carry prompt: False

Exec. accuracy = final result matches gold on the benchmark database. Temporal robust accuracy = matches gold on the original AND on every changed database state. Rule compliance = no finding from the gold-free validator (for the VG methods this is partly circular, because they were optimised against it).

| Method | Tier / category | n | Exec. accuracy | Temporal robust acc. | Rule compliance | Successful query rate | Avg. iterations | Avg. LLM calls | First-attempt acc. | Errors first→final |
|---|---|---|---|---|---|---|---|---|---|---|
| Zero-shot | all | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| Zero-shot | 3 | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| Zero-shot | domain | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| TextGrad | all | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.12 | 2.5 | 75.0% | 2→1 |
| TextGrad | 3 | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.12 | 2.5 | 75.0% | 2→1 |
| TextGrad | domain | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.12 | 2.5 | 75.0% | 2→1 |
| Validator-retry | all | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| Validator-retry | 3 | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| Validator-retry | domain | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 1.0 | 87.5% | 1→1 |
| VG-TextGrad | all | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 2.0 | 87.5% | 1→1 |
| VG-TextGrad | 3 | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 2.0 | 87.5% | 1→1 |
| VG-TextGrad | domain | 8 | 87.5% | 87.5% | 100.0% | 100.0% | 1.00 | 2.0 | 87.5% | 1→1 |

## Remaining semantic issues in final answers (gold-free validator, by category)

| Method | schema | join | temporal | domain | aggregation | execution |
|---|---|---|---|---|---|---|
| Zero-shot | 0 | 0 | 0 | 0 | 0 | 0 |
| TextGrad | 0 | 0 | 0 | 0 | 0 | 0 |
| Validator-retry | 0 | 0 | 0 | 0 | 0 | 0 |
| VG-TextGrad | 0 | 0 | 0 | 0 | 0 | 0 |

## Error categories (first attempt → final answer)

| Method | Syntax error | Unknown column | Unknown table | Ambiguous column | Aggregation misuse | Other execution error | Invalid / non-SELECT | Wrong result | Wrong result (empty) |
|---|---|---|---|---|---|---|---|---|---|
| Zero-shot | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 1→1 | 0→0 |
| TextGrad | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 2→1 | 0→0 |
| Validator-retry | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 1→1 | 0→0 |
| VG-TextGrad | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 0→0 | 1→1 | 0→0 |

## Per-question outcome (✓ correct · ✗ wrong result · E execution error)

| Question | Tier | Zero-shot | TextGrad | Validator-retry | VG-TextGrad |
|---|---|---|---|---|---|
| DOM-02 | 3 | ✓ | ✓ | ✓ | ✓ |
| DOM-03 | 3 | ✓ | ✓ | ✓ | ✓ |
| DOM-04 | 3 | ✓ | ✓(2) | ✓ | ✓ |
| DOM-08 | 3 | ✓ | ✓ | ✓ | ✓ |
| DOM-10 | 3 | ✓ | ✓ | ✓ | ✓ |
| DOM-11 | 3 | ✗ | ✗ | ✗ | ✗ |
| DOM-12 | 3 | ✓ | ✓ | ✓ | ✓ |
| T3-02 | 3 | ✓ | ✓ | ✓ | ✓ |
