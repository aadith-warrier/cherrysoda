| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 72.7% (72.7%) | +0.0% [-2.0%, +2.0%] | 1 / 1 | 292 (+36) | 32 | 43.6% | 77.3% | 19.4 |
| graph+sched | 73.3% (72.7%) | +0.7% [-1.3%, +3.3%] | 2 / 1 | 288 (+32) | 37 | 50.2% | 77.3% | 19.2 |
| sched | 59.3% (72.7%) | -13.3% [-22.7%, -4.0%] | 16 / 36 | 334 (+78) | 256 | 100.0% | 20.0% | 22.3 |
| full | 72.7% (72.7%) | +0.0% [-3.3%, +3.3%] | 4 / 4 | 382 (+126) | 122 | 164.4% | 80.7% | 25.4 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+sched | 0 | 1 | -0.7% [-2.0%, +0.0%] | 1.000 |
| graph vs sched | 36 | 16 | +13.3% [+4.0%, +23.3%] | 0.008 |
| graph vs full | 4 | 4 | +0.0% [-4.0%, +4.0%] | 1.000 |
| graph+sched vs sched | 37 | 16 | +14.0% [+4.7%, +24.0%] | 0.005 |
| graph+sched vs full | 5 | 4 | +0.7% [-3.3%, +4.7%] | 1.000 |
| sched vs full | 15 | 35 | -13.3% [-22.7%, -4.7%] | 0.007 |
