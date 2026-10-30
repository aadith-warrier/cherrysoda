# graph_remask_gsm8k_llada_limit20

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 20

| | draft | after remasking |
|---|---|---|
| accuracy | 50.0% | 60.0% (+10.0%, 95% CI [+0.0%, +25.0%]) |
| reasoning consistency (no flagged step) | 50.0% | 75.0% |
| mean NFE | 256 | 305 (+49) |

fixed 2, broken 0 (exact McNemar p = 0.500)

- examples with a flagged step: 8 wrong, 2 right drafts
- no answer 0.0%, hit token limit 0.0%, 95.3 s/problem
- answer format ('The answer is'): draft 50.0%, final 50.0%; accuracy among formatted 50.0% -> 50.0%
- verifier in situ: graphs parsed cleanly 100.0%, 10.1 steps per answer; a flag means a wrong draft 80.0% of the time; 2 wrong drafts never flagged, 6 flagged but still wrong; flags by type {'arithmetic': 9, 'ungrounded_operand': 6}
- tokens: draft 254, final 254, re-denoised 48 per problem
- time per problem: draft 83.2 s + refine 12.2 s + parse/verify 0.19 s = 95.5 s; peak GPU memory 15.5 GiB
- <= 9 steps (n=8): 62% -> 75% (fixed 1, broken 0)
- 10-11 steps (n=8): 62% -> 62% (fixed 0, broken 0)
- > 11 steps (n=4): 0% -> 25% (fixed 1, broken 0)
- remasked: 50.0% of examples, 1.40 rounds on average; 2 came back identical
- remask ratio |M|/L: 26.9% per round, 37.7% cumulative
- affected-subgraph ratio |A(B)|/|V|: 34.5%
