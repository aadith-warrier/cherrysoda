# full_resample_gsm8k_llada_n1319

llada_8b, method `remask`, mode `full`, max_rounds 3, temperature 0.5, n = 1319

| | draft | after remasking |
|---|---|---|
| accuracy | 63.8% | 67.6% (+3.7%, 95% CI [+2.6%, +4.9%]) |
| reasoning consistency (no flagged step) | 73.5% | 84.5% |
| mean NFE | 256 | 424 (+168) |

fixed 55, broken 6 (exact McNemar p = 0.000)

- examples with a flagged step: 301 wrong, 49 right drafts
- no answer 0.0%, hit token limit 0.0%, 110.3 s/problem
- answer format ('The answer is'): draft 63.9%, final 63.8%; accuracy among formatted 59.3% -> 63.3%
- verifier in situ: graphs parsed cleanly 98.4%, 9.7 steps per answer; a flag means a wrong draft 86.0% of the time; 176 wrong drafts never flagged, 246 flagged but still wrong; flags by type {'arithmetic': 360, 'ungrounded_operand': 80}
- tokens: draft 253, final 253, re-denoised 167 per problem
- time per problem: draft 67.0 s + refine 43.3 s + parse/verify 0.24 s = 110.6 s; peak GPU memory 16.3 GiB
- <= 9 steps (n=647): 65% -> 68% (fixed 23, broken 2)
- 10-11 steps (n=398): 63% -> 67% (fixed 19, broken 2)
- > 11 steps (n=274): 62% -> 66% (fixed 13, broken 2)
- remasked: 26.5% of examples, 2.48 rounds on average; 9 came back identical
- remask ratio |M|/L: 100.0% per round, 248.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
