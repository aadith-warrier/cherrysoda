# graph_remask_gsm8k_dream_n1319

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 1319

| | draft | after remasking |
|---|---|---|
| accuracy | 78.5% | 78.9% (+0.5%, 95% CI [-0.2%, +1.1%]) |
| reasoning consistency (no flagged step) | 87.2% | 90.5% |
| mean NFE | 256 | 324 (+68) |

fixed 13, broken 7 (exact McNemar p = 0.263)

- examples with a flagged step: 88 wrong, 81 right drafts
- no answer 0.0%, hit token limit 0.1%, 99.1 s/problem
- answer format ('The answer is'): draft 97.1%, final 97.2%; accuracy among formatted 79.2% -> 79.6%
- verifier in situ: graphs parsed cleanly 98.3%, 4.5 steps per answer; a flag means a wrong draft 52.1% of the time; 196 wrong drafts never flagged, 75 flagged but still wrong; flags by type {'arithmetic': 103, 'ungrounded_operand': 104}
- tokens: draft 117, final 117, re-denoised 32 per problem
- time per problem: draft 84.3 s + refine 14.8 s + parse/verify 0.23 s = 99.3 s; peak GPU memory 15.9 GiB
- <= 3 steps (n=465): 78% -> 78% (fixed 2, broken 2)
- 4-5 steps (n=546): 83% -> 84% (fixed 7, broken 2)
- > 5 steps (n=308): 70% -> 70% (fixed 4, broken 3)
- remasked: 12.8% of examples, 2.49 rounds on average; 78 came back identical
- remask ratio |M|/L: 78.8% per round, 196.2% cumulative
- affected-subgraph ratio |A(B)|/|V|: 79.9%
