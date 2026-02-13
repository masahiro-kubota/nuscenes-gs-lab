#!/bin/bash
set -euo pipefail

# A' experiment: CAM_FRONT + given pose, single scene
# Usage: bash experiments/a_prime/run.sh [scene_index]

SCENE_INDEX="${1:-0}"

# 1. Export
uv run python scripts/export_front_only.py \
  --dataroot data/raw \
  --scene-index "$SCENE_INDEX"

# 2. Train (uncomment when ready)
# ns-train splatfacto --data data/derived/scene-XXXX_front

# 3. Render (uncomment when ready)
# ns-render camera-path --load-config outputs/...
