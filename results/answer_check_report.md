# Answer-support check + label ban, ProofWriter depth 3, n = 300 (2026-10-30 21:22:08)
repo 8d79545

## llada: design half vs held-out half

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

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00299, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 67.3% | 69.3% | +2.0 [-0.7, +5.3] | 4 / 1 | 0.375 | - |
| graph+check | 67.3% | 70.0% | +2.7 [-0.7, +6.0] | 5 / 1 | 0.219 | - |
| graph+check+ban | 67.3% | 80.0% | +12.7 [+3.3, +22.0] | 34 / 15 | 0.009 | 56 / 49 / 32 / 15 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 1 | -0.7 | 1.000 |
| graph vs graph+check+ban | 15 | 31 | -10.7 | 0.026 |
| graph+check vs graph+check+ban | 15 | 30 | -10.0 | 0.036 |


## llada: all 300
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


## llada: error breakdown, graph+check+ban
```

=== graph_ans_proofwriter_d3_llada_n300  (n=300, draft 210/300 right, final 237/300)

1. Wrong drafts: gold -> predicted, flagged / not flagged
     False -> True     flagged   3   not flagged   0
     False -> Unknown  flagged   6   not flagged   4
      True -> False    flagged   7   not flagged   0
      True -> Unknown  flagged  12   not flagged  11
   Unknown -> False    flagged  35   not flagged   0
   Unknown -> True     flagged  12   not flagged   0
   total wrong 90: flagged 75, never flagged 15 (out of reach of any remasking)

2. Remasked examples: 141
   answer line inside round-1 A(B): 131/141
   tokens came back identical: 8/141
   predicted label changed: 98/141  -> {'fixed': 60, 'broken': 33, 'label unchanged': 43, 'wrong -> other wrong': 5}
   wrong drafts remasked: 75; label changed in 65, fixed 60

3. Flag precision by gold label (share of flagged drafts that were wrong)
      True: n=100 draft acc 70%  flagged  37 (wrong 19)  wrong never flagged 11
     False: n=100 draft acc 87%  flagged  45 (wrong 9)  wrong never flagged 4
   Unknown: n=100 draft acc 53%  flagged  59 (wrong 47)  wrong never flagged 0
```

## llada: graph_remask summary

# graph_remask_proofwriter_d3_llada_n300

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 71.0% (+1.0%, 95% CI [-0.7%, +2.7%]) |
| reasoning consistency (no flagged step) | 71.0% | 79.0% |
| mean NFE | 256 | 292 (+36) |

fixed 5, broken 2 (exact McNemar p = 0.453)

- examples with a flagged step: 52 wrong, 35 right drafts
- no answer 0.0%, hit token limit 0.0%, 19.5 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 70.0% -> 71.0%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 59.8% of the time; 38 wrong drafts never flagged, 47 flagged but still wrong; flags by type {'contradiction': 10, 'false_premise': 4, 'unsupported': 68, 'unsupported_premise': 37, 'hallucinated_rule': 31, 'missed_inference': 20}
- tokens: draft 244, final 245, re-denoised 33 per problem
- time per problem: draft 17.2 s + refine 2.3 s + parse/verify 0.01 s = 19.5 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=109): 70% -> 72% (fixed 4, broken 1)
- 13-16 steps (n=102): 72% -> 71% (fixed 0, broken 1)
- > 16 steps (n=89): 69% -> 70% (fixed 1, broken 0)
- remasked: 29.0% of examples, 1.68 rounds on average; 16 came back identical
- remask ratio |M|/L: 27.2% per round, 45.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 28.2%

## llada: graph_ans_noban summary

# graph_ans_noban_proofwriter_d3_llada_n300

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 72.0% (+2.0%, 95% CI [+0.0%, +4.0%]) |
| reasoning consistency (no flagged step) | 53.0% | 60.7% |
| mean NFE | 256 | 301 (+45) |

fixed 8, broken 2 (exact McNemar p = 0.109)

- examples with a flagged step: 75 wrong, 66 right drafts
- no answer 0.0%, hit token limit 0.0%, 20.2 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 70.0% -> 72.0%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 53.2% of the time; 15 wrong drafts never flagged, 67 flagged but still wrong; flags by type {'contradiction': 10, 'false_premise': 4, 'unsupported_answer': 174, 'unsupported': 66, 'unsupported_premise': 36, 'hallucinated_rule': 31, 'missed_inference': 19}
- tokens: draft 244, final 245, re-denoised 40 per problem
- time per problem: draft 17.2 s + refine 2.9 s + parse/verify 0.01 s = 20.2 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=109): 70% -> 73% (fixed 5, broken 1)
- 13-16 steps (n=102): 72% -> 72% (fixed 1, broken 1)
- > 16 steps (n=89): 69% -> 71% (fixed 2, broken 0)
- remasked: 47.0% of examples, 1.63 rounds on average; 42 came back identical
- remask ratio |M|/L: 21.2% per round, 34.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 23.8%

## llada: graph_ans summary

# graph_ans_proofwriter_d3_llada_n300

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 79.0% (+9.0%, 95% CI [+2.3%, +15.7%]) |
| reasoning consistency (no flagged step) | 53.0% | 77.3% |
| mean NFE | 256 | 308 (+52) |

fixed 60, broken 33 (exact McNemar p = 0.007)

- examples with a flagged step: 75 wrong, 66 right drafts
- no answer 0.0%, hit token limit 0.0%, 20.8 s/problem
- answer format ('The answer is'): draft 100.0%, final 98.3%; accuracy among formatted 70.0% -> 79.7%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 53.2% of the time; 15 wrong drafts never flagged, 15 flagged but still wrong; flags by type {'contradiction': 10, 'false_premise': 4, 'unsupported_answer': 174, 'unsupported': 66, 'unsupported_premise': 36, 'hallucinated_rule': 31, 'missed_inference': 19}
- tokens: draft 244, final 246, re-denoised 47 per problem
- time per problem: draft 17.2 s + refine 3.6 s + parse/verify 0.01 s = 20.8 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=109): 70% -> 70% (fixed 21, broken 21)
- 13-16 steps (n=102): 72% -> 85% (fixed 21, broken 7)
- > 16 steps (n=89): 69% -> 83% (fixed 18, broken 5)
- remasked: 47.0% of examples, 2.03 rounds on average; 8 came back identical
- remask ratio |M|/L: 19.8% per round, 40.1% cumulative
- affected-subgraph ratio |A(B)|/|V|: 22.7%

## dream: design half vs held-out half

### design (proofwriter_d3_00000 .. proofwriter_d3_00149, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 41.3% | 41.3% | +0.0 [-2.7, +2.7] | 2 / 2 | 1.000 | - |
| graph+check | 41.3% | 42.7% | +1.3 [-2.0, +4.7] | 4 / 2 | 0.688 | - |
| graph+check+ban | 41.3% | 47.3% | +6.0 [-3.3, +16.0] | 33 / 24 | 0.289 | 66 / 63 / 32 / 22 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 2 | -1.3 | 0.500 |
| graph vs graph+check+ban | 23 | 32 | -6.0 | 0.281 |
| graph+check vs graph+check+ban | 24 | 31 | -4.7 | 0.419 |

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00299, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 42.7% | 42.7% | +0.0 [-4.0, +4.0] | 4 / 4 | 1.000 | - |
| graph+check | 42.7% | 42.7% | +0.0 [-4.0, +4.0] | 4 / 4 | 1.000 | - |
| graph+check+ban | 42.7% | 44.0% | +1.3 [-8.7, +10.7] | 30 / 28 | 0.896 | 75 / 71 / 29 / 27 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check | 0 | 0 | +0.0 | 1.000 |
| graph vs graph+check+ban | 25 | 27 | -1.3 | 0.890 |
| graph+check vs graph+check+ban | 25 | 27 | -1.3 | 0.890 |


## dream: all 300
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


## dream: error breakdown, graph+check+ban
```
Traceback (most recent call last):
  File "/scratch2/rtarun1/stuff/cherrysoda/.pixi/envs/default/lib/python3.10/runpy.py", line 196, in _run_module_as_main
    return _run_code(code, main_globals, None,
  File "/scratch2/rtarun1/stuff/cherrysoda/.pixi/envs/default/lib/python3.10/runpy.py", line 86, in _run_code
    exec(code, run_globals)
  File "/scratch2/rtarun1/stuff/cherrysoda/scripts/analyze_proofwriter_remask.py", line 86, in <module>
    report(d)
  File "/scratch2/rtarun1/stuff/cherrysoda/scripts/analyze_proofwriter_remask.py", line 48, in report
    pairs = sorted({(g, p) for g, p, _ in conf})
TypeError: '<' not supported between instances of 'str' and 'NoneType'

=== graph_ans_proofwriter_d3_dream_n300  (n=300, draft 126/300 right, final 137/300)

1. Wrong drafts: gold -> predicted, flagged / not flagged
```

## dream: graph_remask summary

# graph_remask_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 42.0% (+0.0%, 95% CI [-2.3%, +2.3%]) |
| reasoning consistency (no flagged step) | 36.7% | 43.3% |
| mean NFE | 256 | 583 (+327) |

fixed 6, broken 6 (exact McNemar p = 1.000)

- examples with a flagged step: 131 wrong, 59 right drafts
- no answer 29.0%, hit token limit 2.3%, 32.6 s/problem
- answer format ('The answer is'): draft 74.0%, final 69.7%; accuracy among formatted 56.3% -> 58.9%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 68.9% of the time; 43 wrong drafts never flagged, 125 flagged but still wrong; flags by type {'unsupported': 218, 'unsupported_premise': 500, 'hallucinated_rule': 440, 'false_premise': 73, 'missed_inference': 15, 'contradiction': 43}
- tokens: draft 195, final 200, re-denoised 280 per problem
- time per problem: draft 14.1 s + refine 18.5 s + parse/verify 0.31 s = 32.9 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 51% (fixed 2, broken 3)
- 11-15 steps (n=103): 35% -> 37% (fixed 4, broken 2)
- > 15 steps (n=95): 39% -> 38% (fixed 0, broken 1)
- remasked: 63.3% of examples, 2.81 rounds on average; 94 came back identical
- remask ratio |M|/L: 70.2% per round, 197.4% cumulative
- affected-subgraph ratio |A(B)|/|V|: 70.5%

## dream: graph_ans_noban summary

# graph_ans_noban_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 42.7% (+0.7%, 95% CI [-1.7%, +3.0%]) |
| reasoning consistency (no flagged step) | 20.7% | 27.0% |
| mean NFE | 256 | 656 (+400) |

fixed 8, broken 6 (exact McNemar p = 0.791)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 29.3%, hit token limit 2.0%, 36.6 s/problem
- answer format ('The answer is'): draft 74.0%, final 69.3%; accuracy among formatted 56.3% -> 60.1%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 146 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 201, re-denoised 287 per problem
- time per problem: draft 14.1 s + refine 22.4 s + parse/verify 0.34 s = 36.9 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 53% (fixed 4, broken 3)
- 11-15 steps (n=103): 35% -> 37% (fixed 4, broken 2)
- > 15 steps (n=95): 39% -> 38% (fixed 0, broken 1)
- remasked: 79.3% of examples, 2.86 rounds on average; 132 came back identical
- remask ratio |M|/L: 65.4% per round, 187.2% cumulative
- affected-subgraph ratio |A(B)|/|V|: 66.7%

## dream: graph_ans summary

# graph_ans_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 45.7% (+3.7%, 95% CI [-3.3%, +10.3%]) |
| reasoning consistency (no flagged step) | 20.7% | 44.0% |
| mean NFE | 256 | 620 (+364) |

fixed 63, broken 52 (exact McNemar p = 0.351)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 33.3%, hit token limit 2.0%, 35.2 s/problem
- answer format ('The answer is'): draft 74.0%, final 65.0%; accuracy among formatted 56.3% -> 68.7%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 91 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 202, re-denoised 284 per problem
- time per problem: draft 14.1 s + refine 21.1 s + parse/verify 0.33 s = 35.6 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 52% (fixed 25, broken 25)
- 11-15 steps (n=103): 35% -> 45% (fixed 23, broken 13)
- > 15 steps (n=95): 39% -> 40% (fixed 15, broken 14)
- remasked: 79.3% of examples, 2.60 rounds on average; 48 came back identical
- remask ratio |M|/L: 66.3% per round, 172.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 67.3%
