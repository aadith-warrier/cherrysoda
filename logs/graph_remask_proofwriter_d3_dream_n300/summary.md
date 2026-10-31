# graph_remask_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 42.0% (+0.0%, 95% CI [-2.3%, +2.3%]) |
| reasoning consistency (no flagged step) | 36.7% | 43.3% |
| mean NFE | 256 | 583 (+327) |

fixed 6, broken 6 (exact McNemar p = 1.000)

- examples with a flagged step: 131 wrong, 59 right drafts
- no answer 29.0%, hit token limit 2.3%, 32.6 s/problem
- answer format ('The answer is'): draft 74.0%, final 69.7%; accuracy among formatted 56.3% -> 58.9%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 68.9% of the time; 43 wrong drafts never flagged, 125 flagged but still wrong; flags by type {'unsupported': 218, 'unsupported_premise': 500, 'hallucinated_rule': 440, 'false_premise': 73, 'missed_inference': 15, 'contradiction': 43}
- tokens: draft 195, final 200, re-denoised 280 per problem
- time per problem: draft 14.1 s + refine 18.5 s + parse/verify 0.31 s = 32.9 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 51% (fixed 2, broken 3)
- 11-15 steps (n=103): 35% -> 37% (fixed 4, broken 2)
- > 15 steps (n=95): 39% -> 38% (fixed 0, broken 1)
- remasked: 63.3% of examples, 2.81 rounds on average; 94 came back identical
- remask ratio |M|/L: 70.2% per round, 197.4% cumulative
- affected-subgraph ratio |A(B)|/|V|: 70.5%
