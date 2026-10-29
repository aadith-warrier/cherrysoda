# scheduled_gsm8k_llada_limit20

llada_8b, method `scheduled`, 1 token(s) per active step per pass, n = 20

| | draft | after scheduling |
|---|---|---|
| accuracy | 50.0% | 50.0% (+0.0%, 95% CI [-20.0%, +20.0%]) |
| reasoning consistency (no flagged step) | 50.0% | 55.0% |
| mean NFE | 256 | 358 (+102) |

fixed 2, broken 2 (exact McNemar p = 1.000)

- examples with a flagged step: 8 wrong, 2 right drafts
- no answer 0.0%, hit token limit 0.0%, 109.0 s/problem
- answer format ('The answer is'): draft 50.0%, final 95.0%; accuracy among formatted 50.0% -> 47.4%
- verifier in situ: graphs parsed cleanly 100.0%, 10.1 steps per answer; a flag means a wrong draft 80.0% of the time; 2 wrong drafts never flagged, 6 flagged but still wrong; flags by type {'arithmetic': 9, 'ungrounded_operand': 6}
- tokens: draft 254, final 255, re-denoised 256 per problem
- time per problem: draft 83.2 s + refine 25.8 s + parse/verify 0.23 s = 109.2 s; peak GPU memory 15.6 GiB
- <= 9 steps (n=8): 62% -> 75% (fixed 2, broken 1)
- 10-11 steps (n=8): 62% -> 50% (fixed 0, broken 1)
- > 11 steps (n=4): 0% -> 0% (fixed 0, broken 0)
- scheduled pass: 102 NFE (2.61 tokens per pass, 5.3 dependency levels); 0 examples left as drafted
