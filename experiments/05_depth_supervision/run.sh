#!/bin/bash
set -euo pipefail

# Phase 3 (Experiment 05): Depth Supervision 実験
# 使い方: bash experiments/05_depth_supervision/run.sh [scene_index] [stage]

SCENE_INDEX="${1:-4}"
STAGE="${2:-1}"

# CUDA 環境
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3
export MAX_JOBS=1

# シーン名マッピング（scene_index → scene_name）
SCENE_NAMES=("scene-0061" "scene-0103" "scene-0553" "scene-0655" "scene-0757" "scene-0796" "scene-0916" "scene-1077" "scene-1094" "scene-1100")
SCENE_NAME="${SCENE_NAMES[$SCENE_INDEX]}"

echo "=== Experiment 05: Depth Supervision (LiDAR Sparse Depth) ==="
echo "Scene: $SCENE_NAME (index: $SCENE_INDEX)"
echo "Stage: $STAGE"
echo ""

# Stage 1: マスクのみ（baseline、深度なし）
if [ "$STAGE" -eq 1 ]; then
    DATA_DIR="data/derived/${SCENE_NAME}_front_lidar_masked"

    # データがなければエクスポート
    if [ ! -d "$DATA_DIR" ]; then
        echo "=== Stage 0: LiDAR マスク付きデータのエクスポート（深度なし）==="
        PYTHONPATH=$(pwd)/src:$PYTHONPATH \
          uv run python scripts/export_front_with_lidar_masks.py \
          --dataroot data/raw \
          --scene-index "$SCENE_INDEX" \
          --dilation 64
        echo ""
    fi

    echo "=== Stage 1: Baseline（マスクのみ、深度なし、30k iter）==="
    uv run ns-train splatfacto \
      --data "$DATA_DIR" \
      --max-num-iterations 30000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/depth_stage1_baseline

# Stage 2: マスク + 深度拘束
elif [ "$STAGE" -eq 2 ]; then
    DATA_DIR="data/derived/${SCENE_NAME}_front_depth_lidar_masked"

    # データがなければエクスポート
    if [ ! -d "$DATA_DIR" ]; then
        echo "=== Stage 0: マスク + 深度マップのエクスポート ==="
        PYTHONPATH=$(pwd)/src:$PYTHONPATH \
          uv run python scripts/export_front_with_depth.py \
          --dataroot data/raw \
          --scene-index "$SCENE_INDEX" \
          --mask-type lidar \
          --dilation 64 \
          --depth-range 0.1 80.0
        echo ""
    fi

    echo "=== Stage 2: マスク + 深度拘束（depth-loss-mult=0.1、30k iter）==="
    uv run ns-train depth-nerfacto \
      --data "$DATA_DIR" \
      --pipeline.model.depth-loss-mult 0.1 \
      --max-num-iterations 30000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/depth_stage2_with_depth

# Stage 3: 深度拘束の重み調整
elif [ "$STAGE" -eq 3 ]; then
    DATA_DIR="data/derived/${SCENE_NAME}_front_depth_lidar_masked"

    # データがなければエクスポート
    if [ ! -d "$DATA_DIR" ]; then
        echo "=== Stage 0: マスク + 深度マップのエクスポート ==="
        PYTHONPATH=$(pwd)/src:$PYTHONPATH \
          uv run python scripts/export_front_with_depth.py \
          --dataroot data/raw \
          --scene-index "$SCENE_INDEX" \
          --mask-type lidar \
          --dilation 64 \
          --depth-range 0.1 80.0
        echo ""
    fi

    echo "=== Stage 3: 深度拘束の重み調整（depth-loss-mult=1.0、30k iter）==="
    uv run ns-train depth-nerfacto \
      --data "$DATA_DIR" \
      --pipeline.model.depth-loss-mult 1.0 \
      --max-num-iterations 30000 \
      --viewer.quit-on-train-completion True \
      --output-dir outputs/depth_stage3_strong_depth

else
    echo "Invalid stage: $STAGE (must be 1, 2, or 3)"
    exit 1
fi

# 学習完了後の処理
echo ""
echo "=== Training Complete ==="
CONFIG_PATH=$(ls -t outputs/depth_stage${STAGE}_*/${SCENE_NAME}_*/splatfacto/*/config.yml 2>/dev/null | head -1)
if [ -n "$CONFIG_PATH" ]; then
    echo "Latest config: $CONFIG_PATH"
    echo ""
    echo "To view results, run:"
    echo "  uv run ns-viewer --load-config $CONFIG_PATH"
else
    echo "Config file not found. Check outputs/ directory."
fi
