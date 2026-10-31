# graph_ans_noban_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 42.7% (+0.7%, 95% CI [-1.7%, +3.0%]) |
| reasoning consistency (no flagged step) | 20.7% | 27.0% |
| mean NFE | 256 | 656 (+400) |

fixed 8, broken 6 (exact McNemar p = 0.791)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 29.3%, hit token limit 2.0%, 36.6 s/problem
- answer format ('The answer is'): draft 74.0%, final 69.3%; accuracy among formatted 56.3% -> 60.1%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 146 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 201, re-denoised 287 per problem
- time per problem: draft 14.1 s + refine 22.4 s + parse/verify 0.34 s = 36.9 s; peak GPU memory 15.6 GiB
- <= 10 steps (n=102): 52% -> 53% (fixed 4, broken 3)
- 11-15 steps (n=103): 35% -> 37% (fixed 4, broken 2)
- > 15 steps (n=95): 39% -> 38% (fixed 0, broken 1)
- remasked: 79.3% of examples, 2.86 rounds on average; 132 came back identical
- remask ratio |M|/L: 65.4% per round, 187.2% cumulative
- affected-subgraph ratio |A(B)|/|V|: 66.7%
