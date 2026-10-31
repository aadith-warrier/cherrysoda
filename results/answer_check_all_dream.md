| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 42.0% (42.0%) | +0.0% [-2.3%, +2.3%] | 6 / 6 | 583 (+327) | 280 | 197.4% | 43.3% | 32.9 |
| graph+check | 42.7% (42.0%) | +0.7% [-1.7%, +3.0%] | 8 / 6 | 656 (+400) | 287 | 187.2% | 27.0% | 36.9 |
| graph+check+ban | 45.7% (42.0%) | +3.7% [-3.3%, +10.3%] | 63 / 52 | 620 (+364) | 284 | 172.6% | 44.0% | 35.6 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -0.7% [-1.7%, +0.0%] | 0.500 |
| graph vs graph+check+ban | 48 | 59 | -3.7% [-10.3%, +3.0%] | 0.334 |
| graph+check vs graph+check+ban | 49 | 58 | -3.0% [-9.7%, +3.7%] | 0.439 |
