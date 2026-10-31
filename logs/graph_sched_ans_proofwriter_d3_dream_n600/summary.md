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
