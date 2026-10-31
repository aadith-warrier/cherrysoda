# graph_remask_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 71.2% (+1.3%, 95% CI [+0.2%, +2.5%]) |
| reasoning consistency (no flagged step) | 70.7% | 78.2% |
| mean NFE | 256 | 292 (+36) |

fixed 11, broken 3 (exact McNemar p = 0.057)

- examples with a flagged step: 108 wrong, 68 right drafts
- no answer 0.0%, hit token limit 0.0%, 19.7 s/problem
- answer format ('The answer is'): draft 100.0%, final 100.0%; accuracy among formatted 69.8% -> 71.2%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 61.4% of the time; 73 wrong drafts never flagged, 97 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported': 156, 'unsupported_premise': 72, 'hallucinated_rule': 55, 'missed_inference': 45}
- tokens: draft 241, final 242, re-denoised 34 per problem
- time per problem: draft 17.3 s + refine 2.4 s + parse/verify 0.01 s = 19.7 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 74% (fixed 8, broken 1)
- 13-16 steps (n=200): 68% -> 68% (fixed 1, broken 2)
- > 16 steps (n=177): 71% -> 72% (fixed 2, broken 0)
- remasked: 29.3% of examples, 1.72 rounds on average; 31 came back identical
- remask ratio |M|/L: 26.9% per round, 46.1% cumulative
- affected-subgraph ratio |A(B)|/|V|: 28.6%
