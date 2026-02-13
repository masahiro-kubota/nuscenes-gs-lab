# Experiment 03: LiDAR Segmentation Masking

## 目的

LiDAR segmentation を使って動的オブジェクトをマスクし、
クリーンな背景 Gaussian Splatting モデルを学習する。

## 背景

- Experiment 01 で低速シーン（scene-0061 など）を特定済み
- Experiment 02 で LiDAR 投影の精度を確認済み
- Phase 0（front_cam_baseline）でマスクなし学習を完了済み

## 実装内容

### 1. masks.py の拡張（マスク生成）

**ファイル**: `src/nuscenes_gs/masks.py`

**追加する関数**:
- `project_lidar_to_mask()` - LiDAR 点群から 2D マスク生成
- `generate_lidar_masks_for_scene()` - シーン全体のマスク生成

**機能**:
- 動的点を 2D ピクセルにラスタライズ
- モルフォロジー膨張（dilation）適用
- バイナリマスク生成（0=学習, 255=マスク）

### 2. nerfstudio_export.py の拡張

**ファイル**: `src/nuscenes_gs/nerfstudio_export.py`

**追加する関数**:
- `export_scene_front_with_lidar_masks()` - マスク付きエクスポート

**機能**:
- 画像エクスポート
- マスク生成・保存
- transforms.json に `mask_path` フィールド追加

### 3. エクスポートスクリプト作成・実行

**ファイル**: `scripts/export_front_with_lidar_masks.py`

**実行**:
```bash
uv run python scripts/export_front_with_lidar_masks.py \
  --dataroot data/raw \
  --scene-index 0 \
  --dilation 3
```

**出力**:
```
data/derived/scene-0061_front_lidar_masked/
├── images/
├── masks/
└── transforms.json
```

### 4. Streamlit でマスク確認

**更新ファイル**: `scripts/lidarseg_viewer.py`

**追加機能**:
- 生成されたマスク画像を表示
- マスクカバレッジ率を計算
- マスクオーバーレイ表示

### 5. 学習と評価

**実行スクリプト**: `experiments/03_lidarseg_masking/run.sh`

**学習ステージ**:
- Stage 1: 1k iterations（環境確認）
- Stage 2: 5k iterations（品質確認）
- Stage 3: 30k iterations（最終品質）

**比較**:
- Baseline（マスクなし）vs LiDAR masked
- PSNR, ns-viewer での目視確認
- 背景品質（道路、建物）
- マスク精度（車両背後の背景が保護されているか）

## 検証項目

### Stage 0: マスク生成 ✓
- [x] マスクが生成される（masks/*.png）- 41 フレーム分生成済み
- [x] マスクがバイナリ（0/255のみ）
- [x] マスクカバレッジ率が妥当（scene-0757 は車両が少ないため低め）
- [x] dilation が適用されている（最終値: dilation=64）
- [x] Streamlit でマスク確認完了（Image + Mask モード）

**完了シーン**: scene-0757（scene-index 4）
- マスク生成パラメータ: point_radius=3, dilation=64
- 出力ディレクトリ: `data/derived/scene-0757_front_lidar_masked/`
- マスク品質: 近距離（~30m）は良好、遠距離（50m+）は LiDAR 点が疎すぎてカバー不可

### Stage 1: 簡易学習（1k iterations）
- [ ] Nerfstudio がマスクを認識する
- [ ] 学習が正常に完了する
- [ ] エラーが発生しない

### Stage 2: 品質確認（5k iterations）
- [ ] Baseline と PSNR を比較
- [ ] ns-viewer で目視確認
- [ ] マスク領域が再構築されていない
- [ ] 背景品質が同等または改善

### Stage 3: 最終品質（30k iterations）
- [ ] フル品質レンダリング完了
- [ ] Before/After スクリーンショット比較
- [ ] 定性的評価（notes.md に記録）

## 成果物

- マスク付き学習パイプライン完成
- 学習済みモデル（outputs/lidarseg_stage*）
- 品質比較結果（notes.md）
- Before/After スクリーンショット

## 次のステップ

- Phase 3: Multi-camera 統合（roadmap.md 参照）
- または Phase 2.1: panoptic への拡張
