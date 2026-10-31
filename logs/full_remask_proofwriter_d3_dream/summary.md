# full_remask_proofwriter_d3_dream

dream_7b, method `remask`, mode `full`, max_rounds 3, temperature None, n = 150

| | draft | after remasking |
|---|---|---|
| accuracy | 41.3% | 40.7% (-0.7%, 95% CI [-2.0%, +0.0%]) |
| reasoning consistency (no flagged step) | 38.0% | 38.0% |
| mean NFE | 256 | 732 (+476) |

fixed 0, broken 1 (exact McNemar p = 1.000)

- examples with a flagged step: 67 wrong, 26 right drafts
- no answer 26.7%, hit token limit 0.7%, 40.2 s/problem
- answer format ('The answer is'): draft 72.7%, final 72.7%; accuracy among formatted 56.0% -> 55.0%
- verifier in situ: graphs parsed cleanly 100.0%, 11.9 steps per answer; a flag means a wrong draft 72.0% of the time; 21 wrong drafts never flagged, 67 flagged but still wrong; flags by type {'unsupported': 92, 'unsupported_premise': 203, 'hallucinated_rule': 252, 'false_premise': 37, 'missed_inference': 4, 'contradiction': 9}
- tokens: draft 194, final 194, re-denoised 412 per problem
- time per problem: draft 14.1 s + refine 26.1 s + parse/verify 0.31 s = 40.5 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=51): 51% -> 49% (fixed 0, broken 1)
- 11-16 steps (n=57): 35% -> 35% (fixed 0, broken 0)
- > 16 steps (n=42): 38% -> 38% (fixed 0, broken 0)
- remasked: 62.0% of examples, 3.00 rounds on average; 75 came back identical
- remask ratio |M|/L: 100.0% per round, 300.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
