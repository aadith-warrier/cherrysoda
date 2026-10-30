# full_remask_gsm8k_llada

llada_8b, method `remask`, mode `full`, max_rounds 3, temperature 0.0, n = 100

| | draft | after remasking |
|---|---|---|
| accuracy | 63.0% | 62.0% (-1.0%, 95% CI [-4.0%, +0.0%]) |
| reasoning consistency (no flagged step) | 72.0% | 72.0% |
| mean NFE | 256 | 338 (+82) |

fixed 0, broken 1 (exact McNemar p = 1.000)

- examples with a flagged step: 24 wrong, 4 right drafts
- no answer 0.0%, hit token limit 0.0%, 113.5 s/problem
- answer format ('The answer is'): draft 50.0%, final 50.0%; accuracy among formatted 54.0% -> 52.0%
- verifier in situ: graphs parsed cleanly 100.0%, 9.3 steps per answer; a flag means a wrong draft 85.7% of the time; 13 wrong drafts never flagged, 24 flagged but still wrong; flags by type {'arithmetic': 30, 'ungrounded_operand': 7}
- tokens: draft 254, final 254, re-denoised 81 per problem
- time per problem: draft 92.8 s + refine 20.7 s + parse/verify 0.14 s = 113.7 s; peak GPU memory 15.6 GiB
- <= 8 steps (n=36): 75% -> 75% (fixed 0, broken 0)
- 9-10 steps (n=34): 56% -> 56% (fixed 0, broken 0)
- > 10 steps (n=30): 57% -> 53% (fixed 0, broken 1)
- remasked: 28.0% of examples, 1.14 rounds on average; 24 came back identical
- remask ratio |M|/L: 100.0% per round, 114.3% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
