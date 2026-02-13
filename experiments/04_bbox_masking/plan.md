# Experiment 04: 3D BBox Masking

## 目的

nuScenes の 3D bounding box annotation を使って動的オブジェクトをマスクし、
クリーンな背景 Gaussian Splatting モデルを学習する。

## 背景

- Phase 0（front_cam_baseline）で CAM_FRONT + 与え姿勢で COLMAP なしに 3DGS 学習を完了
- Experiment 03（LiDAR segmentation masking）で精密なマスクを実装済み
- Phase 1（3D bbox masking）は LiDAR より実装が簡単で、データ追加も不要
- roadmap では Phase 1 をスキップしたが、bbox との比較のために実装

## アプローチ

- nuScenes の sample_annotation（3D bbox）を使用（追加ダウンロード不要）
- 3D bbox を 2D 画像に投影し、polygon を塗りつぶしてマスク生成
- transforms.json の `mask_path` フィールド経由で Nerfstudio に統合
- Experiment 03 と同じ学習パイプライン

## 実装内容

### 1. masks.py の拡張（bbox マスク生成）

**ファイル**: `src/nuscenes_gs/masks.py`

**実装した関数**:
- `project_bbox_to_mask()` - 単一 bbox → マスク
- `project_bboxes_to_mask()` - 1フレームの全 bbox → 統合マスク
- `generate_bbox_masks_for_scene()` - シーン全体のバッチ処理

**機能**:
- 3D bbox corners を 2D に投影
- Convex hull で polygon 作成
- Polygon を塗りつぶし（fillPoly）
- モルフォロジー膨張（dilation）適用
- バイナリマスク生成（Nerfstudio 規約: 0=exclude, 255=include）

### 2. nerfstudio_export.py の拡張

**ファイル**: `src/nuscenes_gs/nerfstudio_export.py`

**実装した関数**:
- `export_scene_front_with_bbox_masks()` - マスク付きエクスポート

### 3. エクスポートスクリプト

**ファイル**: `scripts/export_front_with_bbox_masks.py`

**実行例**:
```bash
uv run python scripts/export_front_with_bbox_masks.py \
  --dataroot data/raw \
  --scene-index 4 \
  --dilation 5
```

**出力**:
```
data/derived/scene-0757_front_bbox_masked/
├── images/
├── masks/
└── transforms.json
```

### 4. 学習スクリプト

**ファイル**: `experiments/04_bbox_masking/run.sh`

**実行例**:
```bash
# Stage 1: Quick test (1k iterations)
bash experiments/04_bbox_masking/run.sh 4 1

# Stage 2: Light test (5k iterations)
bash experiments/04_bbox_masking/run.sh 4 2

# Stage 3: Full quality (30k iterations)
bash experiments/04_bbox_masking/run.sh 4 3
```

## 検証項目

### Stage 0: マスク生成
- [x] マスクが生成される（masks/*.png）
- [x] マスクがバイナリ（0/255のみ）
- [x] マスクカバレッジ率が妥当
- [x] bbox が polygon として正しく塗りつぶされている
- [x] dilation が適用されている

### Stage 1: 簡易学習（1k iterations）
- [x] Nerfstudio がマスクを認識する
- [x] 学習が正常に完了する
- [x] エラーが発生しない

### Stage 2: 品質確認（5k iterations）
- [ ] Baseline と PSNR を比較（スキップ - Stage 3 へ直行）
- [ ] LiDAR masked と比較（スキップ - Stage 3 へ直行）
- [ ] ns-viewer で目視確認（スキップ - Stage 3 へ直行）
- [ ] マスク領域が再構築されていない（スキップ - Stage 3 へ直行）

### Stage 3: 最終品質（30k iterations）
- [x] フル品質レンダリング完了
- [ ] Baseline / LiDAR / BBox の3種類を比較（次のステップ）
- [ ] 定性的評価（notes.md に記録）（次のステップ）

## BBox vs LiDAR の比較

| 項目 | BBox (Phase 1) | LiDAR (Phase 2) |
|------|---------------|-----------------|
| **精密性** | 低（矩形全体） | 高（実際の点のみ） |
| **背景保護** | 低（過剰マスク） | 高（背景を保存） |
| **実装難易度** | 低 | 中 |
| **データ要件** | mini のみ | mini + lidarseg パック |
| **処理時間** | 速い | やや遅い |
| **遠方の車両** | カバー可能 | カバー困難（点が疎） |

**期待される結果**:
- BBox は LiDAR より広い領域をマスク（車両背後の背景も除外）
- LiDAR は近距離（~30m）で高精度、遠距離（50m+）で不足
- BBox は距離に関わらず一定のマスク精度

## パラメータ

**デフォルト設定**:
- `dynamic_categories`: ["vehicle.", "human.", "cycle."]
- `dilation_size`: 5 ピクセル

**調整可能**:
- コマンドライン引数で変更可能
- LiDAR (dilation=64) より小さい理由: bbox は既に大きめ

## 成果物

- BBox マスク付き学習パイプライン完成
- 学習済みモデル（outputs/bbox_stage*）
- Baseline / LiDAR / BBox の3種類の比較結果
- 定性的評価（notes.md）

## 次のステップ

- Phase 2.1: SAM など画像ベースのセグメンテーションモデル導入（遠方の車両対応）
- Phase 3: Multi-camera 統合（roadmap.md 参照）
