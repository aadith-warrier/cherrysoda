# Dream ProofWriter, main method + answer check + ban, all 600 (2026-10-31 09:05:44), repo 01b5f7f

# graph_sched_ans_proofwriter_d3_dream_n600

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 44.0% | 44.3% (+0.3%, 95% CI [-4.5%, +5.2%]) |
| reasoning consistency (no flagged step) | 23.0% | 52.7% |
| mean NFE | 256 | 449 (+193) |

fixed 104, broken 102 (exact McNemar p = 0.944)

- examples with a flagged step: 289 wrong, 173 right drafts
- no answer 40.3%, hit token limit 2.8%, 25.1 s/problem
- answer format ('The answer is'): draft 70.8%, final 56.2%; accuracy among formatted 60.9% -> 75.4%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 62.6% of the time; 47 wrong drafts never flagged, 185 flagged but still wrong; flags by type {'unsupported': 428, 'unsupported_premise': 952, 'hallucinated_rule': 1037, 'unsupported_answer': 291, 'false_premise': 145, 'missed_inference': 14, 'contradiction': 97}
- tokens: draft 194, final 182, re-denoised 233 per problem
- time per problem: draft 14.1 s + refine 10.9 s + parse/verify 0.29 s = 25.4 s; peak GPU memory 15.6 GiB
- <= 11 steps (n=233): 55% -> 45% (fixed 40, broken 63)
- 12-15 steps (n=177): 41% -> 46% (fixed 29, broken 19)
- > 15 steps (n=190): 34% -> 42% (fixed 35, broken 20)
- remasked: 77.0% of examples, 2.49 rounds on average; 30 came back identical
- remask ratio |M|/L: 63.9% per round, 159.2% cumulative
- affected-subgraph ratio |A(B)|/|V|: 65.1%

## design (0-149) vs held-out (150-599)

### design (proofwriter_d3_00000 .. proofwriter_d3_00149, n = 150)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph+sched+check+ban | 41.3% | 46.7% | +5.3 [-4.7, +14.7] | 34 / 26 | 0.366 | 75 / 64 / 24 / 22 |

### held-out (proofwriter_d3_00150 .. proofwriter_d3_00599, n = 450)

| method | draft | final | Δ [95% CI] | fixed / broken | McNemar p | answer bans: lines / label changed / fixed / broken |
|---|---|---|---|---|---|---|
| graph+sched+check+ban | 44.9% | 43.6% | -1.3 [-6.7, +4.0] | 70 / 76 | 0.679 | 218 / 192 / 59 / 71 |

## model-free rule relabel vs the method
```
graph_sched_ans_proofwriter_d3_dream_n600: model-free rule relabel vs label ban

  design (n = 150): draft 41.3%
    rule relabel, no model : 52.7%  fixed 38 / broken 21  p 0.036  (64 answers relabelled)
    label ban (diffusion)  : 46.7%  fixed 34 / broken 26  p 0.366
    ban vs rule            : ban only right 12, rule only right 21, p 0.163
    one label banned (model chose)    :  39 problems, fixed 8, broken 9
    two labels banned (label forced)  :  35 problems, fixed 16, broken 12
    ban run's final label equals the rule's label in 43 of 75 banned problems

  held-out (n = 450): draft 44.9%
    rule relabel, no model : 49.6%  fixed 100 / broken 79  p 0.135  (192 answers relabelled)
    label ban (diffusion)  : 43.6%  fixed 70 / broken 76  p 0.679
    ban vs rule            : ban only right 25, rule only right 52, p 0.003
    one label banned (model chose)    : 104 problems, fixed 11, broken 32
    two labels banned (label forced)  : 111 problems, fixed 48, broken 38
    ban run's final label equals the rule's label in 111 of 218 banned problems

  all (n = 600): draft 44.0%
    rule relabel, no model : 50.3%  fixed 138 / broken 100  p 0.016  (256 answers relabelled)
    label ban (diffusion)  : 44.3%  fixed 104 / broken 102  p 0.944
    ban vs rule            : ban only right 37, rule only right 73, p 0.001
    one label banned (model chose)    : 143 problems, fixed 19, broken 41
    two labels banned (label forced)  : 146 problems, fixed 64, broken 50
    ban run's final label equals the rule's label in 154 of 293 banned problems
```
