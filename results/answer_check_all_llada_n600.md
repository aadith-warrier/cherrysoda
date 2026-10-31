| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 71.2% (69.8%) | +1.3% [+0.2%, +2.5%] | 11 / 3 | 292 (+36) | 34 | 46.1% | 78.2% | 19.7 |
| graph+check | 71.8% (69.8%) | +2.0% [+0.7%, +3.5%] | 15 / 3 | 306 (+50) | 44 | 36.6% | 58.2% | 20.7 |
| graph+check+ban | 79.2% (69.8%) | +9.3% [+5.2%, +13.5%] | 120 / 64 | 314 (+58) | 51 | 42.1% | 76.7% | 21.2 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 4 | -0.7% [-1.3%, -0.2%] | 0.125 |
| graph vs graph+check+ban | 66 | 114 | -8.0% [-12.3%, -3.8%] | 0.000 |
| graph+check vs graph+check+ban | 66 | 110 | -7.3% [-11.7%, -3.2%] | 0.001 |
