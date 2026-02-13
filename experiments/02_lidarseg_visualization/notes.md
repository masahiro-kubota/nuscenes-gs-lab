# Experiment 02: LiDAR Segmentation Visualization - Notes

## 2026-02-14: LiDAR Projection Implementation (Part 1)

### masks.py 実装（投影機能）

`src/nuscenes_gs/masks.py` を作成し、以下の関数を実装：

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

## 2026-02-14: LiDAR Segmentation Data Pack Setup

### Step 1: nuScenes-lidarseg データパック取得 ✓

**実行内容**:
```bash
# データパック展開
tar -xjf ~/Downloads/nuScenes-lidarseg-mini-v1.0.tar.bz2 -C data/raw/
```

**確認結果**:
- ✓ lidarseg データパック検出成功
- ✓ 404 個の lidarseg ファイルを確認
- ✓ nuScenes から正しく読み込める
- Path: `lidarseg/v1.0-mini/`

## 2026-02-14: Streamlit での投影確認と検証完了 ✓

### Step 2: pose_viewer.py への LiDAR 可視化統合 ✓

**実装内容**:
- `scripts/pose_viewer.py` に LiDAR 投影機能を統合（lidarseg_viewer.pyは使用せず）
- 表示モード切り替え機能を追加（サイドバーのラジオボタン）
  - **Image Only**: 元画像のみ表示
  - **Image + LiDAR**: 2D画像にLiDARオーバーレイを合成
  - **LiDAR Only**: 3D点群をインタラクティブ表示
- 距離ベースのカラーマップを実装
  - 青（近距離） → 緑 → 黄 → 赤（遠距離）
  - 点のサイズ: 5px（視認性向上）
- Plotly による 3D 点群可視化
  - マウスで回転・ズーム可能
  - カメラ位置と視線方向を表示

**統計情報**:
- 投影点数: 約 5,000-8,000点/フレーム（元の点群の約20-30%）
- 距離範囲: 約 1m ~ 50m
- カメラ背後の点を除外（z > 0フィルタ）
- 画像境界外の点を除外

### Step 3: 投影精度の検証結果 ✓

**検証完了項目**:
- [x] lidarseg データパックが正しく読み込める（404ファイル確認済み）
- [x] LiDAR点群が正しく画像に投影される
  - 座標変換チェーン: lidar → ego → world → camera → 2D
  - OpenCV座標系での正確な投影を確認
- [x] 距離ベースで色分けされる（青→緑→黄→赤）
- [x] カメラ背後の点が除外される（z > 0フィルタ動作確認）
- [x] 画像境界外の点が除外される
- [x] 座標系の整合性が取れている
  - `compute_w2c()` を OpenCV 座標系に修正
  - 点群と画像の位置が正確に一致することを確認
- [x] 3D 点群の対話的可視化が動作する
  - Plotly による回転・ズーム動作確認
  - カメラ位置と視線方向の表示確認

**発見した問題と修正**:
1. **座標系の問題**: 初期実装では OpenGL 座標系を使用していたため、投影がずれていた
   - 修正: `compute_w2c()` を OpenCV 座標系に変更
2. **点のサイズ**: 初期は1px で見えなかった
   - 修正: 5px に拡大
3. **UIの複雑さ**: チェックボックスとラジオボタンが重複していた
   - 修正: ラジオボタンのみに統一

**結論**:
- LiDAR 点群の投影精度は良好
- 距離ベースのカラーマップにより、3次元情報が視覚的に理解しやすい
- 3D 点群ビューにより、カメラと点群の位置関係を確認可能
- **次のステップ**: Experiment 03 でマスク生成機能を実装
