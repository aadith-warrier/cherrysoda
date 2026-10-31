# graph_sched_gsm8k_llada_zs

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 80.3% | 81.0% (+0.7%, 95% CI [+0.0%, +1.7%]) |
| reasoning consistency (no flagged step) | 93.0% | 95.0% |
| mean NFE | 256 | 262 (+6) |

fixed 2, broken 0 (exact McNemar p = 0.500)

- examples with a flagged step: 12 wrong, 9 right drafts
- no answer 0.0%, hit token limit 0.0%, 16.3 s/problem
- answer format ('The answer is'): draft 94.3%, final 94.0%; accuracy among formatted 80.6% -> 81.6%
- verifier in situ: graphs parsed cleanly 99.0%, 9.4 steps per answer; a flag means a wrong draft 57.1% of the time; 47 wrong drafts never flagged, 10 flagged but still wrong; flags by type {'arithmetic': 14, 'ungrounded_operand': 17}
- tokens: draft 221, final 221, re-denoised 7 per problem
- time per problem: draft 15.9 s + refine 0.4 s + parse/verify 0.10 s = 16.4 s
- <= 8 steps (n=111): 85% -> 85% (fixed 0, broken 0)
- 9-11 steps (n=127): 79% -> 80% (fixed 2, broken 0)
- > 11 steps (n=62): 76% -> 76% (fixed 0, broken 0)
- remasked: 7.0% of examples, 1.43 rounds on average; 9 came back identical
- remask ratio |M|/L: 27.2% per round, 38.8% cumulative
- affected-subgraph ratio |A(B)|/|V|: 33.3%
