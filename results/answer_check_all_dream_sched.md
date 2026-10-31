| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 42.0% (42.0%) | +0.0% [-2.3%, +2.3%] | 6 / 6 | 583 (+327) | 280 | 197.4% | 43.3% | 32.9 |
| graph+check+ban | 45.7% (42.0%) | +3.7% [-3.3%, +10.3%] | 63 / 52 | 620 (+364) | 284 | 172.6% | 44.0% | 35.6 |
| graph+sched+check+ban | 44.3% (42.0%) | +2.3% [-4.3%, +8.7%] | 57 / 50 | 449 (+193) | 233 | 154.9% | 52.7% | 25.4 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+check+ban | 48 | 59 | -3.7% [-10.3%, +3.0%] | 0.334 |
| graph vs graph+sched+check+ban | 52 | 59 | -2.3% [-9.0%, +4.3%] | 0.569 |
| graph+check+ban vs graph+sched+check+ban | 31 | 27 | +1.3% [-3.3%, +6.0%] | 0.694 |
