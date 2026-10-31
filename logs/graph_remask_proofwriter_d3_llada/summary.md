# graph_remask_proofwriter_d3_llada

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 150

| | draft | after remasking |
|---|---|---|
| accuracy | 72.7% | 72.7% (+0.0%, 95% CI [-2.0%, +2.0%]) |
| reasoning consistency (no flagged step) | 70.0% | 77.3% |
| mean NFE | 256 | 292 (+36) |

fixed 1, broken 1 (exact McNemar p = 1.000)

- examples with a flagged step: 24 wrong, 21 right drafts
- no answer 0.0%, hit token limit 0.0%, 19.4 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 72.7% -> 72.7%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 53.3% of the time; 17 wrong drafts never flagged, 23 flagged but still wrong; flags by type {'contradiction': 5, 'false_premise': 3, 'unsupported': 37, 'unsupported_premise': 24, 'hallucinated_rule': 23, 'missed_inference': 3}
- tokens: draft 244, final 245, re-denoised 32 per problem
- time per problem: draft 17.1 s + refine 2.3 s + parse/verify 0.01 s = 19.4 s; peak GPU memory 15.2 GiB
- <= 12 steps (n=59): 81% -> 81% (fixed 1, broken 1)
- 13-16 steps (n=45): 69% -> 69% (fixed 0, broken 0)
- > 16 steps (n=46): 65% -> 65% (fixed 0, broken 0)
- remasked: 30.0% of examples, 1.69 rounds on average; 9 came back identical
- remask ratio |M|/L: 25.8% per round, 43.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 28.3%
