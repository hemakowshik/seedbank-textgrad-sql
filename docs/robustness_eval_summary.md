# Temporal robustness and validator coverage (offline, no LLM)

Mutants that return exactly the gold answer on the benchmark database: 9
- diverge from gold on at least one of 5 changed states (hidden mistakes, counted correct by ordinary execution accuracy, rejected by TRA): **5** in 5 questions
- of these hidden mistakes, flagged by the gold-free validator: 4/5
- same answer on every changed state (no evidence of a mistake): 4

| Mistake type | Hidden mistakes |
|---|---|
| drop-date-bound | 4 |
| drop-no-retest | 1 |

Questions: T1-03, T3-04, TMP-10, TMP-11, TMP-14

Correct queries accepted by TRA: gold 60/60, correct rewrites 18/18

## Questions for which each question-dependent rule is activated by intent extraction

| Rule | Questions |
|---|---|
| AGG-COUNT | 13 |
| AGG-GROUP | 23 |
| DOM-STOCK | 6 |
| DOM-STORAGE | 5 |
| DOM-THRESHOLD | 14 |
| TEMP-LATEST | 18 |
| TEMP-NORETEST | 2 |
| TEMP-RANGE | 12 |

Metamorphic tests run on the gold queries: 28 in total; questions with at least one test: 14/60; mean validator time per query: 6 ms (static + metamorphic)

