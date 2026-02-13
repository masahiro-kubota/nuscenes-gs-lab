# nuscenes-gs-lab

nuScenesデータを使って、3D Gaussian Splattingを段階的に実験・拡張するための再現可能な研究基盤。

単発スクリプト置き場ではなく「実験フレームワーク」として設計する。

---

## スコープ

### 含むもの

* nuScenes → 各手法向けデータ変換
* pose合成（ego_pose + calibrated_sensor）
* マスク生成（bbox / lidarseg）
* 深度拘束実験
* multi-cam統合
* 各GS手法（Relightable, Deferred, SU-RGS等）のデータ準備・評価

### 含まないもの

* nuScenes本体データ
* 学習済みモデルの重い出力
* GS手法本体の実装（外部リポジトリ）

---

## セットアップ

### 1. nuScenes miniデータセットの取得

```bash
# nuScenes miniをダウンロード (3.9GB)
# https://www.nuscenes.org/nuscenes#download から v1.0-mini.tgz をダウンロード
```

### 2. データの展開

```bash
# data/raw/ ディレクトリを作成
mkdir -p data/raw

# ダウンロードしたファイルを展開
tar -xzf ~/Downloads/v1.0-mini.tgz -C data/raw/
```

### 3. 動作確認

```bash
# nuScenesが正しく読み込めるか確認
python3 -c "from nuscenes.nuscenes import NuScenes; nusc = NuScenes(version='v1.0-mini', dataroot='data/raw', verbose=True); print(f'シーン数: {len(nusc.scene)}')"
```

正常に読み込めれば「シーン数: 10」と表示されます。

---

## ディレクトリ構成

```
nuscenes-gs-lab/
│
├── pyproject.toml
├── .gitignore
│
├── src/nuscenes_gs/           # 共通基盤（安定層）
│   ├── __init__.py
│   ├── poses.py               # pose合成・座標変換
│   ├── nerfstudio_export.py   # Nerfstudio形式エクスポート
│   ├── masks.py               # bbox除去、セグメンテーション（予定）
│   └── geometry.py            # LiDAR投影など（予定）
│
├── scripts/                   # 汎用ツール（実験横断）
│   ├── export_front_only.py
│   └── visualize_poses.py     # ポーズ3D可視化
│
├── experiments/               # 実験ごとに独立
│   ├── front_cam_baseline/    # CAM_FRONT single-cam baseline
│   │   ├── plan.md            # 実験計画
│   │   ├── notes.md           # 経緯・結果・所見
│   │   └── run.sh             # 再現コマンド一式
│   ├── vehicle_removal/       # （予定）
│   ├── relightable_gs/        # （予定）
│   └── su_rgs/                # （予定）
│
├── data/
│   ├── raw/                   # nuScenes本体（gitignore）
│   └── derived/               # 変換済みデータ
│       └── scene-XXXX_front/
│           ├── images/
│           └── transforms.json
│
└── outputs/                   # 学習出力（gitignore）
```

---

## 3層構造

### src/ — 共通基盤

2つ以上の実験で使う処理をここに置く。

* pose合成・座標変換
* データ読み込み・エクスポート
* bbox投影・マスク生成
* LiDAR投影

### scripts/ — 汎用ツール

実験をまたいで使える実行スクリプト。

* データ変換（export_front_only.py）
* 可視化

### experiments/ — 実験単位

各実験が自己完結する単位。

* `plan.md` — 実験計画（何をやるか、なぜやるか）
* `notes.md` — 実験ログ（何を試した、何が壊れた、次何をやるか）
* `run.sh` — 再現コマンド（export → train → render の全手順）
* `results/` — 結果物（レンダ画像、メトリクス等。軽いものだけgit管理）
* 実験固有のスクリプト — その実験でしか使わない前処理・後処理

共通処理は `src/` から import し、固有処理だけここに書く。
コードが2つ以上の実験で必要になったら `src/` に昇格させる。

重い学習出力（チェックポイント等）は `outputs/` に置く（gitignore済み）。

---

## 実験ワークフロー

```
1. experiments/<name>/ を作成
2. plan.md で計画を書く
3. データ変換（scripts/ or 実験固有スクリプト）
4. 学習・レンダリング
5. notes.md に結果を記録
6. run.sh に再現コマンドをまとめる
```

---

## .gitignore

```
data/raw/
data/derived/**/images/
outputs/
*.ckpt
*.pth
*.pt
```

---

## 進化パス

| フェーズ           | 内容                            |
| ---------------- | ------------------------------- |
| front_cam_baseline | front-only baseline           |
| A-mask           | bbox マスク                      |
| B                | LiDAR 拘束                      |
| C                | multi-cam                       |
| D                | dynamic GS                      |
| Relightable      | Relightable GS                  |
| Deferred         | Deferred GS                     |
| SU-RGS           | SU-RGS                          |

GS手法本体は外部リポジトリ。このリポにはデータ準備・評価・記録を置く。
