# graph_remask_gsm8k_dream

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 100

| | draft | after remasking |
|---|---|---|
| accuracy | 82.0% | 82.0% (+0.0%, 95% CI [+0.0%, +0.0%]) |
| reasoning consistency (no flagged step) | 85.0% | 89.0% |
| mean NFE | 256 | 334 (+78) |

fixed 0, broken 0 (exact McNemar p = 1.000)

- examples with a flagged step: 6 wrong, 9 right drafts
- no answer 0.0%, hit token limit 0.0%, 86.4 s/problem
- answer format ('The answer is'): draft 97.0%, final 97.0%; accuracy among formatted 82.5% -> 82.5%
- verifier in situ: graphs parsed cleanly 97.0%, 4.3 steps per answer; a flag means a wrong draft 40.0% of the time; 12 wrong drafts never flagged, 6 flagged but still wrong; flags by type {'arithmetic': 8, 'ungrounded_operand': 10}
- tokens: draft 112, final 112, re-denoised 38 per problem
- time per problem: draft 64.6 s + refine 21.7 s + parse/verify 0.16 s = 86.5 s; peak GPU memory 15.9 GiB
- <= 4 steps (n=67): 87% -> 87% (fixed 0, broken 0)
- > 4 steps (n=33): 73% -> 73% (fixed 0, broken 0)
- remasked: 15.0% of examples, 2.47 rounds on average; 6 came back identical
- remask ratio |M|/L: 81.6% per round, 201.3% cumulative
- affected-subgraph ratio |A(B)|/|V|: 81.2%
