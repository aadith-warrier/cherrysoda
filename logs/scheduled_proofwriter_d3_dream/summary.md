# scheduled_proofwriter_d3_dream

dream_7b, method `scheduled`, 1 token(s) per active step per pass, n = 150

| | draft | after scheduling |
|---|---|---|
| accuracy | 41.3% | 39.3% (-2.0%, 95% CI [-10.7%, +7.3%]) |
| reasoning consistency (no flagged step) | 38.0% | 32.0% |
| mean NFE | 256 | 383 (+127) |

fixed 23, broken 26 (exact McNemar p = 0.775)

- examples with a flagged step: 67 wrong, 26 right drafts
- no answer 37.3%, hit token limit 0.7%, 21.1 s/problem
- answer format ('The answer is'): draft 72.7%, final 60.7%; accuracy among formatted 56.0% -> 61.5%
- verifier in situ: graphs parsed cleanly 100.0%, 11.9 steps per answer; a flag means a wrong draft 72.0% of the time; 21 wrong drafts never flagged, 49 flagged but still wrong; flags by type {'unsupported': 92, 'unsupported_premise': 203, 'hallucinated_rule': 252, 'false_premise': 37, 'missed_inference': 4, 'contradiction': 9}
- tokens: draft 194, final 205, re-denoised 256 per problem
- time per problem: draft 14.1 s + refine 7.0 s + parse/verify 0.20 s = 21.3 s; peak GPU memory 15.4 GiB
- <= 10 steps (n=51): 51% -> 35% (fixed 4, broken 12)
- 11-16 steps (n=57): 35% -> 35% (fixed 10, broken 10)
- > 16 steps (n=42): 38% -> 50% (fixed 9, broken 4)
- scheduled pass: 127 NFE (2.46 tokens per pass, 7.1 dependency levels); 0 examples left as drafted
