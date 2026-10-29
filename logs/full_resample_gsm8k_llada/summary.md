# full_resample_gsm8k_llada

llada_8b, method `remask`, mode `full`, max_rounds 3, temperature 0.5, n = 100

| | draft | after remasking |
|---|---|---|
| accuracy | 63.0% | 63.0% (+0.0%, 95% CI [-5.0%, +5.0%]) |
| reasoning consistency (no flagged step) | 72.0% | 78.0% |
| mean NFE | 256 | 448 (+192) |

fixed 3, broken 3 (exact McNemar p = 1.000)

- examples with a flagged step: 24 wrong, 4 right drafts
- no answer 0.0%, hit token limit 0.0%, 142.1 s/problem
- answer format ('The answer is'): draft 50.0%, final 51.0%; accuracy among formatted 54.0% -> 52.9%
- verifier in situ: graphs parsed cleanly 100.0%, 9.3 steps per answer; a flag means a wrong draft 85.7% of the time; 13 wrong drafts never flagged, 21 flagged but still wrong; flags by type {'arithmetic': 30, 'ungrounded_operand': 7}
- tokens: draft 254, final 254, re-denoised 191 per problem
- time per problem: draft 92.8 s + refine 49.3 s + parse/verify 0.19 s = 142.3 s; peak GPU memory 16.3 GiB
- <= 8 steps (n=36): 75% -> 75% (fixed 1, broken 1)
- 9-10 steps (n=34): 56% -> 53% (fixed 0, broken 1)
- > 10 steps (n=30): 57% -> 60% (fixed 2, broken 1)
- remasked: 28.0% of examples, 2.68 rounds on average; 0 came back identical
- remask ratio |M|/L: 100.0% per round, 267.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
