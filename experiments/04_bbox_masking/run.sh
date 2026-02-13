#!/bin/bash
set -euo pipefail

# Phase 1 (Experiment 04): 3D bbox masking 実験
# 使い方: bash experiments/04_bbox_masking/run.sh [scene_index] [stage]

SCENE_INDEX="${1:-4}"
STAGE="${2:-1}"

# CUDA 環境
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3
export MAX_JOBS=1

# シーン名マッピング（scene_index → scene_name）
# nuScenes mini の実際の順序に基づく
SCENE_NAMES=("scene-0061" "scene-0103" "scene-0553" "scene-0655" "scene-0757" "scene-0796" "scene-0916" "scene-1077" "scene-1094" "scene-1100")
SCENE_NAME="${SCENE_NAMES[$SCENE_INDEX]}"

echo "=== Experiment 04: 3D BBox Masking ==="
echo "Scene: $SCENE_NAME (index: $SCENE_INDEX)"
echo "Stage: $STAGE"
echo ""

# データディレクトリ
DATA_DIR="data/derived/${SCENE_NAME}_front_bbox_masked"

# Stage 0: データエクスポート（必要に応じて）
if [ ! -d "$DATA_DIR" ]; then
    echo "=== Stage 0: BBox マスク付きデータのエクスポート ==="
    uv run python scripts/export_front_with_bbox_masks.py \
      --dataroot data/raw \
      --scene-index "$SCENE_INDEX" \
      --dilation 5
    echo ""
fi

# Stage 1/2/3: 学習
if [ "$STAGE" -eq 1 ]; then
    echo "=== Stage 1: Quick test (1k iter, ~5-10min) ==="
    uv run ns-train splatfacto \
      --data "$DATA_DIR" \
      --max-num-iterations 1000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/bbox_stage1_quick_test

elif [ "$STAGE" -eq 2 ]; then
    echo "=== Stage 2: Light test (5k iter, ~20-30min) ==="
    uv run ns-train splatfacto \
      --data "$DATA_DIR" \
      --max-num-iterations 5000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/bbox_stage2_light

elif [ "$STAGE" -eq 3 ]; then
    echo "=== Stage 3: Full quality (30k iter, ~1-2h) ==="
    uv run ns-train splatfacto \
      --data "$DATA_DIR" \
      --max-num-iterations 30000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/bbox_stage3_full

else
    echo "Invalid stage: $STAGE (must be 1, 2, or 3)"
    exit 1
fi

# 学習完了後の処理
echo ""
echo "=== Training Complete ==="
CONFIG_PATH=$(ls -t outputs/bbox_stage${STAGE}_*/${SCENE_NAME}_front_bbox_masked/splatfacto/*/config.yml 2>/dev/null | head -1)
if [ -n "$CONFIG_PATH" ]; then
    echo "Latest config: $CONFIG_PATH"
    echo ""
    echo "To view results, run:"
    echo "  uv run ns-viewer --load-config $CONFIG_PATH"
else
    echo "Config file not found. Check outputs/ directory."
fi
