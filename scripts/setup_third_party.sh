#!/bin/bash
# Clone the official RemeDi, ProSeCo and DAPD code at pinned commits into third_party/.
# We run their samplers unmodified; nothing from these repos is copied into our code.
# Run from the repo root.
set -e
mkdir -p third_party

clone_pinned () {  # url dir commit
  if [ ! -d "third_party/$2/.git" ]; then
    git clone -q "$1" "third_party/$2"
  fi
  git -C "third_party/$2" fetch -q origin "$3" 2>/dev/null || true
  git -C "third_party/$2" checkout -q "$3"
  echo "OK: third_party/$2 @ $(git -C "third_party/$2" rev-parse --short HEAD)"
}

# RemeDi (Huang et al., ICLR 2026): inference.py + remedi/ model code. No license file in the repo.
clone_pinned https://github.com/maple-research-lab/RemeDi.git RemeDi 2e1b19d34db09e345898f6c5b6ed60418659821a
# ProSeCo (Schiff et al., 2026): llada/generate.py is the corrector sampler. Apache-2.0.
clone_pinned https://github.com/kuleshov-group/proseco.git proseco 43ce881779f06f475b56d90a152acd65ddc74fe4
# DAPD (Kim et al., ICML 2026): dapd/ package (LLaDA + Dream generation). MIT.
clone_pinned https://github.com/quasar529/DAPD.git DAPD 05727b08da4cb4008a275123d7d9885dd5714f7c
