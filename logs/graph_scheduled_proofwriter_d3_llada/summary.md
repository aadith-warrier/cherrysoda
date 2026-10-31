# graph_scheduled_proofwriter_d3_llada

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 150

| | draft | after remasking |
|---|---|---|
| accuracy | 72.7% | 73.3% (+0.7%, 95% CI [-1.3%, +3.3%]) |
| reasoning consistency (no flagged step) | 70.0% | 77.3% |
| mean NFE | 256 | 288 (+32) |

fixed 2, broken 1 (exact McNemar p = 1.000)

- examples with a flagged step: 24 wrong, 21 right drafts
- no answer 0.0%, hit token limit 0.0%, 19.2 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 72.7% -> 73.3%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 53.3% of the time; 17 wrong drafts never flagged, 22 flagged but still wrong; flags by type {'contradiction': 5, 'false_premise': 3, 'unsupported': 37, 'unsupported_premise': 24, 'hallucinated_rule': 23, 'missed_inference': 3}
- tokens: draft 244, final 245, re-denoised 37 per problem
- time per problem: draft 17.1 s + refine 2.1 s + parse/verify 0.01 s = 19.2 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=59): 81% -> 81% (fixed 1, broken 1)
- 13-16 steps (n=45): 69% -> 71% (fixed 1, broken 0)
- > 16 steps (n=46): 65% -> 65% (fixed 0, broken 0)
- remasked: 30.0% of examples, 1.84 rounds on average; 9 came back identical
- remask ratio |M|/L: 27.2% per round, 50.2% cumulative
- affected-subgraph ratio |A(B)|/|V|: 29.5%
