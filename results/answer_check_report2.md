# Answer check follow-up (2026-10-30 21:53:36), repo 8d79545

## llada n=300: model-free rule relabel vs label ban
```
graph_ans_proofwriter_d3_llada_n300: model-free rule relabel vs label ban

  design (n = 150): draft 72.7%
    rule relabel, no model : 76.7%  fixed 26 / broken 20  p 0.461  (54 answers relabelled)
    label ban (diffusion)  : 78.0%  fixed 26 / broken 18  p 0.291
    ban vs rule            : ban only right 3, rule only right 1, p 0.625
    one label banned (model chose)    :  13 problems, fixed 6, broken 3
    two labels banned (label forced)  :  38 problems, fixed 19, broken 13
    ban run's final label equals the rule's label in 50 of 54 banned problems

  held-out (n = 150): draft 67.3%
    rule relabel, no model : 76.7%  fixed 32 / broken 18  p 0.065  (53 answers relabelled)
    label ban (diffusion)  : 80.0%  fixed 34 / broken 15  p 0.009
    ban vs rule            : ban only right 6, rule only right 1, p 0.125
    one label banned (model chose)    :  16 problems, fixed 10, broken 2
    two labels banned (label forced)  :  38 problems, fixed 21, broken 13
    ban run's final label equals the rule's label in 50 of 56 banned problems

  all (n = 300): draft 70.0%
    rule relabel, no model : 76.7%  fixed 58 / broken 38  p 0.052  (107 answers relabelled)
    label ban (diffusion)  : 79.0%  fixed 60 / broken 33  p 0.007
    ban vs rule            : ban only right 9, rule only right 2, p 0.065
    one label banned (model chose)    :  29 problems, fixed 16, broken 5
    two labels banned (label forced)  :  76 problems, fixed 40, broken 26
    ban run's final label equals the rule's label in 100 of 110 banned problems
```

## dream n=300: model-free rule relabel vs label ban
```
graph_ans_proofwriter_d3_dream_n300: model-free rule relabel vs label ban

  design (n = 150): draft 41.3%
    rule relabel, no model : 52.7%  fixed 38 / broken 21  p 0.036  (64 answers relabelled)
    label ban (diffusion)  : 47.3%  fixed 33 / broken 24  p 0.289
    ban vs rule            : ban only right 1, rule only right 9, p 0.021
    one label banned (model chose)    :  15 problems, fixed 8, broken 4
    two labels banned (label forced)  :  49 problems, fixed 24, broken 16
    ban run's final label equals the rule's label in 55 of 66 banned problems

  held-out (n = 150): draft 42.7%
    rule relabel, no model : 50.0%  fixed 39 / broken 28  p 0.222  (73 answers relabelled)
    label ban (diffusion)  : 44.0%  fixed 30 / broken 28  p 0.896
    ban vs rule            : ban only right 3, rule only right 12, p 0.035
    one label banned (model chose)    :  24 problems, fixed 7, broken 7
    two labels banned (label forced)  :  49 problems, fixed 22, broken 20
    ban run's final label equals the rule's label in 56 of 75 banned problems

  all (n = 300): draft 42.0%
    rule relabel, no model : 51.3%  fixed 77 / broken 49  p 0.016  (137 answers relabelled)
    label ban (diffusion)  : 45.7%  fixed 63 / broken 52  p 0.351
    ban vs rule            : ban only right 4, rule only right 21, p 0.001
    one label banned (model chose)    :  39 problems, fixed 15, broken 11
    two labels banned (label forced)  :  98 problems, fixed 46, broken 36
    ban run's final label equals the rule's label in 111 of 141 banned problems
```

## dream n=300: error breakdown, graph+check+ban
```

=== graph_ans_proofwriter_d3_dream_n300  (n=300, draft 126/300 right, final 137/300)

1. Wrong drafts: gold -> predicted, flagged / not flagged
     False -> None     flagged  22   not flagged   5
     False -> True     flagged   8   not flagged   0
     False -> Unknown  flagged   4   not flagged   0
      True -> False    flagged   7   not flagged   0
      True -> None     flagged  19   not flagged   7
      True -> Unknown  flagged   4   not flagged   1
   Unknown -> False    flagged  38   not flagged   0
   Unknown -> None     flagged  17   not flagged   7
   Unknown -> True     flagged  35   not flagged   0
   total wrong 174: flagged 154, never flagged 20 (out of reach of any remasking)

2. Remasked examples: 238
   answer line inside round-1 A(B): 166/238
   tokens came back identical: 48/238
   predicted label changed: 139/238  -> {'label unchanged': 99, 'fixed': 63, 'broken': 52, 'wrong -> other wrong': 24}
   wrong drafts remasked: 154; label changed in 87, fixed 63

3. Flag precision by gold label (share of flagged drafts that were wrong)
      True: n=100 draft acc 62%  flagged  70 (wrong 30)  wrong never flagged 8
     False: n=100 draft acc 61%  flagged  77 (wrong 34)  wrong never flagged 5
   Unknown: n=100 draft acc 3%  flagged  91 (wrong 90)  wrong never flagged 7
```

## llada n=600: design half (0-149) vs held-out (150-599)

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


## llada n=600: all
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


## llada n=600: model-free rule relabel vs label ban
```
graph_ans_proofwriter_d3_llada_n600: model-free rule relabel vs label ban

  design (n = 150): draft 72.7%
    rule relabel, no model : 76.7%  fixed 26 / broken 20  p 0.461  (54 answers relabelled)
    label ban (diffusion)  : 78.0%  fixed 26 / broken 18  p 0.291
    ban vs rule            : ban only right 3, rule only right 1, p 0.625
    one label banned (model chose)    :  13 problems, fixed 6, broken 3
    two labels banned (label forced)  :  38 problems, fixed 19, broken 13
    ban run's final label equals the rule's label in 50 of 54 banned problems

  held-out (n = 450): draft 68.9%
    rule relabel, no model : 77.3%  fixed 98 / broken 60  p 0.003  (173 answers relabelled)
    label ban (diffusion)  : 79.6%  fixed 94 / broken 46  p 0.000
    ban vs rule            : ban only right 19, rule only right 9, p 0.087
    one label banned (model chose)    :  45 problems, fixed 23, broken 4
    two labels banned (label forced)  : 122 problems, fixed 67, broken 37
    ban run's final label equals the rule's label in 155 of 182 banned problems

  all (n = 600): draft 69.8%
    rule relabel, no model : 77.2%  fixed 124 / broken 80  p 0.003  (227 answers relabelled)
    label ban (diffusion)  : 79.2%  fixed 120 / broken 64  p 0.000
    ban vs rule            : ban only right 22, rule only right 10, p 0.050
    one label banned (model chose)    :  58 problems, fixed 29, broken 7
    two labels banned (label forced)  : 160 problems, fixed 86, broken 50
    ban run's final label equals the rule's label in 205 of 236 banned problems
```

## llada n=600: error breakdown, graph+check+ban
```

=== graph_ans_proofwriter_d3_llada_n600  (n=600, draft 419/600 right, final 475/600)

1. Wrong drafts: gold -> predicted, flagged / not flagged
     False -> True     flagged   3   not flagged   0
     False -> Unknown  flagged  12   not flagged  10
      True -> False    flagged  10   not flagged   0
      True -> Unknown  flagged  29   not flagged  18
   Unknown -> False    flagged  63   not flagged   0
   Unknown -> True     flagged  36   not flagged   0
   total wrong 181: flagged 153, never flagged 28 (out of reach of any remasking)

2. Remasked examples: 292
   answer line inside round-1 A(B): 269/292
   tokens came back identical: 13/292
   predicted label changed: 194/292  -> {'fixed': 120, 'broken': 64, 'label unchanged': 98, 'wrong -> other wrong': 10}
   wrong drafts remasked: 153; label changed in 130, fixed 120

3. Flag precision by gold label (share of flagged drafts that were wrong)
      True: n=200 draft acc 72%  flagged  81 (wrong 39)  wrong never flagged 18
     False: n=200 draft acc 88%  flagged  93 (wrong 15)  wrong never flagged 10
   Unknown: n=200 draft acc 50%  flagged 118 (wrong 99)  wrong never flagged 0
```

## llada n=600: graph_ans summary

# graph_ans_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 79.2% (+9.3%, 95% CI [+5.2%, +13.5%]) |
| reasoning consistency (no flagged step) | 51.3% | 76.7% |
| mean NFE | 256 | 314 (+58) |

fixed 120, broken 64 (exact McNemar p = 0.000)

- examples with a flagged step: 153 wrong, 139 right drafts
- no answer 0.0%, hit token limit 0.0%, 21.2 s/problem
- answer format ('The answer is'): draft 100.0%, final 98.3%; accuracy among formatted 69.8% -> 80.2%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 52.4% of the time; 28 wrong drafts never flagged, 33 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported_answer': 360, 'unsupported': 154, 'unsupported_premise': 69, 'hallucinated_rule': 55, 'missed_inference': 42}
- tokens: draft 241, final 245, re-denoised 51 per problem
- time per problem: draft 17.3 s + refine 3.9 s + parse/verify 0.01 s = 21.2 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 74% (fixed 44, broken 38)
- 13-16 steps (n=200): 68% -> 83% (fixed 44, broken 14)
- > 16 steps (n=177): 71% -> 82% (fixed 32, broken 12)
- remasked: 48.7% of examples, 2.12 rounds on average; 13 came back identical
- remask ratio |M|/L: 19.8% per round, 42.1% cumulative
- affected-subgraph ratio |A(B)|/|V|: 22.9%
