# ロードマップ（nuScenes → 背景GS）

## Phase 0: 環境・パイプライン検証 ✅

> Exp 00（front_cam_baseline）、Exp 01（scene_analysis）、Exp 02（lidarseg_visualization）

### 使うデータ

* nuScenes v1.0-mini
* CAM_FRONT
* ego_pose / calibrated_sensor（与え姿勢）

### 使うシーンの特徴

* 何でもOK（まず動くこと優先）
* ただし失敗を避けるなら低速・停止が多いほど良い

### 達成したいこと

* **COLMAPなし**で、与え姿勢から **3DGSが学習できる**
* **レンダが出る**（破綻してないカメラパス再現）

### やったこと

* CAM_FRONT抽出 → world↔cam行列生成 → Nerfstudio形式 → splatfacto学習 → viewer確認
* シーン速度分析（10シーン）→ 低速シーン scene-0757 を選定
* LiDAR 点群の画像投影・semantic label 可視化を確認

---

## Phase 1: 3D BBox マスクで動体を除去 ✅

> Exp 04（bbox_masking） — Stage 3（30k iterations）完了

### 使うデータ

* nuScenes（mini → trainvalへ拡張可）
* CAM_FRONT
* **sample_annotation（3D bbox）** ← 追加DL不要

### 使うシーンの特徴（成功率が高い）

* **低速・停止が多い**
* 動体が写ってもよいが、**画面を埋め尽くさない**
* 直線高速より、信号待ち・渋滞・右左折が混ざる方が良い

### 達成したいこと

* 車・歩行者などの **動体が背景に焼き付かない**
* 近景〜中景の背景が安定する（放射状ノイズが減る）

### やったこと

1. **3D bboxをCAM_FRONTへ投影**して2Dマスク生成
   * 対象：`vehicle.* / human.* / cycle.*`
   * dilation=5
2. 学習時に **マスク領域をlossから除外**
3. scene-0757（41枚）で Stage 1 → Stage 3 完了

### 知見

* bbox は遠方の車両もカバーできるが、背景を過剰にマスクする傾向あり

---

## Phase 2: LiDAR セグメンテーションで精密マスク ✅

> Exp 03（lidarseg_masking） — Stage 3（30k iterations）完了
>
> ※ 実際には Phase 1 より先に実施（LiDAR 投影の可視化から自然に発展したため）

### 使うデータ

* **nuScenes-lidarseg**（追加パック）
  * LiDAR keyframe 点群に semantic label
* CAM_FRONT（引き続き）
* ego_pose / calibrated_sensor

### 使うシーンの特徴

* Phase 1と同じ（低速優先）
* 動体が多いシーンでも対応力を上げたい段階

### 達成したいこと

* bbox投影で残る「輪郭の漏れ」「bbox外の飛び出し」を減らす
* 背景に残る"ゴースト"を目立たなくする

### やったこと

1. lidarsegで **vehicle/human/cycle のLiDAR点を特定**
2. 動的点を画像に投影し、**モルフォロジー膨張でマスク生成**
3. dilation を 3 → 8 → 32 → **64** と段階調整
4. bbox マスクとは独立に実験（論理和の統合は未実施）

### 知見

* 近距離（~30m）は精密なマスクが可能
* 遠距離（50m+）は LiDAR 点が疎すぎてカバー困難
* Nerfstudio のマスク規約（0=exclude, 255=include）に注意

---

## Phase 3: 背景の形を安定化（幾何拘束）

> Exp 05（depth_supervision） — 計画済み・未着手

### 使うデータ

* CAM_FRONT
* ego_pose / calibrated_sensor
* LiDAR（sweeps or keyframe）
* lidarseg（静的点のフィルタに使用）

### 使うシーンの特徴

* **道路スケールが大きい（遠景が多い）**シーンで効果が大きい
* 直線区間や遠景が抜ける区間

### 達成したいこと

* 遠景の漂い、地面のうねり、スケール不安定を抑える
* "背景の形"が安定し、再利用できる土台になる

### やること

1. 静的LiDAR点（動体除去済み）→ CAM_FRONTへ投影
2. **スパース深度マップ**を生成（16-bit PNG、欠損はOK）
3. Nerfstudio の depth supervision（depth_file_path + depth-loss-mult）で学習
4. 遠景の安定度で評価（見た目＋軌跡レンダ）

---

## Phase 4: マルチカメラ化（最終形へ）

> Exp 06（multicam_front3） — 計画済み・未着手

### 使うデータ

* CAM_FRONT + CAM_FRONT_LEFT + CAM_FRONT_RIGHT（まず3台）
* ego_pose / calibrated_sensor（各cameraのsample_dataごと）
* （必要なら）lidarseg/panoptic, LiDAR拘束

### 使うシーンの特徴

* カメラ間で見える共通領域が多いシーン（交差点/市街地は強い）
* 露出差が大きいので、極端な逆光シーンは後回し

### 達成したいこと

* 横方向の構造（建物側面、路肩、歩道）を安定化
* 将来的な「周囲車両を破綻なく見せる」土台になる

### やること

1. まず3台（Front/Front-Left/Front-Right）だけ追加
2. per-frame intrinsics で異なるカメラを1つの transforms.json に統合
3. マスク・深度戦略はPhase 1〜3のまま適用
4. 露出差対策（軽い色正規化）を必要に応じて導入

---

## Phase 5: "穴埋め"と再利用性の向上（仕上げ）

### 使うデータ

* 同一路線の別走行（反復走行データ）
* 既存背景GS（固定）
* 追加フレーム（穴が見える瞬間）

### 使うシーンの特徴

* "穴が見える"視点が含まれる（別走行・別レーンなどが効く）

### 達成したいこと

* 動体を消した結果できる欠損（穴）を自然に埋める
* 背景GSを「シナリオテスト用アセット」として安定運用できる

### やること

1. 背景GSを固定し、追加フレームで欠損を埋める
2. 必要なら2D inpaintで補助（軽い仕上げとして）
3. 評価：任意視点レンダで破綻がないこと

---

# 重要な設計原則（このロードマップの背骨）

* **2Hzは厳しいが、低速区間＋動体マスクで十分戦える**
* 歪みは基本気にしない（nuScenes画像は補正済み）
* 改善の優先順位は
  **動体マスク → 幾何安定（LiDAR）→ マルチカメラ → 高周期**
* "まずレンダが出る"を守る（Phase 0 で達成済み）
