# graph_remask_gsm8k_llada_n1319

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 1319

| | draft | after remasking |
|---|---|---|
| accuracy | 63.8% | 74.8% (+11.0%, 95% CI [+9.2%, +12.8%]) |
| reasoning consistency (no flagged step) | 73.5% | 89.6% |
| mean NFE | 256 | 284 (+28) |

fixed 157, broken 12 (exact McNemar p = 0.000)

- examples with a flagged step: 301 wrong, 49 right drafts
- no answer 0.0%, hit token limit 0.0%, 74.1 s/problem
- answer format ('The answer is'): draft 63.9%, final 64.1%; accuracy among formatted 59.3% -> 71.4%
- verifier in situ: graphs parsed cleanly 98.4%, 9.7 steps per answer; a flag means a wrong draft 86.0% of the time; 176 wrong drafts never flagged, 144 flagged but still wrong; flags by type {'arithmetic': 360, 'ungrounded_operand': 80}
- tokens: draft 253, final 253, re-denoised 27 per problem
- time per problem: draft 67.0 s + refine 7.1 s + parse/verify 0.22 s = 74.3 s; peak GPU memory 15.6 GiB
- <= 9 steps (n=647): 65% -> 77% (fixed 83, broken 4)
- 10-11 steps (n=398): 63% -> 74% (fixed 44, broken 2)
- > 11 steps (n=274): 62% -> 70% (fixed 30, broken 6)
- remasked: 26.5% of examples, 1.37 rounds on average; 36 came back identical
- remask ratio |M|/L: 29.4% per round, 40.4% cumulative
- affected-subgraph ratio |A(B)|/|V|: 40.7%
