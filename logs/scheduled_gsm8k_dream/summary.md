# scheduled_gsm8k_dream

dream_7b, method `scheduled`, 1 token(s) per active step per pass, n = 100

| | draft | after scheduling |
|---|---|---|
| accuracy | 82.0% | 61.0% (-21.0%, 95% CI [-30.0%, -12.0%]) |
| reasoning consistency (no flagged step) | 85.0% | 82.0% |
| mean NFE | 256 | 352 (+96) |

fixed 3, broken 24 (exact McNemar p = 0.000)

- examples with a flagged step: 6 wrong, 9 right drafts
- no answer 0.0%, hit token limit 0.0%, 85.4 s/problem
- answer format ('The answer is'): draft 97.0%, final 79.0%; accuracy among formatted 82.5% -> 73.4%
- verifier in situ: graphs parsed cleanly 97.0%, 4.3 steps per answer; a flag means a wrong draft 40.0% of the time; 12 wrong drafts never flagged, 6 flagged but still wrong; flags by type {'arithmetic': 8, 'ungrounded_operand': 10}
- tokens: draft 112, final 124, re-denoised 256 per problem
- time per problem: draft 64.6 s + refine 20.8 s + parse/verify 0.23 s = 85.6 s; peak GPU memory 15.4 GiB
- <= 4 steps (n=67): 87% -> 66% (fixed 1, broken 15)
- > 4 steps (n=33): 73% -> 52% (fixed 2, broken 9)
- scheduled pass: 96 NFE (1.19 tokens per pass, 3.6 dependency levels); 0 examples left as drafted
