# graph_scheduled_proofwriter_d3_dream

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 150

| | draft | after remasking |
|---|---|---|
| accuracy | 41.3% | 43.3% (+2.0%, 95% CI [-3.3%, +7.3%]) |
| reasoning consistency (no flagged step) | 38.0% | 53.3% |
| mean NFE | 256 | 450 (+194) |

fixed 10, broken 7 (exact McNemar p = 0.629)

- examples with a flagged step: 67 wrong, 26 right drafts
- no answer 34.0%, hit token limit 0.7%, 24.9 s/problem
- answer format ('The answer is'): draft 72.7%, final 64.7%; accuracy among formatted 56.0% -> 64.9%
- verifier in situ: graphs parsed cleanly 100.0%, 11.9 steps per answer; a flag means a wrong draft 72.0% of the time; 21 wrong drafts never flagged, 57 flagged but still wrong; flags by type {'unsupported': 92, 'unsupported_premise': 203, 'hallucinated_rule': 252, 'false_premise': 37, 'missed_inference': 4, 'contradiction': 9}
- tokens: draft 194, final 180, re-denoised 235 per problem
- time per problem: draft 14.1 s + refine 10.8 s + parse/verify 0.26 s = 25.1 s; peak GPU memory 15.4 GiB
- <= 10 steps (n=51): 51% -> 45% (fixed 0, broken 3)
- 11-16 steps (n=57): 35% -> 44% (fixed 6, broken 1)
- > 16 steps (n=42): 38% -> 40% (fixed 4, broken 3)
- remasked: 62.0% of examples, 2.61 rounds on average; 11 came back identical
- remask ratio |M|/L: 68.8% per round, 179.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 67.9%
