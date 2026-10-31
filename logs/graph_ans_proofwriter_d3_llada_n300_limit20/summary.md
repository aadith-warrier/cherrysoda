# graph_ans_proofwriter_d3_llada_n300_limit20

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 20

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 75.0% (+5.0%, 95% CI [-20.0%, +30.0%]) |
| reasoning consistency (no flagged step) | 55.0% | 80.0% |
| mean NFE | 256 | 301 (+45) |

fixed 4, broken 3 (exact McNemar p = 1.000)

- examples with a flagged step: 4 wrong, 5 right drafts
- no answer 0.0%, hit token limit 0.0%, 21.1 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 70.0% -> 75.0%
- verifier in situ: graphs parsed cleanly 100.0%, 13.1 steps per answer; a flag means a wrong draft 44.4% of the time; 2 wrong drafts never flagged, 0 flagged but still wrong; flags by type {'contradiction': 1, 'false_premise': 1, 'unsupported_answer': 8, 'unsupported': 3, 'unsupported_premise': 2, 'hallucinated_rule': 2}
- tokens: draft 241, final 247, re-denoised 37 per problem
- time per problem: draft 18.0 s + refine 3.1 s + parse/verify 0.01 s = 21.1 s; peak GPU memory 14.9 GiB
- <= 10 steps (n=7): 71% -> 71% (fixed 2, broken 2)
- 11-15 steps (n=8): 75% -> 75% (fixed 1, broken 1)
- > 15 steps (n=5): 60% -> 80% (fixed 1, broken 0)
- remasked: 45.0% of examples, 2.00 rounds on average; 1 came back identical
- remask ratio |M|/L: 17.0% per round, 34.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 20.9%
