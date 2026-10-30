pixi run python -m scripts.run_graph_method --config configs/run/graph_scheduled_proofwriter_d3_llada.yaml --device cuda:0   # ~10 min: only the 45 flagged problems
pixi run python -m scripts.run_graph_method --config configs/run/scheduled_proofwriter_d3_llada.yaml --device cuda:0         # ~45 min: re-denoises all 150
pixi run python -m scripts.compare_methods \
    --runs logs/graph_remask_proofwriter_d3_llada logs/graph_scheduled_proofwriter_d3_llada logs/scheduled_proofwriter_d3_llada logs/full_remask_proofwriter_d3_llada \
    --names graph graph+sched sched full --out results/compare_proofwriter_llada_all
pixi run python -m scripts.analyze_proofwriter_remask logs/graph_remask_proofwriter_d3_llada logs/graph_scheduled_proofwriter_d3_llada