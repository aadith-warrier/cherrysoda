
import glob
import os
import re

os.makedirs("configs/run/full", exist_ok=True)
METHODS = ("graph_remask", "full_remask", "full_resample", "graph_scheduled", "scheduled")
for path in sorted(glob.glob("configs/run/*_gsm8k_*.yaml")):
    if not os.path.basename(path).startswith(tuple(m + "_gsm8k_" for m in METHODS)):
        continue
    text = open(path).read()
    text = re.sub(r'^run_id:\s*"([^"]+)"', r'run_id: "\1_n1319"', text, flags=re.M)
    text = re.sub(r"^sample_size:.*$", "sample_size: full           # the whole test set (1,319)", text, flags=re.M)
    out = os.path.join("configs/run/full", os.path.basename(path).replace(".yaml", "_n1319.yaml"))
    open(out, "w").write(text)
    print("wrote", out)
