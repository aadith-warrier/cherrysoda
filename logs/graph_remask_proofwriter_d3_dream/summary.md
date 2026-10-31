# graph_remask_proofwriter_d3_dream

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 150

| | draft | after remasking |
|---|---|---|
| accuracy | 41.3% | 40.7% (-0.7%, 95% CI [-4.0%, +2.0%]) |
| reasoning consistency (no flagged step) | 38.0% | 43.3% |
| mean NFE | 256 | 593 (+337) |

fixed 2, broken 3 (exact McNemar p = 1.000)

- examples with a flagged step: 67 wrong, 26 right drafts
- no answer 28.7%, hit token limit 2.0%, 32.6 s/problem
- answer format ('The answer is'): draft 72.7%, final 69.3%; accuracy among formatted 56.0% -> 56.7%
- verifier in situ: graphs parsed cleanly 100.0%, 11.9 steps per answer; a flag means a wrong draft 72.0% of the time; 21 wrong drafts never flagged, 65 flagged but still wrong; flags by type {'unsupported': 92, 'unsupported_premise': 203, 'hallucinated_rule': 252, 'false_premise': 37, 'missed_inference': 4, 'contradiction': 9}
- tokens: draft 194, final 198, re-denoised 288 per problem
- time per problem: draft 14.1 s + refine 18.6 s + parse/verify 0.31 s = 33.0 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=51): 51% -> 49% (fixed 1, broken 2)
- 11-16 steps (n=57): 35% -> 35% (fixed 1, broken 1)
- > 16 steps (n=42): 38% -> 38% (fixed 0, broken 0)
- remasked: 62.0% of examples, 2.86 rounds on average; 51 came back identical
- remask ratio |M|/L: 72.5% per round, 207.3% cumulative
- affected-subgraph ratio |A(B)|/|V|: 71.8%
