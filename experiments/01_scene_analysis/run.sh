#!/bin/bash
set -euo pipefail

# Experiment 01: Scene Analysis - scene-0757 3DGS学習
# 使い方: bash experiments/01_scene_analysis/run.sh

echo "=== Experiment 01: Scene Analysis - scene-0757 3DGS Training ==="

# CUDA環境設定
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3
export MAX_JOBS=1

# データディレクトリ
DATA_DIR="data/derived/scene-0757_front"

# データ確認
if [ ! -d "$DATA_DIR" ]; then
  echo "Error: $DATA_DIR が見つかりません"
  echo "先に以下のコマンドでデータをエクスポートしてください："
  echo "  uv run python scripts/export_front_only.py --dataroot data/raw --scene-index 4"
  exit 1
fi

echo "Using data: $DATA_DIR"
echo "Frames: $(ls -1 $DATA_DIR/images/*.jpg 2>/dev/null | wc -l)"
echo ""

# 学習実行（30,000 iterations）
echo "=== Starting 3DGS Training (30,000 iterations) ==="
uv run ns-train splatfacto \
  --data "$DATA_DIR" \
  --max-num-iterations 30000 \
  --viewer.quit-on-train-completion True \
  --output-dir outputs/scene_analysis_scene0757

# 学習完了後の処理
echo ""
echo "=== Training Complete ==="
CONFIG_PATH=$(ls -t outputs/scene_analysis_scene0757/scene-0757_front/splatfacto/*/config.yml 2>/dev/null | head -1)

if [ -n "$CONFIG_PATH" ]; then
  echo "Latest config: $CONFIG_PATH"
  echo ""
  echo "結果を確認するには、以下のコマンドを実行してください："
  echo "  uv run ns-viewer --load-config $CONFIG_PATH"
else
  echo "Config file not found. Check outputs/ directory."
fi
