# Experiment 03: LiDAR Segmentation Masking - Notes

## 実験ログ

このファイルには、Experiment 03 の実行過程で得られた知見や結果を記録します。

---

## 2025-02-14: マスク生成とパラメータ調整

### 実装完了
- ✅ `src/nuscenes_gs/masks.py` - LiDAR 点群投影とマスク生成機能
- ✅ `src/nuscenes_gs/nerfstudio_export.py` - マスク付きエクスポート機能
- ✅ `scripts/export_front_with_lidar_masks.py` - CLI ツール
- ✅ `scripts/pose_viewer.py` - マスク可視化機能（Image + Mask モード追加）

### マスク生成パラメータの調整履歴

**テストシーン**: scene-0757（平均速度 5.0 km/h、停止率 60%、41 フレーム）

#### 初期実装（dilation=3）
- **結果**: マスクが点々として表示（連続領域にならない）
- **原因**: LiDAR 点が疎すぎて、各点を 1 ピクセルとして描画しても穴だらけ
- **対応**: 各点を半径 3 ピクセルの円として描画 + dilation=8 に変更

#### 第1回調整（dilation=8）
```bash
uv run python scripts/export_front_with_lidar_masks.py \
  --dataroot data/raw --scene-index 4 --dilation 8
```
- **結果**: 改善されたが、まだ断片的なマスク
- **評価**: 「うーんって感じ」（不十分）

#### 第2回調整（dilation=32）
```bash
uv run python scripts/export_front_with_lidar_masks.py \
  --dataroot data/raw --scene-index 4 --dilation 32
```
- **結果**: より連続的になったが、まだ満足できない
- **評価**: 改善したが、さらなる調整が必要

#### 第3回調整（dilation=64、最終版）
```bash
uv run python scripts/export_front_with_lidar_masks.py \
  --dataroot data/raw --scene-index 4 --dilation 64
```
- **結果**: 近距離の車両（~30m）は良好にマスクされる
- **マスクファイルサイズ**: 約 4-6 KB/フレーム（41 マスク生成済み）
- **出力ディレクトリ**: `data/derived/scene-0757_front_lidar_masked/`

### LiDAR ベースのマスク生成の限界

#### 確認された制約
1. **近距離（~30m）**: 良好にマスク可能
   - LiDAR 点密度が十分
   - dilation=64 で連続した領域を生成
   - 大型車両（バスなど）は特に良好

2. **遠距離（50m+）**: マスク不可
   - LiDAR 点が疎すぎる or 全く当たっていない
   - dilation を増やしても解決しない（点がないため）
   - 遠方の車両は静的背景として学習される可能性

#### 今後の改善案（Phase 2.1 として検討）
- **SAM (Segment Anything Model) 3** - プロンプト不要の汎用セグメンテーション
- **Mask2Former** - セマンティックセグメンテーション専用
- **GroundingDINO + SAM** - テキストプロンプト（"vehicle"）でセグメント

画像ベースのセグメンテーションモデルであれば、遠方の車両もマスク可能。

### 最終設定

**マスク生成パラメータ**:
- `point_radius=3` - 各 LiDAR 点を半径 3 ピクセルの円として描画
- `dilation_size=64` - モルフォロジー膨張カーネルサイズ
- `dynamic_classes` - デフォルト（vehicle.*, human.*, cycle.*）

**期待される効果**:
- 近距離の動的オブジェクトは精密にマスク → 背景の品質向上
- 遠距離の動的オブジェクトはマスクされない → baseline と同等

---

## 2025-02-14: マスク規約の問題と修正

### Stage 1 学習で発覚した問題

**実行**:
```bash
bash experiments/03_lidarseg_masking/run.sh 4 1
```

**結果**: 左側の静的な建物が全く描画されない（深刻な品質劣化）

### 原因分析

**診断手順**:
1. Streamlit でマスク確認 → 左側の建物はマスクされていない（期待通り）
2. マスクファイル分析:
   - フレーム 0000: 左半分カバレッジ 0.00%、右半分 11.70%
   - 全体: 平均左側 6.51%、右側 9.30%
3. Nerfstudio のマスク規約を調査 → **規約が逆だった**

**問題**:
- **我々の実装**: 0=学習対象、255=マスク（除外）
- **Nerfstudio の規約**: 0=除外、255=学習対象

そのため、左側の建物（マスク値 0）が「学習から除外」と解釈され、描画されなかった。

### 修正内容

**ファイル**: `src/nuscenes_gs/masks.py`

**変更点**:
```python
# モルフォロジー膨張の後にマスクを反転
mask = cv2.bitwise_not(mask)

# 動的点がない場合も修正
return np.full((h, w), 255, dtype=np.uint8)  # 全体を学習対象
```

**修正後のマスク**:
- 左半分: 学習対象 (255) が 100.00% ✓
- 右半分: 除外 (0) が 11.70% ✓

**再エクスポート**:
```bash
rm -rf data/derived/scene-0757_front_lidar_masked/masks
uv run python scripts/export_front_with_lidar_masks.py \
  --dataroot data/raw --scene-index 4 --dilation 64
```

### Stage 1 学習結果（修正後）

**実行**:
```bash
bash experiments/03_lidarseg_masking/run.sh 4 1
```

**結果**: ✓ 成功
- 左側の建物が正しく描画されることを確認
- マスク規約の修正が正しく機能
- パイプライン統合完了

---

## 次のステップ

1. ✓ **Stage 1 学習（1k iterations）** - パイプライン統合確認完了
2. **Stage 2 学習（5k iterations）** - baseline との比較
3. **Stage 3 学習（30k iterations）** - 最終品質評価
