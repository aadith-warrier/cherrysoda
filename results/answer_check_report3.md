# ProofWriter: remaining rows (2026-10-31 02:17:52), repo 8d79545

## dream n=150: all four variants
| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 40.7% (41.3%) | -0.7% [-4.0%, +2.0%] | 2 / 3 | 593 (+337) | 288 | 207.3% | 43.3% | 33.0 |
| graph+sched | 43.3% (41.3%) | +2.0% [-3.3%, +7.3%] | 10 / 7 | 450 (+194) | 235 | 179.9% | 53.3% | 25.1 |
| sched | 39.3% (41.3%) | -2.0% [-10.7%, +7.3%] | 23 / 26 | 383 (+127) | 256 | 100.0% | 32.0% | 21.3 |
| full | 40.7% (41.3%) | -0.7% [-2.0%, +0.0%] | 0 / 1 | 732 (+476) | 412 | 300.0% | 38.0% | 40.5 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+sched | 7 | 11 | -2.7% [-8.0%, +2.7%] | 0.481 |
| graph vs sched | 26 | 24 | +1.3% [-8.0%, +10.0%] | 0.888 |
| graph vs full | 2 | 2 | +0.0% [-2.7%, +2.7%] | 1.000 |
| graph+sched vs sched | 27 | 21 | +4.0% [-5.3%, +12.7%] | 0.471 |
| graph+sched vs full | 11 | 7 | +2.7% [-2.7%, +8.7%] | 0.481 |
| sched vs full | 23 | 25 | -1.3% [-10.0%, +8.0%] | 0.885 |


## llada n=600: design (0-149) vs held-out (150-599)

### design (proofwriter_d3_00000 .. proofwriter_d3_00149, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 72.7% | 72.7% | +0.0 [-2.0, +2.0] | 1 / 1 | 1.000 | - |
| graph+check | 72.7% | 74.0% | +1.3 [-1.3, +4.0] | 3 / 1 | 0.625 | - |
| graph+check+ban | 72.7% | 78.0% | +5.3 [-3.3, +13.3] | 26 / 18 | 0.291 | 54 / 47 / 26 / 18 |
| graph+sched+check+ban | 72.7% | 74.7% | +2.0 [-6.0, +9.3] | 20 / 17 | 0.743 | 55 / 43 / 20 / 17 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -1.3 | 0.500 |
| graph vs graph+check+ban | 18 | 26 | -5.3 | 0.291 |
| graph vs graph+sched+check+ban | 17 | 20 | -2.0 | 0.743 |
| graph+check vs graph+check+ban | 18 | 24 | -4.0 | 0.441 |
| graph+check vs graph+sched+check+ban | 17 | 18 | -0.7 | 1.000 |
| graph+check+ban vs graph+sched+check+ban | 10 | 5 | +3.3 | 0.302 |

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00599, n = 450)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 68.9% | 70.7% | +1.8 [+0.2, +3.1] | 10 / 2 | 0.039 | - |
| graph+check | 68.9% | 71.1% | +2.2 [+0.7, +3.8] | 12 / 2 | 0.013 | - |
| graph+check+ban | 68.9% | 79.6% | +10.7 [+5.8, +15.6] | 94 / 46 | 0.000 | 182 / 144 / 91 / 46 |
| graph+sched+check+ban | 68.9% | 76.2% | +7.3 [+2.9, +11.8] | 76 / 43 | 0.003 | 180 / 125 / 75 / 43 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -0.4 | 0.500 |
| graph vs graph+check+ban | 48 | 88 | -8.9 | 0.001 |
| graph vs graph+sched+check+ban | 46 | 71 | -5.6 | 0.026 |
| graph+check vs graph+check+ban | 48 | 86 | -8.4 | 0.001 |
| graph+check vs graph+sched+check+ban | 46 | 69 | -5.1 | 0.040 |
| graph+check+ban vs graph+sched+check+ban | 33 | 18 | +3.3 | 0.049 |


## llada n=600: all
| method | acc (draft) | Δ vs draft [95% CI] | fixed / broken | NFE (+overhead) | tokens re-denoised | remask ratio | consistent after | s/problem |
|---|---|---|---|---|---|---|---|---|
| graph | 71.2% (69.8%) | +1.3% [+0.2%, +2.5%] | 11 / 3 | 292 (+36) | 34 | 46.1% | 78.2% | 19.7 |
| graph+check | 71.8% (69.8%) | +2.0% [+0.7%, +3.5%] | 15 / 3 | 306 (+50) | 44 | 36.6% | 58.2% | 20.7 |
| graph+check+ban | 79.2% (69.8%) | +9.3% [+5.2%, +13.5%] | 120 / 64 | 314 (+58) | 51 | 42.1% | 76.7% | 21.2 |
| graph+sched+check+ban | 75.8% (69.8%) | +6.0% [+2.0%, +10.0%] | 96 / 60 | 301 (+45) | 49 | 41.5% | 74.2% | 20.4 |

| A vs B | A only right | B only right | gap A-B [95% CI] | exact McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 4 | -0.7% [-1.3%, -0.2%] | 0.125 |
| graph vs graph+check+ban | 66 | 114 | -8.0% [-12.3%, -3.8%] | 0.000 |
| graph vs graph+sched+check+ban | 63 | 91 | -4.7% [-8.8%, -0.8%] | 0.029 |
| graph+check vs graph+check+ban | 66 | 110 | -7.3% [-11.7%, -3.2%] | 0.001 |
| graph+check vs graph+sched+check+ban | 63 | 87 | -4.0% [-8.0%, -0.2%] | 0.060 |
| graph+check+ban vs graph+sched+check+ban | 43 | 23 | +3.3% [+0.8%, +6.0%] | 0.019 |


## llada n=600: model-free rule relabel vs graph+sched+check+ban
```
graph_sched_ans_proofwriter_d3_llada_n600: model-free rule relabel vs label ban

  design (n = 150): draft 72.7%
    rule relabel, no model : 76.7%  fixed 26 / broken 20  p 0.461  (54 answers relabelled)
    label ban (diffusion)  : 74.7%  fixed 20 / broken 17  p 0.743
    ban vs rule            : ban only right 5, rule only right 8, p 0.581
    one label banned (model chose)    :  19 problems, fixed 6, broken 5
    two labels banned (label forced)  :  34 problems, fixed 14, broken 11
    ban run's final label equals the rule's label in 41 of 55 banned problems

  held-out (n = 450): draft 68.9%
    rule relabel, no model : 77.3%  fixed 98 / broken 60  p 0.003  (173 answers relabelled)
    label ban (diffusion)  : 76.2%  fixed 76 / broken 43  p 0.003
    ban vs rule            : ban only right 23, rule only right 28, p 0.576
    one label banned (model chose)    :  71 problems, fixed 29, broken 18
    two labels banned (label forced)  : 103 problems, fixed 45, broken 23
    ban run's final label equals the rule's label in 125 of 180 banned problems

  all (n = 600): draft 69.8%
    rule relabel, no model : 77.2%  fixed 124 / broken 80  p 0.003  (227 answers relabelled)
    label ban (diffusion)  : 75.8%  fixed 96 / broken 60  p 0.005
    ban vs rule            : ban only right 28, rule only right 36, p 0.382
    one label banned (model chose)    :  90 problems, fixed 35, broken 23
    two labels banned (label forced)  : 137 problems, fixed 59, broken 34
    ban run's final label equals the rule's label in 166 of 235 banned problems
```

## llada n=600: graph+sched+check+ban summary

# graph_sched_ans_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 75.8% (+6.0%, 95% CI [+2.0%, +10.0%]) |
| reasoning consistency (no flagged step) | 51.3% | 74.2% |
| mean NFE | 256 | 301 (+45) |

fixed 96, broken 60 (exact McNemar p = 0.005)

- examples with a flagged step: 153 wrong, 139 right drafts
- no answer 0.0%, hit token limit 0.0%, 20.4 s/problem
- answer format ('The answer is'): draft 100.0%, final 97.2%; accuracy among formatted 69.8% -> 77.7%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 52.4% of the time; 28 wrong drafts never flagged, 57 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported_answer': 360, 'unsupported': 154, 'unsupported_premise': 69, 'hallucinated_rule': 55, 'missed_inference': 42}
- tokens: draft 241, final 242, re-denoised 49 per problem
- time per problem: draft 17.3 s + refine 3.1 s + parse/verify 0.01 s = 20.4 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 71% (fixed 34, broken 33)
- 13-16 steps (n=200): 68% -> 78% (fixed 33, broken 13)
- > 16 steps (n=177): 71% -> 79% (fixed 29, broken 14)
- remasked: 48.7% of examples, 2.11 rounds on average; 13 came back identical
- remask ratio |M|/L: 19.7% per round, 41.5% cumulative
- affected-subgraph ratio |A(B)|/|V|: 23.0%
