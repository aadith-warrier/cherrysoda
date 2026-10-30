# graph_scheduled_gsm8k_dream_n1319_r870-1319

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 449

| | draft | after remasking |
|---|---|---|
| accuracy | 78.8% | 79.3% (+0.4%, 95% CI [-1.1%, +2.2%]) |
| reasoning consistency (no flagged step) | 86.9% | 93.8% |
| mean NFE | 256 | 281 (+25) |

fixed 9, broken 7 (exact McNemar p = 0.804)

- examples with a flagged step: 29 wrong, 30 right drafts
- no answer 0.0%, hit token limit 0.0%, 62.7 s/problem
- answer format ('The answer is'): draft 97.8%, final 96.0%; accuracy among formatted 79.0% -> 81.2%
- verifier in situ: graphs parsed cleanly 99.1%, 4.6 steps per answer; a flag means a wrong draft 49.2% of the time; 66 wrong drafts never flagged, 20 flagged but still wrong; flags by type {'ungrounded_operand': 31, 'arithmetic': 38}
- tokens: draft 120, final 121, re-denoised 26 per problem
- time per problem: draft 57.0 s + refine 5.7 s + parse/verify 0.25 s = 62.9 s; peak GPU memory 15.4 GiB
- <= 4 steps (n=246): 83% -> 83% (fixed 6, broken 5)
- 5-5 steps (n=93): 87% -> 87% (fixed 1, broken 1)
- > 5 steps (n=110): 63% -> 64% (fixed 2, broken 1)
- remasked: 13.1% of examples, 2.05 rounds on average; 6 came back identical
- remask ratio |M|/L: 75.1% per round, 154.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 76.3%
