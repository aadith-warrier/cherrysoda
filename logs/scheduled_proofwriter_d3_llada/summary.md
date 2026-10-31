# scheduled_proofwriter_d3_llada

llada_8b, method `scheduled`, 1 token(s) per active step per pass, n = 150

| | draft | after scheduling |
|---|---|---|
| accuracy | 72.7% | 59.3% (-13.3%, 95% CI [-22.7%, -4.0%]) |
| reasoning consistency (no flagged step) | 70.0% | 20.0% |
| mean NFE | 256 | 334 (+78) |

fixed 16, broken 36 (exact McNemar p = 0.008)

- examples with a flagged step: 24 wrong, 21 right drafts
- no answer 0.7%, hit token limit 0.0%, 22.3 s/problem
- answer format ('The answer is'): draft 100.0%, final 92.7%; accuracy among formatted 72.7% -> 62.6%
- verifier in situ: graphs parsed cleanly 100.0%, 14.0 steps per answer; a flag means a wrong draft 53.3% of the time; 17 wrong drafts never flagged, 17 flagged but still wrong; flags by type {'contradiction': 5, 'false_premise': 3, 'unsupported': 37, 'unsupported_premise': 24, 'hallucinated_rule': 23, 'missed_inference': 3}
- tokens: draft 244, final 252, re-denoised 256 per problem
- time per problem: draft 17.1 s + refine 5.2 s + parse/verify 0.01 s = 22.3 s; peak GPU memory 14.9 GiB
- <= 12 steps (n=59): 81% -> 58% (fixed 6, broken 20)
- 13-16 steps (n=45): 69% -> 58% (fixed 3, broken 8)
- > 16 steps (n=46): 65% -> 63% (fixed 7, broken 8)
- scheduled pass: 78 NFE (3.49 tokens per pass, 4.4 dependency levels); 0 examples left as drafted
