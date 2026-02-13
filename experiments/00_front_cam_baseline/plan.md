いい選択です。
**A’（CAM_FRONT + 与え姿勢GS）**を、nuScenes前提で“詰まらない順番”に落とします。

対象：nuScenes
使う：CAM_FRONT / ego_pose / calibrated_sensor
やらない：COLMAP / マスク / LiDAR拘束

---

# 全体フロー（最短PoC）

```
1. miniデータ取得
2. CAM_FRONTだけ抽出
3. world→cam行列生成
4. Nerfstudio形式に変換
5. Splatfactoで学習
6. レンダ確認
```

---

# STEP 0：miniで開始（絶対にmini）

* Full dataset → Mini（3.88GB）
* 10 scenesだけ

```bash
pip install nuscenes-devkit
```

---

# STEP 1：1シーンだけ使う

まずは **1 sceneだけ**。

```python
from nuscenes.nuscenes import NuScenes
nusc = NuScenes(version="v1.0-mini", dataroot="path/to/data")

scene = nusc.scene[0]
first_sample_token = scene["first_sample_token"]
```

---

# STEP 2：CAM_FRONTの画像とposeを取得

各 sample を辿る：

```python
sample = nusc.get("sample", first_sample_token)

while True:
    cam_token = sample["data"]["CAM_FRONT"]
    cam_data = nusc.get("sample_data", cam_token)

    ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
    calib = nusc.get("calibrated_sensor", cam_data["calibrated_sensor_token"])

    # 画像パス
    img_path = cam_data["filename"]

    if sample["next"] == "":
        break
    sample = nusc.get("sample", sample["next"])
```

---

# STEP 3：world→camera行列を作る（重要）

nuScenesの座標構造：

```
world → ego → camera
```

### 1) world → ego

```python
T_world_ego
```

* ego_pose["translation"]
* ego_pose["rotation"] (quaternion)

---

### 2) ego → camera

```python
T_ego_cam
```

* calibrated_sensor["translation"]
* calibrated_sensor["rotation"]

---

### 3) world → camera

```python
T_world_cam = T_ego_cam @ T_world_ego
```

※回転はクォータニオン→回転行列変換必須

---

## ⚠ 座標系注意（ここ重要）

nuScenes：

* x 前
* y 左
* z 上

Nerfstudio：

* OpenGL系
* x 右
* y 上
* z 後ろ

なので **座標変換マトリクスを1枚挟む必要あり**。

最初は：

> とりあえずOpenCV系座標で出して、Nerfstudio側の transforms.json に合わせる

でOK。
ここでハマる人が9割です。

---

# STEP 4：Nerfstudio形式に変換

インストール：

```bash
pip install nerfstudio
```

使うモデル：

* **splatfacto**

必要ファイル：

```
images/
transforms.json
```

transforms.json例：

```json
{
  "camera_model": "OPENCV",
  "fl_x": ...,
  "fl_y": ...,
  "cx": ...,
  "cy": ...,
  "frames": [
    {
      "file_path": "images/0001.jpg",
      "transform_matrix": [[...4x4...]]
    }
  ]
}
```

intrinsicは：

```python
calib["camera_intrinsic"]
```

から取得。

---

# STEP 5：Splatfactoで学習（3段階アプローチ）

## Stage 1: 超軽量テスト（5-10分）

**目的**: 環境動作確認、パイプライン破綻チェック

```bash
uv run ns-train splatfacto \
  --data data/derived/scene-0061_front \
  --max-num-iterations 1000 \
  --viewer.quit-on-train-completion True \
  --output-dir outputs/stage1_quick_test
```

**設定理由**:
* `max-num-iterations 1000` - 超短時間（5分程度）
* デフォルト設定を使用（ガウシアン数は自動調整）
* RTX 4090（24GB VRAM）なら問題なく完走

**確認ポイント**:
* CUDAメモリエラーが出ないか
* transforms.jsonが正しく読み込まれるか
* PSNRが上昇傾向か（15→20程度でもOK）

---

## Stage 2: 軽量テスト（20-30分）

**目的**: 品質・収束性確認

```bash
uv run ns-train splatfacto \
  --data data/derived/scene-0061_front \
  --max-num-iterations 5000 \
  --viewer.quit-on-train-completion True \
  --output-dir outputs/stage2_light
```

**設定理由**:
* `5000 iterations` - 軽量設定
* デフォルト設定を使用（ガウシアン数は自動調整）
* 1600x900×39フレームなら十分

**確認ポイント**:
* PSNR > 25
* ns-viewerでレンダリング確認
* 座標系の破綻がないか（地面が斜めになっていないか）

---

## Stage 3: フル品質（1-2時間）

**目的**: 最終品質

```bash
uv run ns-train splatfacto \
  --data data/derived/scene-0061_front \
  --max-num-iterations 30000 \
  --viewer.quit-on-train-completion True \
  --output-dir outputs/stage3_full
```

**設定理由**:
* `30000 iterations` - splatfactoのデフォルト
* デフォルト設定を使用（ガウシアン数は自動調整）
* 1600x900なら2時間以内で完了

**目標品質**:
* PSNR > 28-30
* publication-quality rendering

---

## 時間見積もり（RTX 4090基準）

| Stage | Iterations | 予想時間 | VRAM使用量 |
|-------|-----------|---------|-----------|
| 1     | 1,000     | 5-10分  | ~4GB      |
| 2     | 5,000     | 20-30分 | ~6GB      |
| 3     | 30,000    | 1-2時間 | ~8GB      |

---

## 推奨進行順序

1. まずStage 1を実行 - 環境が正しく動くか確認
2. Stage 1の出力を`ns-viewer`で確認
3. 問題なければStage 2へ
4. Stage 2で座標系・品質を確認
5. 満足できればStage 3で最終品質

---

# STEP 6：レンダ確認

```bash
ns-viewer --load-config outputs/.../config.yml
```

✔ カメラパスに沿って表示される
✔ 破綻していない

これが出れば成功。

---

# ここで起きる典型トラブル（Stage 1で検出）

| 症状     | 原因          | 対処 |
| ------ | ----------- | ---- |
| 全部バラバラ | 座標変換ミス      | src/nuscenes_gs/poses.pyを確認 |
| スケール爆発 | 行列順序ミス      | T_world_cam = T_ego_cam @ T_world_egoの順序確認 |
| 画像真っ黒  | intrinsicミス | transforms.jsonのfl_x/fl_yを確認 |
| 地面が斜め  | 座標系不一致      | nuScenes→OpenCV座標変換を確認 |
| Gaussianが爆発 | pose破綻 | rotation行列のdet=1.0を確認 |

---

# 最短成功のための制限

最初は：

* 画像間引く（例：2Hz全部使わない）
* 30〜50枚だけ使う
* 1シーンの前半だけ

これで十分。

---

# 成功の定義

1. GSが学習する
2. カメラパスに沿ってレンダできる
3. 明らかな行列崩壊がない

ここまでで **背景＋車ありGSが立つ**

---

# 次のステップ（成功後）

* 3D bbox投影マスク追加
* LiDAR拘束追加
* 複数カメラ化

---

もしよければ次に：

* 「world→cam の具体的な行列コード」
* 「Nerfstudio座標変換を正確にやる式」
* 「bbox投影マスクの実装」

どこから書きますか？
