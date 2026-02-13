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

### 次のステップ

**Step 1: nuScenes-lidarseg データパック取得**

Experiment 02を進めるには、lidarsegデータパックが必要です：

```bash
# nuScenes ダウンロードページから取得
# https://www.nuscenes.org/nuscenes#download
# v1.0-mini-lidarseg.tgz (~100MB) をダウンロード

# 展開
tar -xzf ~/Downloads/v1.0-mini-lidarseg.tgz -C data/raw/

# 確認
python3 -c "
from nuscenes.nuscenes import NuScenes
nusc = NuScenes(version='v1.0-mini', dataroot='data/raw', verbose=True)
sample = nusc.sample[0]
lidar_token = sample['data']['LIDAR_TOP']
lidarseg = nusc.get('lidarseg', lidar_token)
print(f'Lidarseg path: {lidarseg[\"filename\"]}')
"
```

**Step 2: Streamlit での投影確認**

データパック取得後、`scripts/lidarseg_viewer.py` を更新してLiDAR投影を表示：
- 全点投影（semantic別カラーマップ）
- 動的点のみ投影
- 統計情報表示

**Step 3: 投影精度の検証**

- [ ] lidarseg データパックが正しく読み込める
- [ ] LiDAR点群が正しく画像に投影される
- [ ] Semantic labelごとに色分けされる
- [ ] 動的点（vehicle/human/cycle）が正しくフィルタされる
- [ ] カメラ背後の点が除外される
- [ ] 画像境界外の点が除外される
- [ ] 座標系の整合性が取れている
