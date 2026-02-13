# Experiment 04: 3D BBox Masking - Notes

## 実験ログ

このファイルには、Experiment 04 の実行過程で得られた知見や結果を記録します。

---

## 2026-02-14: 実装とパイプライン統合

### 実装完了

- ✅ `src/nuscenes_gs/masks.py` - bbox 投影とマスク生成機能
  - `project_bbox_to_mask()` - 単一 bbox → マスク
  - `project_bboxes_to_mask()` - 1フレーム全 bbox → 統合マスク
  - `generate_bbox_masks_for_scene()` - シーン全体バッチ処理
- ✅ `src/nuscenes_gs/nerfstudio_export.py` - マスク付きエクスポート機能
- ✅ `scripts/export_front_with_bbox_masks.py` - CLI ツール
- ✅ `experiments/04_bbox_masking/run.sh` - 学習スクリプト

### マスク生成（scene-0757）

**実行**:
```bash
PYTHONPATH=/home/masahirokubota/nuscenes-gs-lab/src:$PYTHONPATH \
  uv run python scripts/export_front_with_bbox_masks.py \
  --dataroot data/raw --scene-index 4 --dilation 5
```

**結果**: ✓ 成功
- 41 フレーム分のマスク生成
- マスクサイズ: 約 4-5 KB/フレーム
- 出力ディレクトリ: `data/derived/scene-0757_front_bbox_masked/`

**パラメータ**:
- `dilation_size=5` - LiDAR (64) より小さい理由: bbox は既に大きめの領域をカバー
- `dynamic_categories=["vehicle.", "human.", "cycle."]` - デフォルト

### Stage 1 学習（1k iterations）

**実行**:
```bash
bash experiments/04_bbox_masking/run.sh 4 1
```

**結果**: ✓ 成功
- Nerfstudio がマスクを正しく認識
- エラーなく学習完了
- Config: `outputs/bbox_stage1_quick_test/scene-0757_front_bbox_masked/splatfacto/2026-02-14_034511/config.yml`

**確認事項**:
- [x] マスク読み込みエラーなし
- [x] 学習が正常に完了（1000 steps）
- [x] パイプライン統合成功

### Stage 3 学習（30k iterations）

**実行**:
```bash
bash experiments/04_bbox_masking/run.sh 4 3
```

**結果**: ✓ 成功
- フル品質学習完了（30000 steps）
- Config: `outputs/bbox_stage3_full/scene-0757_front_bbox_masked/splatfacto/2026-02-14_034836/config.yml`

**確認事項**:
- [x] 学習が正常に完了（30000 steps）
- [x] フル品質モデル生成完了

**ビューアで確認**:
```bash
uv run ns-viewer --load-config outputs/bbox_stage3_full/scene-0757_front_bbox_masked/splatfacto/2026-02-14_034836/config.yml
```

---

## 完了ステータス

1. ✓ **Stage 0: マスク生成** - 完了
2. ✓ **Stage 1 学習（1k iterations）** - 完了
3. **Stage 2 学習（5k iterations）** - スキップ（Stage 3 へ直行）
4. ✓ **Stage 3 学習（30k iterations）** - 完了

## 比較実験の準備

**3つのバージョンを比較する**:
1. **Baseline**: マスクなし（`experiments/front_cam_baseline`）
2. **LiDAR**: LiDAR segmentation マスク（`experiments/03_lidarseg_masking`）
3. **BBox**: 3D bbox マスク（`experiments/04_bbox_masking`）- 今回

**予想される違い**:
- BBox は LiDAR より広い領域をマスク（車両背後の背景も除外される可能性）
- LiDAR は近距離で精密、遠距離で不足
- BBox は距離に関わらず一定のカバレッジ
