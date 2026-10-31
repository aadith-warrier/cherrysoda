# Dream ProofWriter, main method + answer check + ban (2026-10-31 03:27:04), repo 8d79545

## dream n=300: design (0-149) vs held-out (150-299)

### design (proofwriter_d3_00000 .. proofwriter_d3_00149, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 41.3% | 41.3% | +0.0 [-2.7, +2.7] | 2 / 2 | 1.000 | - |
| graph+check+ban | 41.3% | 47.3% | +6.0 [-3.3, +16.0] | 33 / 24 | 0.289 | 66 / 63 / 32 / 22 |
| graph+sched+check+ban | 41.3% | 46.7% | +5.3 [-4.7, +14.7] | 34 / 26 | 0.366 | 75 / 64 / 24 / 22 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check+ban | 23 | 32 | -6.0 | 0.281 |
| graph vs graph+sched+check+ban | 26 | 34 | -5.3 | 0.366 |
| graph+check+ban vs graph+sched+check+ban | 16 | 15 | +0.7 | 1.000 |

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00299, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph | 42.7% | 42.7% | +0.0 [-4.0, +4.0] | 4 / 4 | 1.000 | - |
| graph+check+ban | 42.7% | 44.0% | +1.3 [-8.7, +10.7] | 30 / 28 | 0.896 | 75 / 71 / 29 / 27 |
| graph+sched+check+ban | 42.7% | 42.0% | -0.7 [-9.3, +8.7] | 23 / 24 | 1.000 | 80 / 73 / 20 / 23 |

| A vs B | A only right | B only right | gap A-B | McNemar p |
|---|---|---|---|---|
| graph vs graph+check+ban | 25 | 27 | -1.3 | 0.890 |
| graph vs graph+sched+check+ban | 26 | 25 | +0.7 | 1.000 |
| graph+check+ban vs graph+sched+check+ban | 15 | 12 | +2.0 | 0.701 |

## dream n=300: all
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


## dream n=300: model-free rule relabel vs graph+sched+check+ban
```
graph_sched_ans_proofwriter_d3_dream_n300: model-free rule relabel vs label ban

  design (n = 150): draft 41.3%
    rule relabel, no model : 52.7%  fixed 38 / broken 21  p 0.036  (64 answers relabelled)
    label ban (diffusion)  : 46.7%  fixed 34 / broken 26  p 0.366
    ban vs rule            : ban only right 12, rule only right 21, p 0.163
    one label banned (model chose)    :  39 problems, fixed 8, broken 9
    two labels banned (label forced)  :  35 problems, fixed 16, broken 12
    ban run's final label equals the rule's label in 43 of 75 banned problems

  held-out (n = 150): draft 42.7%
    rule relabel, no model : 50.0%  fixed 39 / broken 28  p 0.222  (73 answers relabelled)
    label ban (diffusion)  : 42.0%  fixed 23 / broken 24  p 1.000
    ban vs rule            : ban only right 10, rule only right 22, p 0.050
    one label banned (model chose)    :  38 problems, fixed 5, broken 8
    two labels banned (label forced)  :  40 problems, fixed 15, broken 15
    ban run's final label equals the rule's label in 36 of 80 banned problems

  all (n = 300): draft 42.0%
    rule relabel, no model : 51.3%  fixed 77 / broken 49  p 0.016  (137 answers relabelled)
    label ban (diffusion)  : 44.3%  fixed 57 / broken 50  p 0.562
    ban vs rule            : ban only right 22, rule only right 43, p 0.013
    one label banned (model chose)    :  77 problems, fixed 13, broken 17
    two labels banned (label forced)  :  75 problems, fixed 31, broken 27
    ban run's final label equals the rule's label in 79 of 155 banned problems
```

# graph_sched_ans_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 44.3% (+2.3%, 95% CI [-4.3%, +8.7%]) |
| reasoning consistency (no flagged step) | 20.7% | 52.7% |
| mean NFE | 256 | 449 (+193) |

fixed 57, broken 50 (exact McNemar p = 0.562)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 40.3%, hit token limit 2.0%, 25.1 s/problem
- answer format ('The answer is'): draft 74.0%, final 56.3%; accuracy among formatted 56.3% -> 75.7%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 97 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 183, re-denoised 233 per problem
- time per problem: draft 14.1 s + refine 11.0 s + parse/verify 0.30 s = 25.4 s; peak GPU memory 15.4 GiB
- <= 10 steps (n=102): 52% -> 42% (fixed 16, broken 26)
- 11-15 steps (n=103): 35% -> 43% (fixed 20, broken 12)
- > 15 steps (n=95): 39% -> 48% (fixed 21, broken 12)
- remasked: 79.3% of examples, 2.49 rounds on average; 13 came back identical
- remask ratio |M|/L: 62.3% per round, 154.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 63.4%
