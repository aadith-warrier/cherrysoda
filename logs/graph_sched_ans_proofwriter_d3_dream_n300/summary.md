# graph_sched_ans_proofwriter_d3_dream_n300

dream_7b, method `remask`, mode `graph`, max_rounds 3, temperature None, n = 300

| | draft | after remasking |
|---|---|---|
| accuracy | 42.0% | 44.3% (+2.3%, 95% CI [-4.3%, +8.7%]) |
| reasoning consistency (no flagged step) | 20.7% | 52.7% |
| mean NFE | 256 | 449 (+193) |

fixed 57, broken 50 (exact McNemar p = 0.562)

- examples with a flagged step: 154 wrong, 84 right drafts
- no answer 40.3%, hit token limit 2.0%, 25.1 s/problem
- answer format ('The answer is'): draft 74.0%, final 56.3%; accuracy among formatted 56.3% -> 75.7%
- verifier in situ: graphs parsed cleanly 100.0%, 12.0 steps per answer; a flag means a wrong draft 64.7% of the time; 20 wrong drafts never flagged, 97 flagged but still wrong; flags by type {'unsupported': 214, 'unsupported_premise': 499, 'hallucinated_rule': 439, 'unsupported_answer': 160, 'false_premise': 73, 'missed_inference': 14, 'contradiction': 43}
- tokens: draft 195, final 183, re-denoised 233 per problem
- time per problem: draft 14.1 s + refine 11.0 s + parse/verify 0.30 s = 25.4 s; peak GPU memory 15.4 GiB
- <= 10 steps (n=102): 52% -> 42% (fixed 16, broken 26)
- 11-15 steps (n=103): 35% -> 43% (fixed 20, broken 12)
- > 15 steps (n=95): 39% -> 48% (fixed 21, broken 12)
- remasked: 79.3% of examples, 2.49 rounds on average; 13 came back identical
- remask ratio |M|/L: 62.3% per round, 154.9% cumulative
- affected-subgraph ratio |A(B)|/|V|: 63.4%
