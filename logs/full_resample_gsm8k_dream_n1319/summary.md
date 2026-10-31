# full_resample_gsm8k_dream_n1319

dream_7b, method `remask`, mode `full`, max_rounds 3, temperature 0.5, n = 1319

| | draft | after remasking |
|---|---|---|
| accuracy | 78.5% | 76.2% (-2.3%, 95% CI [-3.4%, -1.1%]) |
| reasoning consistency (no flagged step) | 87.2% | 95.0% |
| mean NFE | 256 | 317 (+61) |

fixed 20, broken 50 (exact McNemar p = 0.000)

- examples with a flagged step: 88 wrong, 81 right drafts
- no answer 2.0%, hit token limit 0.1%, 97.7 s/problem
- answer format ('The answer is'): draft 97.1%, final 95.2%; accuracy among formatted 79.2% -> 78.5%
- verifier in situ: graphs parsed cleanly 98.3%, 4.5 steps per answer; a flag means a wrong draft 52.1% of the time; 196 wrong drafts never flagged, 68 flagged but still wrong; flags by type {'arithmetic': 103, 'ungrounded_operand': 104}
- tokens: draft 117, final 112, re-denoised 34 per problem
- time per problem: draft 84.3 s + refine 13.5 s + parse/verify 0.25 s = 98.0 s; peak GPU memory 15.9 GiB
- <= 3 steps (n=465): 78% -> 75% (fixed 7, broken 20)
- 4-5 steps (n=546): 83% -> 83% (fixed 11, broken 13)
- > 5 steps (n=308): 70% -> 65% (fixed 2, broken 17)
- remasked: 12.8% of examples, 1.87 rounds on average; 0 came back identical
- remask ratio |M|/L: 100.0% per round, 187.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
