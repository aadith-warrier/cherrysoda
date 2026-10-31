# graph_sched_gsm8k_llada_zs_limit20

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 20

| | draft | after remasking |
|---|---|---|
| accuracy | 70.0% | 70.0% (+0.0%, 95% CI [+0.0%, +0.0%]) |
| reasoning consistency (no flagged step) | 95.0% | 95.0% |
| mean NFE | 256 | 257 (+1) |

fixed 0, broken 0 (exact McNemar p = 1.000)

- examples with a flagged step: 1 wrong, 0 right drafts
- no answer 0.0%, hit token limit 0.0%, 16.2 s/problem
- answer format ('The answer is'): draft 95.0%, final 95.0%; accuracy among formatted 73.7% -> 73.7%
- verifier in situ: graphs parsed cleanly 100.0%, 9.1 steps per answer; a flag means a wrong draft 100.0% of the time; 5 wrong drafts never flagged, 1 flagged but still wrong; flags by type {'arithmetic': 1}
- tokens: draft 219, final 219, re-denoised 1 per problem
- time per problem: draft 16.1 s + refine 0.1 s + parse/verify 0.09 s = 16.3 s
- <= 8 steps (n=8): 50% -> 50% (fixed 0, broken 0)
- 9-11 steps (n=8): 75% -> 75% (fixed 0, broken 0)
- > 11 steps (n=4): 100% -> 100% (fixed 0, broken 0)
- remasked: 5.0% of examples, 1.00 rounds on average; 1 came back identical
- remask ratio |M|/L: 10.6% per round, 10.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 22.2%
