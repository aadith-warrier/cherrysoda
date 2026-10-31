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
