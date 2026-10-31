| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 71.0% (70.0%) | +1.0% [-0.7%, +2.7%] | 5 / 2 | 292 (+36) | 33 | 45.6% | 79.0% | 19.5 |
| graph+check | 72.0% (70.0%) | +2.0% [+0.0%, +4.0%] | 8 / 2 | 301 (+45) | 40 | 34.6% | 60.7% | 20.2 |
| graph+check+ban | 79.0% (70.0%) | +9.0% [+2.3%, +15.7%] | 60 / 33 | 308 (+52) | 47 | 40.1% | 77.3% | 20.8 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 3 | -1.0% [-2.3%, +0.0%] | 0.250 |
| graph vs graph+check+ban | 33 | 57 | -8.0% [-14.7%, -1.7%] | 0.015 |
| graph+check vs graph+check+ban | 33 | 54 | -7.0% [-13.3%, -0.7%] | 0.031 |
