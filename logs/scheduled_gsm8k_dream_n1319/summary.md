# scheduled_gsm8k_dream_n1319

dream_7b, method `scheduled`, 1 token(s) per active step per pass, n = 1319

| | draft | after scheduling |
|---|---|---|
| accuracy | 78.5% | 50.6% (-27.8%, 95% CI [-30.6%, -25.1%]) |
| reasoning consistency (no flagged step) | 87.2% | 78.2% |
| mean NFE | 256 | 354 (+98) |

fixed 40, broken 407 (exact McNemar p = 0.000)

- examples with a flagged step: 88 wrong, 81 right drafts
- no answer 0.1%, hit token limit 0.2%, 98.5 s/problem
- answer format ('The answer is'): draft 97.1%, final 72.7%; accuracy among formatted 79.2% -> 64.0%
- verifier in situ: graphs parsed cleanly 98.3%, 4.5 steps per answer; a flag means a wrong draft 52.1% of the time; 196 wrong drafts never flagged, 72 flagged but still wrong; flags by type {'arithmetic': 103, 'ungrounded_operand': 104}
- tokens: draft 117, final 132, re-denoised 256 per problem
- time per problem: draft 84.3 s + refine 14.2 s + parse/verify 0.23 s = 98.7 s; peak GPU memory 15.4 GiB
- <= 3 steps (n=465): 78% -> 56% (fixed 14, broken 116)
- 4-5 steps (n=546): 83% -> 55% (fixed 16, broken 170)
- > 5 steps (n=308): 70% -> 34% (fixed 10, broken 121)
- scheduled pass: 98 NFE (1.23 tokens per pass, 3.6 dependency levels); 0 examples left as drafted
