# Experiment 02: LiDAR Segmentation Visualization

## 目的

nuScenes-lidarseg データパックを使用して、LiDAR 点群を画像に投影し、
semantic segmentation の精度を確認する。

## 背景

- Experiment 01 で低速シーンを特定済み
- Phase 2 では LiDAR の semantic labels を使って動的オブジェクトをマスク
- 投影精度が重要（座標系・semantic label の正確性）

## 実装内容

### 1. データパック取得 ✓

**データ**: nuScenes-lidarseg v1.0-mini (~100MB)

**ステータス**: 完了 ✓
- ファイル: `nuScenes-lidarseg-mini-v1.0.tar.bz2`
- 展開済み: `data/raw/lidarseg/v1.0-mini/`
- 404 個の lidarseg ファイルを確認

**実行コマンド**:
```bash
tar -xjf ~/Downloads/nuScenes-lidarseg-mini-v1.0.tar.bz2 -C data/raw/
```

**確認済み**:
- ✓ nuScenes から正しく読み込める
- ✓ Path: `lidarseg/v1.0-mini/`

### 2. masks.py 実装（投影機能）✓

**ファイル**: `src/nuscenes_gs/masks.py`

**ステータス**: 完了 ✓

**実装済み関数**:
- `load_lidar_points_and_labels()` - LiDAR点群とsemantic labelsの読み込み
- `transform_lidar_to_world()` - LiDAR → ego → world 座標変換
- `project_points_to_image()` - World → camera → 2D投影
- `create_label_overlay()` - Semantic labelに基づくカラーマップオーバーレイ生成
- `compute_w2c()` - World-to-camera行列計算

**座標変換チェーン**:
```
lidar frame → ego frame → world frame → camera frame → 2D image
```

**実装の特徴**:
- 既存の `poses.py` の `make_transform()` と `compute_c2w()` を再利用
- カメラ背後の点をフィルタ（z > 0）
- 画像境界外の点をフィルタ
- Semantic label別のカラーマップ（動的: 赤系、静的: 青/緑系）

### 3. Streamlit での投影確認 ✓

**更新ファイル**: `scripts/pose_viewer.py`（既存ビューアに統合）

**ステータス**: 完了 ✓

**実装した機能**:
- LiDAR 点群投影表示（距離ベースのカラーマップ：青→緑→黄→赤）
- 3D 点群ビュー（インタラクティブに回転可能）
- 表示モード切り替え（Image Only / Image + LiDAR / LiDAR Only）
- 統計情報（投影点数、距離範囲）

**表示レイアウト**:
```
[軌跡プロット] [画像 or 3D点群]
```

**実装内容**:
- `masks.py` の関数を使用
- `load_lidar_points_and_labels()` で LiDAR データ読み込み
- `transform_lidar_to_world()` で座標変換
- `project_points_to_image()` で 2D 投影
- `create_label_overlay()` で距離ベースのカラーマップ生成
- Plotly で 3D 点群の対話的可視化

## 検証項目

### Step 1-2: 基盤準備
- [x] lidarseg データパックが正しく読み込める
- [x] masks.py の投影機能が実装されている

### Step 3: Streamlit での投影確認
- [x] LiDAR 点群が正しく画像に投影される
- [x] 距離ベースで色分けされる（青→緑→黄→赤）
- [x] カメラ背後の点が除外される（z > 0 フィルタ）
- [x] 画像境界外の点が除外される
- [x] 座標系の整合性が取れている（OpenCV座標系で正しく投影）
- [x] 3D 点群の対話的可視化が動作する

## 成果物

### 完了済み
- ✓ `src/nuscenes_gs/masks.py`（投影機能）
  - LiDAR点群の読み込みと座標変換
  - 2D投影とカラーマップ生成
  - OpenCV座標系での正確な投影
- ✓ lidarseg データパック取得・展開
- ✓ `scripts/pose_viewer.py` への LiDAR 可視化統合
  - 3つの表示モード（Image Only / Image + LiDAR / LiDAR Only）
  - 距離ベースのカラーマップ（青→緑→黄→赤）
  - 3D 点群の対話的可視化（Plotly）
- ✓ 投影精度の検証結果（notes.md に記録）

## 次の実験

Experiment 03 でマスク生成機能を実装し、Nerfstudio パイプラインに統合する。
