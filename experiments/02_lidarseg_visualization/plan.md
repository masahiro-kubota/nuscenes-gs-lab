# Experiment 02: LiDAR Segmentation Visualization

## 目的

nuScenes-lidarseg データパックを使用して、LiDAR 点群を画像に投影し、
semantic segmentation の精度を確認する。

## 背景

- Experiment 01 で低速シーンを特定済み
- Phase 2 では LiDAR の semantic labels を使って動的オブジェクトをマスク
- 投影精度が重要（座標系・semantic label の正確性）

## 実装内容

### 1. データパック取得

**データ**: nuScenes-lidarseg v1.0-mini (~100MB)

**ダウンロード**:
- https://www.nuscenes.org/nuscenes#download
- v1.0-mini-lidarseg.tgz

**展開**:
```bash
tar -xzf ~/Downloads/v1.0-mini-lidarseg.tgz -C data/raw/
```

**確認**:
```bash
python3 -c "
from nuscenes.nuscenes import NuScenes
nusc = NuScenes(version='v1.0-mini', dataroot='data/raw', verbose=True)
sample = nusc.sample[0]
lidar_token = sample['data']['LIDAR_TOP']
lidarseg = nusc.get('lidarseg', lidar_token)
print(f'Lidarseg path: {lidarseg[\"filename\"]}')
"
```

### 2. masks.py 実装（投影機能）

**ファイル**: `src/nuscenes_gs/masks.py`

**実装する関数**:
- `load_lidar_points_and_labels()` - LiDAR データ読み込み
- `transform_lidar_to_world()` - LiDAR → world 座標変換
- `project_lidar_to_image()` - world → camera → 2D 投影
- （マスク生成は Experiment 03 で実装）

**座標変換チェーン**:
```
lidar frame → ego frame → world frame → camera frame → 2D image
```

### 3. Streamlit での投影確認

**更新ファイル**: `scripts/lidarseg_viewer.py`

**追加機能**:
- LiDAR 点群投影表示（全点、semantic 別カラーマップ）
- 動的点群のみ表示（vehicle/human/cycle）
- 統計情報（点数、semantic 分布）

**表示レイアウト**:
```
[元画像] [LiDAR全点投影]
[動的点のみ] [統計情報]
```

## 検証項目

- [ ] lidarseg データパックが正しく読み込める
- [ ] LiDAR 点群が正しく画像に投影される
- [ ] semantic label ごとに色分けされる
- [ ] 動的点（vehicle/human/cycle）が正しくフィルタされる
- [ ] カメラ背後の点が除外される
- [ ] 画像境界外の点が除外される
- [ ] 座標系の整合性が取れている

## 成果物

- `src/nuscenes_gs/masks.py`（投影機能）
- Streamlit での投影可視化
- 投影精度の検証結果（notes.md）

## 次の実験

Experiment 03 でマスク生成機能を実装し、Nerfstudio パイプラインに統合する。
