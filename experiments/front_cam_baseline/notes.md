# A' experiment: CAM_FRONT + given pose

## Overview

nuScenes mini の 1シーンから CAM_FRONT のみ抽出し、splatfacto で学習する最小 PoC。

## 2025-02-13: initial export

- scene-0061 を export（39 frames, 1600x900）
- transforms.json 生成確認済み
  - rotation det=1.0, orthogonality ~1e-15
  - camera height Z ≈ 1.5m
  - fl_x=1266.4, fl_y=1266.4
