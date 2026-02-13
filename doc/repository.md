いいですね。
**`nuscenes-gs-lab` は「nuScenes × 3DGS の実験基盤」**として設計するのが正解です。

あなたの目的は：

* A’（Front-only, pose-given）でまず動かす
* マスク / LiDAR拘束 / surround に拡張
* 将来的に動体GSや再合成まで行く

なので、**単発スクリプト置き場ではなく“実験フレームワーク”として設計**します。

---

# 🧠 nuscenes-gs-lab の目的

> nuScenesデータを使って、3D Gaussian Splattingを段階的に実験・拡張するための再現可能な研究基盤

---

# 🎯 スコープ

## 含むもの

* nuScenes → Nerfstudio形式変換
* pose合成（ego_pose + calibrated_sensor）
* 実験設定（YAML）
* 実験ログ（Markdown）
* マスク生成（bbox / lidarseg）
* 深度拘束実験
* 将来的なmulti-cam統合

## 含まないもの

* nuScenes本体データ
* 学習済みモデルの重い出力
* 研究成果物の最終アーティファクト

---

# 📁 推奨ディレクトリ構成（最適化済み）

```
nuscenes-gs-lab/
│
├── README.md
├── pyproject.toml
├── .gitignore
│
├── configs/
│   ├── dataset/
│   │   └── nuscenes_mini.yaml
│   │
│   └── exp/
│       ├── a_prime.yaml
│       ├── a_mask.yaml
│       ├── b_depth.yaml
│       └── c_surround.yaml
│
├── scripts/
│   ├── export_front_only.py
│   ├── train_splatfacto.sh
│   ├── render.sh
│   ├── make_bbox_masks.py
│   └── project_lidar_depth.py
│
├── src/
│   └── nuscenes_gs/
│       ├── __init__.py
│       ├── io.py
│       ├── poses.py
│       ├── nerfstudio_export.py
│       └── geometry.py
│
├── data/
│   ├── raw/          # symlink推奨
│   └── derived/
│       └── scene-0011_front/
│           ├── images/
│           └── transforms.json
│
├── outputs/          # gitignore
│
└── notes/
    ├── 2026-02-13_a_prime_scene0011.md
    └── experiments_index.md
```

---

# 🔧 各レイヤの役割

## 1️⃣ src/

ロジックの本体

* pose合成
* bbox投影
* LiDAR投影
* 座標変換

→ ここがあなたの「研究コア」

---

## 2️⃣ scripts/

実行レイヤ

* データ変換
* 学習実行
* レンダリング

→ コマンドを整理する層

---

## 3️⃣ configs/

実験の定義

* どのscene
* 何枚使うか
* どの手法か
* 学習回数

→ 再現性の中核

---

## 4️⃣ notes/

実験ログ（超重要）

* 何を試したか
* 何が壊れたか
* 次何をやるか

半年後の自分を救う場所。

---

# 🧪 実験ワークフロー（標準化）

```
1. config作成
2. export
3. train
4. viewer確認
5. notesに記録
```

---

# 🔒 .gitignore最小セット

```
data/raw/
data/derived/**/images/
outputs/
*.ckpt
*.pth
*.pt
```

---

# 🔥 進化パス

| フェーズ   | 追加するもの     |
| ------ | ---------- |
| A’     | front-only |
| A-mask | bboxマスク    |
| B      | LiDAR拘束    |
| C      | multi-cam  |
| D      | dynamic GS |

このrepoはこの進化を前提に設計。

---

# 📌 重要な思想

このrepoは：

> 「GSを動かすための場所」

ではなく

> 「nuScenes × GSの実験を体系化する研究基盤」

です。


