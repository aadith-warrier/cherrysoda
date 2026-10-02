# study_llada_paper_noblock_250

250 problems from `configs/dataset/gsm8k_paper.yaml`, model `configs/model/llada_8b.yaml`.

| variant | length | steps | block | tok/round | accuracy | no answer | hit limit | answer tokens | s/problem | graph steps | equations | unsourced | extras |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| paperprompt_len256_blkoff_eoslast | 256 | 256 | off | 1 | 66% | 0% | 0% | 253 | 64.3 | 9.6 | 4.2 | 0.97 | confidence_eos_eot_inf |
