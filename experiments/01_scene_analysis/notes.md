# Experiment 01: Scene Analysis - Notes

## 2026-02-14: Scene Speed Analysis Implementation

### スクリプト作成

- `scripts/analyze_scene_speed.py` - シーン速度分析スクリプト作成完了
- `scripts/lidarseg_viewer.py` - Streamlit可視化アプリ初期版作成完了

### シーン速度分析結果

nuScenes mini 10シーンの速度分析を実施：

```
=== Scene Speed Analysis ===
Scene           Frames   Avg Speed (km/h)   Stop Ratio
------------------------------------------------------------
scene-0553      41              0.0         100.0%
scene-1100      40              0.2         100.0%
scene-0757      41              5.0          60.0%
scene-0916      41             16.8           0.0%
scene-0061      39             17.3           0.0%
scene-0103      40             21.8           0.0%
scene-1094      40             23.2          10.3%
scene-0655      41             29.3           0.0%
scene-0796      40             43.7           0.0%
scene-1077      41             45.3           0.0%
```

### 重要な発見

**最も低速なシーン**:
- **scene-0553**: 0.0 km/h, 停止率100% - 完全停止シーン
- **scene-1100**: 0.2 km/h, 停止率100% - ほぼ停止シーン
- **scene-0757**: 5.0 km/h, 停止率60% - 低速で停止が多い

**baseline実験で使用済み**:
- **scene-0061**: 17.3 km/h - Phase 0（front_cam_baseline）で使用

### 推奨シーン選択

LiDAR segmentation masking実験（Phase 2）では、以下のシーンが推奨される：

1. **scene-0553** - 完全停止、最も安定
2. **scene-0757** - 低速・停止混在、実用的
3. **scene-0061** - baseline との比較に最適（既存データ利用可能）

**理由**:
- 2Hz サンプリングレートでは、動体のモーションブラーが大きい
- 低速・停止が多いシーンでは、マスクの効果が高い
- scene-0061はbaseline比較に便利（既に学習済みモデルあり）

### シーン選定と3DGS学習設定

**選定シーン**: scene-0757

**選定理由**:
- 平均速度 5.0 km/h、停止率 60%
- 周囲の車両が少ない（Streamlit で目視確認済み）
- 減速パターンあり、カメラの動き（視点変化）が適度
- GS再構築に必要な視点変化を確保しつつ、周囲の動体が少ない理想的なシーン

**3DGS学習設定**:
- フレーム数: 41
- 画像解像度: 1600×900
- max-num-iterations: 30,000
- max-num-gaussians: 制限なし（Nerfstudio splatfacto デフォルト）
- densification停止iter: 15,000（デフォルト）
  - 15,000 iter 以降は既存 Gaussians の最適化のみ
- その他デフォルト設定:
  - cull_alpha_thresh: 0.1
  - densify_grad_thresh: 0.0008

**学習実行**:
```bash
bash experiments/01_scene_analysis/run.sh
```

### 次のステップ

- scene-0757 の 3DGS 学習実行（30,000 iterations）
- 学習結果の品質確認
- Experiment 02 で lidarseg データパック取得と LiDAR 投影実装
