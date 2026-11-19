# Validator evaluation (offline, no LLM)

Gold queries: 60 · false alarms on gold: 0 (0%)

Correct rewrites in other SQL styles: 18 · false alarms: 0 (0%)

Wrong-but-executing mutants: 105 · detected by static rules: 104 (99%) · detected by static + metamorphic: 105 (100%)

| Mistake injected | Category | Mutants | Static rules | Static + metamorphic | Metamorphic tests fired |
|---|---|---|---|---|---|
| double-count-stock | domain | 2 | 100% | 100% | 0% |
| drop-date-bound | temporal | 1 | 100% | 100% | 100% |
| drop-group-by | aggregation | 21 | 100% | 100% | 0% |
| drop-latest | temporal | 14 | 100% | 100% | 57% |
| drop-no-retest | temporal | 1 | 100% | 100% | 100% |
| drop-stock | domain | 2 | 100% | 100% | 100% |
| earliest-not-latest | temporal | 15 | 100% | 100% | 47% |
| global-latest | temporal | 15 | 100% | 100% | 0% |
| or-to-and | domain | 3 | 100% | 100% | 33% |
| threshold-direction | domain | 7 | 86% | 100% | 71% |
| threshold-off-by-one | domain | 7 | 100% | 100% | 0% |
| wrong-join-key | join | 17 | 100% | 100% | 18% |

Missed mutants: 0

Note: the rules were developed on this benchmark, so these figures are optimistic. An independent question set is needed for an unbiased estimate.
