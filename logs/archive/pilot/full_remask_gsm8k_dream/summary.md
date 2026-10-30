# full_remask_gsm8k_dream

dream_7b, method `remask`, mode `full`, max_rounds 3, temperature None, n = 100

| | draft | after remasking |
|---|---|---|
| accuracy | 82.0% | 82.0% (+0.0%, 95% CI [+0.0%, +0.0%]) |
| reasoning consistency (no flagged step) | 85.0% | 85.0% |
| mean NFE | 256 | 371 (+115) |

fixed 0, broken 0 (exact McNemar p = 1.000)

- examples with a flagged step: 6 wrong, 9 right drafts
- no answer 0.0%, hit token limit 0.0%, 90.0 s/problem
- answer format ('The answer is'): draft 97.0%, final 97.0%; accuracy among formatted 82.5% -> 82.5%
- verifier in situ: graphs parsed cleanly 97.0%, 4.3 steps per answer; a flag means a wrong draft 40.0% of the time; 12 wrong drafts never flagged, 6 flagged but still wrong; flags by type {'arithmetic': 8, 'ungrounded_operand': 10}
- tokens: draft 112, final 112, re-denoised 62 per problem
- time per problem: draft 64.6 s + refine 25.4 s + parse/verify 0.18 s = 90.2 s; peak GPU memory 15.9 GiB
- <= 4 steps (n=67): 87% -> 87% (fixed 0, broken 0)
- > 4 steps (n=33): 73% -> 73% (fixed 0, broken 0)
- remasked: 15.0% of examples, 3.00 rounds on average; 12 came back identical
- remask ratio |M|/L: 100.0% per round, 300.0% cumulative
- affected-subgraph ratio |A(B)|/|V|: 100.0%
