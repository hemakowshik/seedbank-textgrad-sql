# Statistics for 20261119-150823_groq_openai-gpt-oss-20b

Model(s) used: openai/gpt-oss-20b · repeats: 1 · questions: 8

## Accuracy with 95% confidence intervals

| Method | n | Exec. accuracy [95% CI] | Temporal robust acc. [95% CI] | Rule compliance | First-attempt acc. | Avg. LLM calls | Exec. acc. mean ± sd over repeats |
|---|---|---|---|---|---|---|---|
| Zero-shot | 8 | 87.5% [52.9, 97.8] | 87.5% [52.9, 97.8] | 100.0% | 87.5% | 1.0 | single run |
| TextGrad | 8 | 87.5% [52.9, 97.8] | 87.5% [52.9, 97.8] | 100.0% | 75.0% | 2.5 | single run |
| Validator-retry | 8 | 87.5% [52.9, 97.8] | 87.5% [52.9, 97.8] | 100.0% | 87.5% | 1.0 | single run |
| VG-TextGrad | 8 | 87.5% [52.9, 97.8] | 87.5% [52.9, 97.8] | 100.0% | 87.5% | 2.0 | single run |

## Paired comparison on execution accuracy (exact McNemar test, Holm-corrected)

| A vs B | paired items | only A right | only B right | p | p (Holm) | significant at 0.05 |
|---|---|---|---|---|---|---|
| VG-TextGrad vs TextGrad | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| VG-TextGrad vs Validator-retry | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| VG-TextGrad vs Zero-shot | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| TextGrad vs Zero-shot | 8 | 0 | 0 | 1.0000 | 1.0000 | no |

## Paired comparison on temporal robust accuracy (exact McNemar test, Holm-corrected)

| A vs B | paired items | only A right | only B right | p | p (Holm) | significant at 0.05 |
|---|---|---|---|---|---|---|
| VG-TextGrad vs TextGrad | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| VG-TextGrad vs Validator-retry | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| VG-TextGrad vs Zero-shot | 8 | 0 | 0 | 1.0000 | 1.0000 | no |
| TextGrad vs Zero-shot | 8 | 0 | 0 | 1.0000 | 1.0000 | no |

## Execution accuracy by question category

| Method | domain |
|---|---|
| Zero-shot | 87.5% (8) |
| TextGrad | 87.5% (8) |
| Validator-retry | 87.5% (8) |
| VG-TextGrad | 87.5% (8) |
