# A' experiment: CAM_FRONT + given pose

## Overview

nuScenes mini の 1シーンから CAM_FRONT のみ抽出し、splatfacto で学習する最小 PoC。

## 2026-02-13: initial setup and export

### Environment setup
- nuScenes mini v1.0をdata/raw/に展開（5.1GB）
- Python依存関係インストール:
  - PyTorch 2.10.0 + CUDA 12.8
  - Nerfstudio 1.1.5
  - gsplat 1.4.0 (initially 1.5.3, downgraded due to JIT compilation memory issues)
- CUDA環境変数設定が必要: `CUDA_HOME=/usr/local/cuda-12.3`

### Data export
- scene-0061 を export（39 frames, 1600x900）
- transforms.json 生成確認済み
  - rotation det=1.0, orthogonality ~1e-15
  - camera height Z ≈ 1.5m
  - fl_x=1266.4, fl_y=1266.4
- 出力先: data/derived/scene-0061_front/

### Training preparation (Stage 1)

#### gsplatコンパイル問題の調査

**問題**: gsplat JITコンパイルがメモリ不足で失敗

**原因究明**:
- 試行1: gsplat 1.5.3 → nvccがkilled（exit code 137 = OOM killer）
- 試行2: gsplat 1.4.0にダウングレード → 同じ問題
- メモリ調査結果:
  - 物理RAM: 32GB、空きメモリ: 24GB（十分なはず）
  - **しかし**: journalctlでOOM killer発動を確認
  - Chrome、VS Code、Cursorなど複数プロセスが同時にkilled
  - スワップ: 2GBのみ（1.7GB使用済み）
  - nvcc並列コンパイル（ninja -j 10）が一時的に10GB以上消費
  - システム全体: 使用メモリ + nvcc並列コンパイル > 物理RAM + スワップ

**gsplatコンパイルが必要な理由**:
- gsplatはCUDA拡張を含むPyTorchライブラリ
- PyTorch 2.10.0 + CUDA 12.8用の事前ビルド済みwheelが存在しない
- ソースコードのみ配布 → 初回実行時にJITコンパイルが発生
- `nerfstudio`のインストールは成功しても、`ns-train`実行時にコンパイルが必要

**対処**: `MAX_JOBS=1`で並列度を1に制限
- 試行3: `export MAX_JOBS=1 && uv pip install gsplat==1.4.0` → インストール成功
- 試行4: Stage 1学習開始（1000 iterations、MAX_JOBS=1設定）
  - 出力先: outputs/stage1_quick_test/scene-0061_front/splatfacto/2026-02-13_222128/
  - 状態: 画像キャッシュ処理中...
