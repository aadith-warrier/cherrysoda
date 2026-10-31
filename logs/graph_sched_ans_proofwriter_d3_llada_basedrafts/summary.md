# graph_sched_ans_proofwriter_d3_llada_basedrafts

llada_8b, method `remask`, mode `graph`, max_rounds 3, temperature 0.0, n = 600

| | draft | after remasking |
|---|---|---|
| accuracy | 67.5% | 76.7% (+9.2%, 95% CI [+5.2%, +13.2%]) |
| reasoning consistency (no flagged step) | 48.7% | 70.8% |
| mean NFE | 256 | 305 (+49) |

fixed 109, broken 54 (exact McNemar p = 0.000)

- examples with a flagged step: 170 wrong, 138 right drafts
- no answer 0.0%, hit token limit 0.0%, 32.5 s/problem
- answer format ('The answer is'): draft 99.7%, final 97.5%; accuracy among formatted 67.4% -> 77.9%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 55.2% of the time; 25 wrong drafts never flagged, 61 flagged but still wrong; flags by type {'missed_inference': 45, 'unsupported_answer': 362, 'contradiction': 19, 'false_premise': 9, 'unsupported': 204, 'unsupported_premise': 71, 'hallucinated_rule': 61}
- tokens: draft 241, final 242, re-denoised 55 per problem
- time per problem: draft 29.2 s + refine 3.4 s + parse/verify 0.01 s = 32.6 s; peak GPU memory 15.3 GiB
- <= 12 steps (n=221): 66% -> 68% (fixed 41, broken 35)
- 13-16 steps (n=213): 69% -> 81% (fixed 36, broken 11)
- > 16 steps (n=166): 68% -> 83% (fixed 32, broken 8)
- remasked: 51.3% of examples, 2.15 rounds on average; 7 came back identical
- remask ratio |M|/L: 20.3% per round, 43.7% cumulative
- affected-subgraph ratio |A(B)|/|V|: 23.7%
