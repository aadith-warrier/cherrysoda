# graph_ans_noban_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 71.8% (+2.0%, 95% CI [+0.7%, +3.5%]) |
| reasoning consistency (no flagged step) | 51.3% | 58.2% |
| mean NFE | 256 | 306 (+50) |

fixed 15, broken 3 (exact McNemar p = 0.008)

- examples with a flagged step: 153 wrong, 139 right drafts
- no answer 0.0%, hit token limit 0.0%, 20.6 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 69.8% -> 71.8%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 52.4% of the time; 28 wrong drafts never flagged, 138 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported_answer': 360, 'unsupported': 154, 'unsupported_premise': 69, 'hallucinated_rule': 55, 'missed_inference': 42}
- tokens: draft 241, final 244, re-denoised 44 per problem
- time per problem: draft 17.3 s + refine 3.4 s + parse/verify 0.01 s = 20.7 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 74% (fixed 9, broken 1)
- 13-16 steps (n=200): 68% -> 68% (fixed 2, broken 2)
- > 16 steps (n=177): 71% -> 73% (fixed 4, broken 0)
- remasked: 48.7% of examples, 1.70 rounds on average; 84 came back identical
- remask ratio |M|/L: 21.5% per round, 36.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 24.4%
