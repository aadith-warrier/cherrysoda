# graph_remask_proofwriter_d3_llada_n300

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 71.0% (+1.0%, 95% CI [-0.7%, +2.7%]) |
| reasoning consistency (no flagged step) | 71.0% | 79.0% |
| mean NFE | 256 | 292 (+36) |

fixed 5, broken 2 (exact McNemar p = 0.453)

- examples with a flagged step: 52 wrong, 35 right drafts
- no answer 0.0%, hit token limit 0.0%, 19.5 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 70.0% -> 71.0%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 59.8% of the time; 38 wrong drafts never flagged, 47 flagged but still wrong; flags by type {'contradiction': 10, 'false_premise': 4, 'unsupported': 68, 'unsupported_premise': 37, 'hallucinated_rule': 31, 'missed_inference': 20}
- tokens: draft 244, final 245, re-denoised 33 per problem
- time per problem: draft 17.2 s + refine 2.3 s + parse/verify 0.01 s = 19.5 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=109): 70% -> 72% (fixed 4, broken 1)
- 13-16 steps (n=102): 72% -> 71% (fixed 0, broken 1)
- > 16 steps (n=89): 69% -> 70% (fixed 1, broken 0)
- remasked: 29.0% of examples, 1.68 rounds on average; 16 came back identical
- remask ratio |M|/L: 27.2% per round, 45.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 28.2%
