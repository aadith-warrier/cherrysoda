# graph_ans_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 45.7% (+3.7%, 95% CI [-3.3%, +10.3%]) |
| reasoning consistency (no flagged step) | 20.7% | 44.0% |
| mean NFE | 256 | 620 (+364) |

fixed 63, broken 52 (exact McNemar p = 0.351)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 33.3%, hit token limit 2.0%, 35.2 s/problem
- answer format ('The answer is'): draft 74.0%, final 65.0%; accuracy among formatted 56.3% -> 68.7%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 91 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 202, re-denoised 284 per problem
- time per problem: draft 14.1 s + refine 21.1 s + parse/verify 0.33 s = 35.6 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 52% (fixed 25, broken 25)
- 11-15 steps (n=103): 35% -> 45% (fixed 23, broken 13)
- > 15 steps (n=95): 39% -> 40% (fixed 15, broken 14)
- remasked: 79.3% of examples, 2.60 rounds on average; 48 came back identical
- remask ratio |M|/L: 66.3% per round, 172.6% cumulative
- affected-subgraph ratio |A(B)|/|V|: 67.3%
