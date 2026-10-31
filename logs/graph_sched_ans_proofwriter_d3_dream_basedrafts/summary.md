# graph_sched_ans_proofwriter_d3_dream_basedrafts

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 44.3% | 40.7% (-3.7%, 95% CI [-8.3%, +0.8%]) |
| reasoning consistency (no flagged step) | 20.8% | 52.8% |
| mean NFE | 256 | 443 (+187) |

fixed 88, broken 110 (exact McNemar p = 0.135)

- examples with a flagged step: 297 wrong, 178 right drafts
- no answer 43.7%, hit token limit 2.8%, 31.6 s/problem
- answer format ('The answer is'): draft 71.7%, final 54.0%; accuracy among formatted 61.4% -> 73.1%
- verifier in situ: graphs parsed cleanly 100.0%, 12.1 steps per answer; a flag means a wrong draft 62.5% of the time; 37 wrong drafts never flagged, 209 flagged but still wrong; flags by type {'unsupported': 438, 'unsupported_premise': 928, 'hallucinated_rule': 1049, 'unsupported_answer': 285, 'false_premise': 176, 'missed_inference': 5, 'contradiction': 50}
- tokens: draft 197, final 182, re-denoised 234 per problem
- time per problem: draft 21.1 s + refine 10.5 s + parse/verify 0.28 s = 31.9 s; peak GPU memory 15.4 GiB
- <= 11 steps (n=210): 56% -> 43% (fixed 31, broken 58)
- 12-15 steps (n=199): 39% -> 41% (fixed 33, broken 29)
- > 15 steps (n=191): 37% -> 38% (fixed 24, broken 23)
- remasked: 79.2% of examples, 2.45 rounds on average; 21 came back identical
- remask ratio |M|/L: 61.8% per round, 151.5% cumulative
- affected-subgraph ratio |A(B)|/|V|: 63.6%
