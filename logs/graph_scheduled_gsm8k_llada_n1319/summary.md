# graph_scheduled_gsm8k_llada_n1319

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 1319

| | draft | after remasking |
|---|---|---|
| accuracy | 63.8% | 75.9% (+12.1%, 95% CI [+10.2%, +13.9%]) |
| reasoning consistency (no flagged step) | 73.5% | 90.4% |
| mean NFE | 256 | 281 (+25) |

fixed 171, broken 12 (exact McNemar p = 0.000)

- examples with a flagged step: 301 wrong, 49 right drafts
- no answer 0.0%, hit token limit 0.0%, 73.3 s/problem
- answer format ('The answer is'): draft 63.9%, final 64.1%; accuracy among formatted 59.3% -> 73.1%
- verifier in situ: graphs parsed cleanly 98.4%, 9.7 steps per answer; a flag means a wrong draft 86.0% of the time; 176 wrong drafts never flagged, 130 flagged but still wrong; flags by type {'arithmetic': 360, 'ungrounded_operand': 80}
- tokens: draft 253, final 253, re-denoised 26 per problem
- time per problem: draft 67.0 s + refine 6.3 s + parse/verify 0.19 s = 73.5 s; peak GPU memory 15.6 GiB
- <= 9 steps (n=647): 65% -> 78% (fixed 88, broken 4)
- 10-11 steps (n=398): 63% -> 75% (fixed 49, broken 2)
- > 11 steps (n=274): 62% -> 72% (fixed 34, broken 6)
- remasked: 26.5% of examples, 1.32 rounds on average; 33 came back identical
- remask ratio |M|/L: 29.4% per round, 38.7% cumulative
- affected-subgraph ratio |A(B)|/|V|: 40.5%
