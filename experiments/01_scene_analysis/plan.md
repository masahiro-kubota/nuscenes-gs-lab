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
uv run streamlit run scripts/lidarseg_viewer.py
```

## 検証項目

- [ ] シーン速度分析が正しく動作する
- [ ] 低速シーンが特定できる
- [ ] Streamlit アプリが起動する
- [ ] シーン・フレーム選択が動作する
- [ ] カメラ画像が表示される

## 成果物

- `scripts/analyze_scene_speed.py`
- `scripts/lidarseg_viewer.py`
- シーン速度分析結果（notes.md に記録）

## 次の実験

Experiment 02 で lidarseg データパックを取得し、LiDAR 投影を実装する。
