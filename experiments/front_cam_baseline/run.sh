#!/bin/bash
set -euo pipefail

# A' experiment: CAM_FRONT + given pose, single scene
# Usage: bash experiments/front_cam_baseline/run.sh [scene_index] [stage]
#   scene_index: 0-9 for mini dataset (default: 0 = scene-0061)
#   stage: 1, 2, or 3 (default: 1)

SCENE_INDEX="${1:-0}"
STAGE="${2:-1}"

# CUDA environment (required for gsplat)
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3
export MAX_JOBS=1  # Limit parallel compilation to avoid OOM during gsplat JIT build

# 1. Export
echo "=== Stage 0: Export data ==="
uv run python scripts/export_front_only.py \
  --dataroot data/raw \
  --scene-index "$SCENE_INDEX"

# Determine scene name (mini dataset scene names)
SCENE_NAMES=("scene-0061" "scene-0103" "scene-0655" "scene-0757" "scene-0796" "scene-0916" "scene-1077" "scene-1094" "scene-1100" "scene-0553")
SCENE_NAME="${SCENE_NAMES[$SCENE_INDEX]}"
DATA_DIR="data/derived/${SCENE_NAME}_front"

echo "Using scene: $SCENE_NAME"
echo "Data directory: $DATA_DIR"

# 2. Train
if [ "$STAGE" -eq 1 ]; then
  echo "=== Stage 1: Quick test (1k iter, ~5-10min) ==="
  uv run ns-train splatfacto \
    --data "$DATA_DIR" \
    --max-num-iterations 1000 \
    --viewer.quit-on-train-completion True \
    --output-dir outputs/stage1_quick_test
elif [ "$STAGE" -eq 2 ]; then
  echo "=== Stage 2: Light test (5k iter, ~20-30min) ==="
  uv run ns-train splatfacto \
    --data "$DATA_DIR" \
    --max-num-iterations 5000 \
    --viewer.quit-on-train-completion True \
    --output-dir outputs/stage2_light
elif [ "$STAGE" -eq 3 ]; then
  echo "=== Stage 3: Full quality (30k iter, ~1-2h) ==="
  uv run ns-train splatfacto \
    --data "$DATA_DIR" \
    --max-num-iterations 30000 \
    --viewer.quit-on-train-completion True \
    --output-dir outputs/stage3_full
else
  echo "Invalid stage: $STAGE (must be 1, 2, or 3)"
  exit 1
fi

# 3. Render (manual step after training)
echo ""
echo "=== Next: Render ==="
echo "Find your latest output directory in outputs/"
echo "Then run:"
echo "  uv run ns-viewer --load-config outputs/.../config.yml"
