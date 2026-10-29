| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 74.0% (63.0%) | +11.0% [+5.0%, +17.0%] | 11 / 0 | 283 (+27) | 26 | 36.4% | 87.0% | 99.6 |
| graph+sched | 75.0% (63.0%) | +12.0% [+6.0%, +19.0%] | 12 / 0 | 281 (+25) | 27 | 37.2% | 87.0% | 99.2 |
| full-resample | 63.0% (63.0%) | +0.0% [-5.0%, +5.0%] | 3 / 3 | 448 (+192) | 191 | 267.9% | 78.0% | 142.3 |
| sched | 67.0% (63.0%) | +4.0% [-6.0%, +13.0%] | 14 / 10 | 359 (+103) | 256 | 100.0% | 69.0% | 118.9 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+sched | 0 | 1 | -1.0% [-3.0%, +0.0%] | 1.000 |
| graph vs full-resample | 13 | 2 | +11.0% [+4.0%, +18.0%] | 0.007 |
| graph vs sched | 15 | 8 | +7.0% [-2.0%, +16.0%] | 0.210 |
| graph+sched vs full-resample | 14 | 2 | +12.0% [+5.0%, +19.0%] | 0.004 |
| graph+sched vs sched | 16 | 8 | +8.0% [-1.0%, +18.0%] | 0.152 |
| full-resample vs sched | 11 | 15 | -4.0% [-14.0%, +6.0%] | 0.557 |
