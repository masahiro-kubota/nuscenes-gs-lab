# Experiment 01: Scene Analysis

## 目的

nuScenes mini の各シーンの速度を分析し、マスク実験に最適な低速シーンを特定する。
また、LiDAR segmentation 可視化のための Streamlit アプリの基盤を作成する。

## 背景

- nuScenes mini には 10 シーンあるが、速度特性が異なる
- マスク実験では低速・停止が多いシーンが成功率が高い（2Hz サンプリングレート）
- 対話的な可視化ツールがあれば、データ確認が効率的

## 実装内容

### 1. シーン速度分析スクリプト

**ファイル**: `scripts/analyze_scene_speed.py`

**機能**:
- 各シーンの平均速度を計算（km/h）
- 停止割合を計算（速度 < 1.0 m/s）
- フレーム数をカウント
- 結果を表形式で表示

**実行**:
```bash
uv run python scripts/analyze_scene_speed.py --dataroot data/raw
```

### 2. Streamlit 可視化アプリ（初期版）

**ファイル**: `scripts/lidarseg_viewer.py`

**機能**:
- シーン選択（ドロップダウン）
- フレーム選択（スライダー）
- カメラ画像表示
- lidarseg データパック検出

**実行**:
```bash
uv run streamlit run scripts/pose_viewer.py
```

### 3. シーン選択と3DGS学習

**選択シーン**: scene-0757（減速シーン）

**理由**:
- 平均速度 5.0 km/h、停止率 60%
- 周囲の車両が少ない
- 減速パターンがあり、カメラの動き（視点変化）が適度にある
- GS再構築に必要な視点変化を確保しつつ、周囲の動体が少ない理想的なシーン

**データエクスポート**:
```bash
uv run python scripts/export_front_only.py --dataroot data/raw --scene-index 4
```

**3DGS学習（30,000 iterations）**:
```bash
# CUDA環境設定
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3
export MAX_JOBS=1

# 学習実行
uv run ns-train splatfacto \
  --data data/derived/scene-0757_front \
  --max-num-iterations 30000 \
  --viewer.quit-on-train-completion True \
  --output-dir outputs/scene_analysis_scene0757
```

**結果確認**:
```bash
# 学習完了後、最新のconfigを確認
CONFIG_PATH=$(ls -t outputs/scene_analysis_scene0757/scene-0757_front/splatfacto/*/config.yml 2>/dev/null | head -1)

# ビューアで確認
uv run ns-viewer --load-config $CONFIG_PATH
```

## 検証項目

### Phase 1: シーン分析
- [x] シーン速度分析が正しく動作する
- [x] 低速シーンが特定できる
- [x] Streamlit アプリが起動する
- [x] シーン・フレーム選択が動作する
- [x] カメラ画像が表示される
- [x] scene-0757 を選択・確認完了

### Phase 2: 3DGS学習（scene-0757）
- [ ] データエクスポートが完了する（41フレーム、1600×900）
- [ ] 30,000 iterations の学習が正常に完了する
- [ ] ビューアで再構築品質を確認できる
- [ ] 減速シーンでの3DGS再構築の品質を評価する

## 成果物

- `scripts/analyze_scene_speed.py`
- `scripts/lidarseg_viewer.py`
- シーン速度分析結果（notes.md に記録）
- **scene-0757 の 3DGS 学習済みモデル**（outputs/scene_analysis_scene0757/）

## 次の実験

scene-0757 での3DGS品質を確認後、Experiment 02 で lidarseg データパックを取得し、LiDAR 投影を実装する。
