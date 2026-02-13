# Experiment 05: Depth Supervision（LiDAR スパース深度拘束）

## 目的

LiDAR 静的点群をスパース深度として 3DGS 学習に組み込み、
遠景の漂い・地面のうねり・スケール不安定を抑制する。

## 背景

- Experiment 03/04 で動的オブジェクトのマスキングを完了済み
- マスクで動体は除去できたが、背景の幾何（特に遠景）は不安定
- roadmap Phase 3 に該当：「背景の形を安定化（幾何拘束）」
- nuScenes LiDAR は ~30m で密、50m+ で疎だが、スパース深度でも幾何の正則化に十分

## アプローチ

### スパース深度マップの生成

1. LiDAR keyframe 点群を読み込み
2. lidarseg で動的カテゴリ（vehicle/human/cycle）をフィルタ
3. 残った静的点を CAM_FRONT に投影
4. 各ピクセルに深度値を格納（疎な深度マップ）
5. 16-bit PNG または .npy で保存

### Nerfstudio への統合

Nerfstudio の depth supervision は `transforms.json` で以下を指定：

```json
{
  "frames": [
    {
      "file_path": "images/0001.jpg",
      "depth_file_path": "depth/0001.png",
      "transform_matrix": [...]
    }
  ],
  "depth_unit_scale_factor": 0.001
}
```

- `depth_file_path`: 深度マップへのパス
- `depth_unit_scale_factor`: ピクセル値 → メートルへの変換係数
- 16-bit PNG（値 0 = 深度なし）を使用

## 実装内容

### 1. depth.py の新規作成（深度マップ生成）

**ファイル**: `src/nuscenes_gs/depth.py`

**実装する関数**:
- `project_lidar_to_depth()` - 静的 LiDAR 点群 → スパース深度マップ
- `generate_depth_maps_for_scene()` - シーン全体のバッチ処理

**機能**:
- masks.py の `load_lidar_points_and_labels()` を再利用して点群読み込み
- 動的カテゴリをフィルタ（静的点のみ残す）
- カメラ座標系での深度（z 値）を計算
- 16-bit PNG に保存（depth_mm = depth_m * 1000）
- 深度範囲: 0.1m ~ 80m（nuScenes LiDAR の有効範囲）

### 2. nerfstudio_export.py の拡張

**ファイル**: `src/nuscenes_gs/nerfstudio_export.py`

**実装する関数**:
- `export_scene_front_with_depth()` - 深度付きエクスポート
- `export_scene_front_with_masks_and_depth()` - マスク＋深度付きエクスポート

**追加フィールド**:
- `depth_file_path` を各フレームに追加
- `depth_unit_scale_factor: 0.001` をトップレベルに追加

### 3. エクスポートスクリプト

**ファイル**: `scripts/export_front_with_depth.py`

**実行例**:
```bash
uv run python scripts/export_front_with_depth.py \
  --dataroot data/raw \
  --scene-index 4 \
  --mask-type lidar \
  --dilation 64
```

**出力**:
```
data/derived/scene-0757_front_depth/
├── images/
├── masks/          # オプション（--mask-type 指定時）
├── depth/          # スパース深度マップ（16-bit PNG）
└── transforms.json
```

### 4. 深度可視化の追加

**ファイル**: `scripts/pose_viewer.py` の拡張

**追加機能**:
- 深度マップのカラーマップ表示
- 深度カバレッジ率の表示
- 画像 + 深度オーバーレイ表示

### 5. 学習スクリプト

**ファイル**: `experiments/05_depth_supervision/run.sh`

**実行例**:
```bash
# Stage 1: マスクのみ（baseline）
bash experiments/05_depth_supervision/run.sh 4 1

# Stage 2: マスク + 深度拘束
bash experiments/05_depth_supervision/run.sh 4 2

# Stage 3: 深度拘束の重み調整
bash experiments/05_depth_supervision/run.sh 4 3
```

**Nerfstudio コマンド**:
```bash
ns-train splatfacto \
  --data data/derived/scene-0757_front_depth/ \
  --pipeline.model.depth-loss-mult 0.1 \
  --max-num-iterations 30000
```

## 検証項目

### Stage 0: 深度マップ生成
- [ ] 深度マップが生成される（depth/*.png）
- [ ] 深度値が妥当な範囲（0.1m ~ 80m）
- [ ] 動的オブジェクトが除外されている
- [ ] 深度カバレッジ率の確認（LiDAR が疎な領域は 0）
- [ ] Streamlit で深度オーバーレイ確認

### Stage 1: 深度なし baseline（マスクのみ）
- [ ] Experiment 03/04 と同等の PSNR
- [ ] 比較用の基準モデル確保

### Stage 2: 深度拘束あり学習
- [ ] Nerfstudio が depth_file_path を認識する
- [ ] 学習が正常に完了する
- [ ] 遠景の安定度が改善（ns-viewer で確認）
- [ ] 地面のうねりが改善
- [ ] PSNR 比較（depth あり vs なし）

### Stage 3: パラメータ調整
- [ ] depth-loss-mult の最適値探索（0.01, 0.1, 1.0）
- [ ] 深度範囲のクリッピング効果確認
- [ ] 最終品質の評価

## パラメータ

**デフォルト設定**:
- `depth_unit_scale_factor`: 0.001（16-bit PNG: mm → m）
- `depth_range`: [0.1, 80.0] メートル
- `depth-loss-mult`: 0.1（Nerfstudio デフォルト）
- `dynamic_categories`: ["vehicle.", "human.", "cycle."]

**調整可能**:
- `depth-loss-mult`: 深度拘束の重み（大きくすると幾何重視、小さくすると色重視）
- `depth_range`: 有効深度範囲

## 期待される効果

| 項目 | マスクのみ | マスク + 深度拘束 |
|------|-----------|------------------|
| **近景（~30m）** | 良好 | 同等～改善 |
| **遠景（50m+）** | 不安定（漂い） | 安定化 |
| **地面** | うねりあり | 平坦に改善 |
| **スケール** | 不安定な場合あり | 安定 |
| **学習時間** | 基準 | やや増加 |

## 成果物

- 深度マップ生成パイプライン完成
- depth.py（共通基盤に追加）
- 学習済みモデル（outputs/depth_stage*）
- マスクのみ vs マスク+深度 の比較結果
- 定性的評価（notes.md）

## 次のステップ

- Experiment 06: Multi-camera 統合（前方3カメラ）
- 深度拘束を multi-cam にも適用
