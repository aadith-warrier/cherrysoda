# scheduled_gsm8k_llada

llada_8b, method `scheduled`, 1 token(s) per active step per pass, n = 100

| | draft | after scheduling |
|---|---|---|
| accuracy | 63.0% | 67.0% (+4.0%, 95% CI [-6.0%, +13.0%]) |
| reasoning consistency (no flagged step) | 72.0% | 69.0% |
| mean NFE | 256 | 359 (+103) |

fixed 14, broken 10 (exact McNemar p = 0.541)

- examples with a flagged step: 24 wrong, 4 right drafts
- no answer 0.0%, hit token limit 0.0%, 118.7 s/problem
- answer format ('The answer is'): draft 50.0%, final 77.0%; accuracy among formatted 54.0% -> 62.3%
- verifier in situ: graphs parsed cleanly 100.0%, 9.3 steps per answer; a flag means a wrong draft 85.7% of the time; 13 wrong drafts never flagged, 15 flagged but still wrong; flags by type {'arithmetic': 30, 'ungrounded_operand': 7}
- tokens: draft 254, final 254, re-denoised 256 per problem
- time per problem: draft 92.8 s + refine 25.9 s + parse/verify 0.22 s = 118.9 s; peak GPU memory 15.6 GiB
- <= 8 steps (n=36): 75% -> 72% (fixed 3, broken 4)
- 9-10 steps (n=34): 56% -> 79% (fixed 9, broken 1)
- > 10 steps (n=30): 57% -> 47% (fixed 2, broken 5)
- scheduled pass: 103 NFE (2.68 tokens per pass, 5.4 dependency levels); 0 examples left as drafted
