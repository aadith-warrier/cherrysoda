# graph_sched_ans_proofwriter_d3_llada_basedrafts_limit5

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 5

| | draft | after remasking |
|---|---|---|
| accuracy | 20.0% | 60.0% (+40.0%, 95% CI [-40.0%, +100.0%]) |
| reasoning consistency (no flagged step) | 0.0% | 40.0% |
| mean NFE | 256 | 371 (+115) |

fixed 3, broken 1 (exact McNemar p = 0.625)

- examples with a flagged step: 4 wrong, 1 right drafts
- no answer 0.0%, hit token limit 0.0%, 32.0 s/problem
- answer format ('The answer is'): draft 100.0%, final 80.0%; accuracy among formatted 20.0% -> 50.0%
- verifier in situ: graphs parsed cleanly 100.0%, 10.0 steps per answer; a flag means a wrong draft 80.0% of the time; 0 wrong drafts never flagged, 1 flagged but still wrong; flags by type {'missed_inference': 4, 'unsupported_answer': 7, 'contradiction': 1, 'false_premise': 1, 'unsupported': 1}
- tokens: draft 230, final 233, re-denoised 113 per problem
- time per problem: draft 23.9 s + refine 8.1 s + parse/verify 0.02 s = 32.0 s; peak GPU memory 15.2 GiB
- <= 9 steps (n=2): 50% -> 50% (fixed 1, broken 1)
- 10-11 steps (n=2): 0% -> 50% (fixed 1, broken 0)
- > 11 steps (n=1): 0% -> 100% (fixed 1, broken 0)
- remasked: 100.0% of examples, 2.20 rounds on average; 0 came back identical
- remask ratio |M|/L: 22.8% per round, 50.1% cumulative
- affected-subgraph ratio |A(B)|/|V|: 30.8%
