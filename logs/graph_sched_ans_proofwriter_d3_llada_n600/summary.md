# graph_sched_ans_proofwriter_d3_llada_n600

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 69.8% | 75.8% (+6.0%, 95% CI [+2.0%, +10.0%]) |
| reasoning consistency (no flagged step) | 51.3% | 74.2% |
| mean NFE | 256 | 301 (+45) |

fixed 96, broken 60 (exact McNemar p = 0.005)

- examples with a flagged step: 153 wrong, 139 right drafts
- no answer 0.0%, hit token limit 0.0%, 20.4 s/problem
- answer format ('The answer is'): draft 100.0%, final 97.2%; accuracy among formatted 69.8% -> 77.7%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 52.4% of the time; 28 wrong drafts never flagged, 57 flagged but still wrong; flags by type {'contradiction': 19, 'false_premise': 14, 'unsupported_answer': 360, 'unsupported': 154, 'unsupported_premise': 69, 'hallucinated_rule': 55, 'missed_inference': 42}
- tokens: draft 241, final 242, re-denoised 49 per problem
- time per problem: draft 17.3 s + refine 3.1 s + parse/verify 0.01 s = 20.4 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=223): 71% -> 71% (fixed 34, broken 33)
- 13-16 steps (n=200): 68% -> 78% (fixed 33, broken 13)
- > 16 steps (n=177): 71% -> 79% (fixed 29, broken 14)
- remasked: 48.7% of examples, 2.11 rounds on average; 13 came back identical
- remask ratio |M|/L: 19.7% per round, 41.5% cumulative
- affected-subgraph ratio |A(B)|/|V|: 23.0%
