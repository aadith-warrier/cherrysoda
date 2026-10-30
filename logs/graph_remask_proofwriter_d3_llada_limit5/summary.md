# graph_remask_proofwriter_d3_llada_limit5

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 5

| | draft | after remasking |
|---|---|---|
| accuracy | 60.0% | 80.0% (+20.0%, 95% CI [+0.0%, +60.0%]) |
| reasoning consistency (no flagged step) | 60.0% | 80.0% |
| mean NFE | 256 | 328 (+72) |

fixed 1, broken 0 (exact McNemar p = 1.000)

- examples with a flagged step: 2 wrong, 0 right drafts
- no answer 0.0%, hit token limit 0.0%, 23.4 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 60.0% -> 80.0%
- verifier in situ: graphs parsed cleanly 100.0%, 9.8 steps per answer; a flag means a wrong draft 100.0% of the time; 0 wrong drafts never flagged, 1 flagged but still wrong; flags by type {'contradiction': 1, 'false_premise': 1, 'unsupported': 1}
- tokens: draft 225, final 234, re-denoised 29 per problem
- time per problem: draft 18.2 s + refine 5.3 s + parse/verify 0.01 s = 23.5 s; peak GPU memory 15.2 GiB
- <= 9 steps (n=3): 33% -> 67% (fixed 1, broken 0)
- 10-12 steps (n=2): 100% -> 100% (fixed 0, broken 0)
- remasked: 40.0% of examples, 1.50 rounds on average; 0 came back identical
- remask ratio |M|/L: 25.3% per round, 37.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 37.0%
