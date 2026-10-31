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
