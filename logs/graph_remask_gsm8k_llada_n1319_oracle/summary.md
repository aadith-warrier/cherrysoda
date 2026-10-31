# graph_remask_gsm8k_llada_n1319_oracle

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 56

| | draft | after remasking |
|---|---|---|
| accuracy | 0.0% | 58.9% (+58.9%, 95% CI [+46.4%, +71.4%]) |
| reasoning consistency (no flagged step) | 0.0% | 67.9% |
| mean NFE | 256 | 341 (+85) |

fixed 33, broken 0 (exact McNemar p = 0.000)

- examples with a flagged step: 56 wrong, 0 right drafts
- no answer 0.0%, hit token limit 0.0%, 88.4 s/problem
- answer format ('The answer is'): draft 76.8%, final 76.8%; accuracy among formatted 0.0% -> 53.5%
- verifier in situ: graphs parsed cleanly 94.6%, 9.8 steps per answer; a flag means a wrong draft 100.0% of the time; 0 wrong drafts never flagged, 23 flagged but still wrong; flags by type {'unspecified': 182, 'arithmetic': 41, 'ungrounded_operand': 5, 'oracle': 1}
- tokens: draft 254, final 254, re-denoised 84 per problem
- time per problem: draft 66.8 s + refine 21.6 s + parse/verify 0.18 s = 88.6 s; peak GPU memory 15.6 GiB
- <= 9 steps (n=26): 0% -> 58% (fixed 15, broken 0)
- 10-10 steps (n=12): 0% -> 58% (fixed 7, broken 0)
- > 10 steps (n=18): 0% -> 61% (fixed 11, broken 0)
- remasked: 100.0% of examples, 1.00 rounds on average; 3 came back identical
- remask ratio |M|/L: 32.9% per round, 32.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 44.7%
