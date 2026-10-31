# graph_ans_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 79.2% (+9.3%, 95% CI [+5.2%, +13.5%]) |
| reasoning consistency (no flagged step) | 51.3% | 76.7% |
| mean NFE | 256 | 314 (+58) |

fixed 120, broken 64 (exact McNemar p = 0.000)

- examples with a flagged step: 153 wrong, 139 right drafts
- no answer 0.0%, hit token limit 0.0%, 21.2 s/problem
- answer format ('The answer is'): draft 100.0%, final 98.3%; accuracy among formatted 69.8% -> 80.2%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 52.4% of the time; 28 wrong drafts never flagged, 33 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported_answer': 360, 'unsupported': 154, 'unsupported_premise': 69, 'hallucinated_rule': 55, 'missed_inference': 42}
- tokens: draft 241, final 245, re-denoised 51 per problem
- time per problem: draft 17.3 s + refine 3.9 s + parse/verify 0.01 s = 21.2 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 74% (fixed 44, broken 38)
- 13-16 steps (n=200): 68% -> 83% (fixed 44, broken 14)
- > 16 steps (n=177): 71% -> 82% (fixed 32, broken 12)
- remasked: 48.7% of examples, 2.12 rounds on average; 13 came back identical
- remask ratio |M|/L: 19.8% per round, 42.1% cumulative
- affected-subgraph ratio |A(B)|/|V|: 22.9%
