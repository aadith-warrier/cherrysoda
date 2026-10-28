# graph_remask_gsm8k_llada

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 100

| | draft | after remasking |
|---|---|---|
| accuracy | 63.0% | 74.0% (+11.0%, 95% CI [+5.0%, +17.0%]) |
| reasoning consistency (no flagged step) | 72.0% | 87.0% |
| mean NFE | 256 | 283 (+27) |

fixed 11, broken 0 (exact McNemar p = 0.001)

- examples with a flagged step: 24 wrong, 4 right drafts
- no answer 0.0%, hit token limit 0.0%, 99.3 s/problem
- answer format ('The answer is'): draft 50.0%, final 50.0%; accuracy among formatted 54.0% -> 64.0%
- verifier in situ: graphs parsed cleanly 100.0%, 9.3 steps per answer; a flag means a wrong draft 85.7% of the time; 13 wrong drafts never flagged, 13 flagged but still wrong; flags by type {'arithmetic': 30, 'ungrounded_operand': 7}
- tokens: draft 254, final 254, re-denoised 26 per problem
- time per problem: draft 92.8 s + refine 6.5 s + parse/verify 0.15 s = 99.4 s; peak GPU memory 15.5 GiB
- <= 8 steps (n=36): 75% -> 83% (fixed 3, broken 0)
- 9-10 steps (n=34): 56% -> 71% (fixed 5, broken 0)
- > 10 steps (n=30): 57% -> 67% (fixed 3, broken 0)
- remasked: 28.0% of examples, 1.32 rounds on average; 5 came back identical
- remask ratio |M|/L: 27.5% per round, 36.4% cumulative
- affected-subgraph ratio |A(B)|/|V|: 36.5%
