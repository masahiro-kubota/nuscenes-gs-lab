# Experiment 06: Multi-Camera Front 3（前方3カメラ統合）

## 目的

CAM_FRONT + CAM_FRONT_LEFT + CAM_FRONT_RIGHT の3カメラを統合し、
横方向の構造（建物側面、路肩、歩道）を安定的に再構築する。

## 背景

- Experiment 00〜05 は CAM_FRONT 単独で実験
- 単一カメラでは横方向の情報が不足し、画面端の再構築が不安定
- roadmap Phase 4 に該当：「マルチカメラ化」
- nuScenes は 6 カメラだが、まず前方 3 カメラ（FOV ~180°）から始める
- 各カメラは独立した intrinsics を持つ（同一モデルだが calibration が異なる）

## アプローチ

### nuScenes のカメラ構成

```
        CAM_FRONT_LEFT    CAM_FRONT    CAM_FRONT_RIGHT
              ↖               ↑               ↗
                          [ego車両]
              ↙               ↓               ↘
        CAM_BACK_LEFT     CAM_BACK     CAM_BACK_RIGHT
```

前方 3 カメラの FOV:
- CAM_FRONT: ~70° (正面)
- CAM_FRONT_LEFT: ~70° (左前方)
- CAM_FRONT_RIGHT: ~70° (右前方)
- 合計: ~180° の前方視野

### Nerfstudio での複数カメラ対応

Nerfstudio は `transforms.json` の frames 配列に異なる intrinsics のフレームを混在可能：

```json
{
  "frames": [
    {
      "file_path": "images/front_0001.jpg",
      "fl_x": 1266.4,
      "fl_y": 1266.4,
      "cx": 816.3,
      "cy": 491.5,
      "w": 1600,
      "h": 900,
      "transform_matrix": [...]
    },
    {
      "file_path": "images/front_left_0001.jpg",
      "fl_x": 1272.6,
      "fl_y": 1272.6,
      "cx": 826.6,
      "cy": 479.3,
      "w": 1600,
      "h": 900,
      "transform_matrix": [...]
    }
  ]
}
```

- トップレベルの共通 intrinsics を削除し、各フレームに個別指定
- `camera_model` は全カメラ共通で `OPENCV`

## 実装内容

### 1. nerfstudio_export.py の拡張（マルチカメラ対応）

**ファイル**: `src/nuscenes_gs/nerfstudio_export.py`

**実装する関数**:
- `export_scene_multicam()` - 複数カメラのエクスポート

**機能**:
- 対象カメラリストを引数で指定（デフォルト: FRONT, FRONT_LEFT, FRONT_RIGHT）
- 各カメラの calibrated_sensor から個別の intrinsics を取得
- フレームごとに fl_x, fl_y, cx, cy, w, h を付与
- ファイル名にカメラ名を含める（`front_0001.jpg`, `front_left_0001.jpg`）
- 既存の単一カメラ関数との互換性維持

### 2. masks.py の拡張（マルチカメラ対応）

**ファイル**: `src/nuscenes_gs/masks.py`

**追加・修正**:
- LiDAR マスク生成を任意のカメラに対応
- BBox マスク生成を任意のカメラに対応
- カメラ名をマスクファイル名に反映

### 3. depth.py の拡張（マルチカメラ対応）

**ファイル**: `src/nuscenes_gs/depth.py`

**追加・修正**:
- 深度マップ生成を任意のカメラに対応
- LiDAR → 各カメラへの投影

### 4. エクスポートスクリプト

**ファイル**: `scripts/export_multicam_front3.py`

**実行例**:
```bash
uv run python scripts/export_multicam_front3.py \
  --dataroot data/raw \
  --scene-index 4 \
  --mask-type lidar \
  --depth \
  --dilation 64
```

**出力**:
```
data/derived/scene-0757_front3/
├── images/
│   ├── front_0001.jpg
│   ├── front_left_0001.jpg
│   ├── front_right_0001.jpg
│   ├── front_0002.jpg
│   └── ...
├── masks/               # オプション
├── depth/               # オプション
└── transforms.json      # per-frame intrinsics
```

### 5. 学習スクリプト

**ファイル**: `experiments/06_multicam_front3/run.sh`

**実行例**:
```bash
# Stage 1: Front3 マスクなし（baseline）
bash experiments/06_multicam_front3/run.sh 4 1

# Stage 2: Front3 + マスク
bash experiments/06_multicam_front3/run.sh 4 2

# Stage 3: Front3 + マスク + 深度拘束
bash experiments/06_multicam_front3/run.sh 4 3
```

## 検証項目

### Stage 0: データエクスポート
- [ ] 3カメラの画像が正しくエクスポートされる
- [ ] 各カメラの intrinsics が正しい（個別に異なる）
- [ ] c2w 行列が各カメラ固有のものになっている
- [ ] transforms.json のフレーム数 = 単一カメラの約3倍
- [ ] Streamlit で3カメラの軌跡を確認（pose_viewer の拡張）

### Stage 1: マルチカメラ baseline
- [ ] Nerfstudio が per-frame intrinsics を認識する
- [ ] 学習が正常に完了する（1k → 5k → 30k）
- [ ] 単一カメラと比較して横方向が改善
- [ ] カメラ間の色の不整合が許容範囲内

### Stage 2: マスク付き学習
- [ ] 各カメラのマスクが正しく生成・適用される
- [ ] 動体除去がカメラ間で一貫している
- [ ] PSNR 比較（単一 vs 3カメラ）

### Stage 3: マスク + 深度付き学習
- [ ] 深度拘束が全カメラに適用される
- [ ] 最終品質の評価
- [ ] 単一カメラ / 3カメラ / 3カメラ+深度 の3種比較

## 注意点・課題

### 露出差
- nuScenes の各カメラは独立に露出調整されている
- 特に CAM_FRONT_LEFT/RIGHT は逆光や影の影響を受けやすい
- 必要に応じて簡易的な色正規化（ヒストグラムマッチング等）を検討

### 同期
- nuScenes の sample は全センサーの同期タイムスタンプ
- 各カメラの sample_data は同一 sample に紐づくため、厳密に同期済み

### 画像枚数の増加
- 単一カメラ: ~40 枚/シーン → 3カメラ: ~120 枚/シーン
- VRAM 使用量が増加するが、24GB GPU なら問題なし
- 学習時間は約2〜3倍に増加

### カメラ間のオーバーラップ
- 隣接カメラ間に若干のオーバーラップがある
- これは幾何の一貫性向上に寄与（正の効果）

## パラメータ

**デフォルト設定**:
- `cameras`: ["CAM_FRONT", "CAM_FRONT_LEFT", "CAM_FRONT_RIGHT"]
- `camera_model`: "OPENCV"（全カメラ共通）
- マスク・深度パラメータは Experiment 03〜05 と同一

## 期待される効果

| 項目 | 単一カメラ (FRONT) | 3カメラ (Front3) |
|------|-------------------|-----------------|
| **画面中央** | 良好 | 同等 |
| **画面端** | 不安定 | 改善（隣接カメラが補完） |
| **横方向の建物** | 不完全 | 安定化 |
| **視野角** | ~70° | ~180° |
| **画像枚数** | ~40枚 | ~120枚 |
| **学習時間** | 基準 | 2〜3倍 |

## 成果物

- マルチカメラエクスポートパイプライン完成
- nerfstudio_export.py のマルチカメラ対応
- 学習済みモデル（outputs/multicam_stage*）
- 単一カメラ / 3カメラ の比較結果
- 定性的評価（notes.md）

## 次のステップ

- 6カメラ（全方位）への拡張
- Phase 5: 穴埋め・再利用性向上
- 外部 GS 手法（Relightable GS, SU-RGS 等）への展開
