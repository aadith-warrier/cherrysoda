
### design (proofwriter_d3_00000 .. proofwriter_d3_00149, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 72.7% | 72.7% | +0.0 [-2.0, +2.0] | 1 / 1 | 1.000 | - |
| graph+check | 72.7% | 74.0% | +1.3 [-1.3, +4.0] | 3 / 1 | 0.625 | - |
| graph+check+ban | 72.7% | 78.0% | +5.3 [-3.3, +13.3] | 26 / 18 | 0.291 | 54 / 47 / 26 / 18 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -1.3 | 0.500 |
| graph vs graph+check+ban | 18 | 26 | -5.3 | 0.291 |
| graph+check vs graph+check+ban | 18 | 24 | -4.0 | 0.441 |

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00599, n = 450)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 68.9% | 70.7% | +1.8 [+0.2, +3.1] | 10 / 2 | 0.039 | - |
| graph+check | 68.9% | 71.1% | +2.2 [+0.7, +3.8] | 12 / 2 | 0.013 | - |
| graph+check+ban | 68.9% | 79.6% | +10.7 [+5.8, +15.6] | 94 / 46 | 0.000 | 182 / 144 / 91 / 46 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -0.4 | 0.500 |
| graph vs graph+check+ban | 48 | 88 | -8.9 | 0.001 |
| graph+check vs graph+check+ban | 48 | 86 | -8.4 | 0.001 |
