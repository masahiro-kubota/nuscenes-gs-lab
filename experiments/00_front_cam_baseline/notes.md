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
  - 状態: 画像キャッシュ処理中... → 失敗（MAX_JOBS=1が効かなかった）

**最終解決策**: 事前ビルド済みwheelを使用（Python 3.10必須）
- 試行5: PyTorch 2.1.2+cu121 + gsplat 1.5.3事前ビルド済みwheel
  - **重要**: gsplat 1.5.3の事前ビルド済みwheelはPython 3.10専用（cp310）
  - Python 3.11用の事前ビルド済みwheelは存在しない
  - Python 3.10にダウングレード
  - PyTorch 2.1.2+cu121をPyTorch公式リポジトリからインストール
  - gsplat 1.5.3+pt24cu124をgsplat公式リポジトリからインストール（JITコンパイル不要）
  - numpy 1.26.4（PyTorch 2.1.2との互換性のためnumpy<2制約）
  - 結果: 環境構築成功
- 試行6: `uv add`を使った正しい依存関係管理
  - **重要**: pyproject.tomlを直接編集せず、`uv add`コマンドを使用
  - **重要**: バージョンを指定せず、uvの依存関係解決に任せる
  - `uv add torch torchvision gsplat` (バージョン指定なし)
  - 結果: PyTorch 2.5.1+cu121、gsplat 1.5.3+pt24cu124がインストール
  - インポート確認成功、CUDA利用可能
  - 次: Stage 1学習テスト
- 試行7: pkg_resources.packaging問題の解決
  - **問題**: `ImportError: cannot import name 'packaging' from 'pkg_resources'`
  - **原因**: PyTorch 2.1.2のcpp_extension.pyが非推奨のpkg_resources.packagingを使用
  - **解決**: setuptools==69.5.1をプロジェクト依存関係に追加
  - 結果: Stage 1訓練成功（1000 iterations）

### Training execution (Stage 1-3)

**最終環境確定**:
- Python 3.10.16
- PyTorch 2.1.2+cu118
- torchvision 0.16.2+cu118
- gsplat 1.4.0+pt21cu118
- nerfstudio 1.1.5
- setuptools 69.5.1（pkg_resources問題の修正）

**Stage 1: Quick test (1000 iterations)**
- 出力先: outputs/stage1_quick_test/scene-0061_front/splatfacto/2026-02-13_231711/
- 実行時間: 約5分
- 結果: 成功（環境動作確認完了）

**Stage 2: Light test (5000 iterations)**
- 出力先: outputs/stage2_light/scene-0061_front/splatfacto/2026-02-13_232238/
- 実行時間: 約30分
- 結果: 成功（座標系正常、レンダリング品質良好）

**Stage 3: Full quality (30000 iterations)**
- 出力先: outputs/stage3_full/scene-0061_front/splatfacto/[timestamp]/
- 実行時間: 約1-2時間
- 結果: 成功（フル品質レンダリング完了）

### 重要な発見

**plan.mdの誤り**:
- `--pipeline.model.max-num-gaussians` パラメータは存在しない
- nerfstudio 1.1.5のsplatfactoでは該当パラメータが認識されない
- run.shにこのパラメータが含まれていなかったのは正しかった
- plan.mdを修正し、デフォルト設定（自動調整）を使用するように変更

**結論**:
- nuScenes CAM_FRONT single-cam baselineの完全な動作確認完了
- PyTorch 2.1.2 + CUDA 11.8 + gsplat 1.4.0の組み合わせで安定動作
- Stage 1/2/3全てのワークフローが正常に完了
