"""LiDAR segmentation-based masking for nuScenes data.

This module provides functions to:
1. Load LiDAR point clouds with semantic labels
2. Transform LiDAR points to world/camera coordinates
3. Project LiDAR points onto 2D images
4. Generate masks for dynamic objects (vehicles, humans, cycles)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np
from nuscenes.utils.data_classes import LidarPointCloud

from .poses import compute_c2w, make_transform

if TYPE_CHECKING:
    from nuscenes.nuscenes import NuScenes


def load_lidar_points_and_labels(
    nusc: NuScenes,
    lidar_token: str,
) -> tuple[np.ndarray, np.ndarray]:
    """LiDAR点群とsemantic labelsを読み込む.

    Args:
        nusc: NuScenes instance
        lidar_token: LiDAR sample_data token

    Returns:
        points: (N, 3) [x, y, z] in lidar frame
        labels: (N,) uint8 semantic class IDs

    Raises:
        KeyError: If lidarseg data is not available for this token
    """
    # 点群読み込み
    lidar_data = nusc.get("sample_data", lidar_token)
    pc = LidarPointCloud.from_file(str(Path(nusc.dataroot) / lidar_data["filename"]))
    points = pc.points.T  # (N, 4) -> transpose to (N, 4)

    # semantic labels読み込み
    lidarseg_data = nusc.get("lidarseg", lidar_token)
    labels = np.fromfile(
        Path(nusc.dataroot) / lidarseg_data["filename"],
        dtype=np.uint8,
    )

    return points[:, :3], labels  # (N, 3), (N,)


def transform_lidar_to_world(
    points_lidar: np.ndarray,
    ego_pose: dict,
    calibrated_sensor: dict,
) -> np.ndarray:
    """LiDAR座標系の点群をworld座標系に変換.

    変換チェーン: lidar → ego → world

    Args:
        points_lidar: (N, 3) in lidar frame
        ego_pose: ego_pose data (world系でのego姿勢)
        calibrated_sensor: calibrated_sensor data (ego系でのlidar姿勢)

    Returns:
        points_world: (N, 3) in world frame
    """
    # lidar → ego
    T_ego_lidar = make_transform(
        calibrated_sensor["translation"],
        calibrated_sensor["rotation"],
    )

    # ego → world
    T_world_ego = make_transform(
        ego_pose["translation"],
        ego_pose["rotation"],
    )

    # lidar → world
    T_world_lidar = T_world_ego @ T_ego_lidar

    # 点群をhomogeneous座標に変換
    points_homo = np.hstack([points_lidar, np.ones((len(points_lidar), 1))])

    # 変換適用
    points_world_homo = (T_world_lidar @ points_homo.T).T

    return points_world_homo[:, :3]


def project_points_to_image(
    points_world: np.ndarray,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """World座標系の点群を2D画像に投影.

    Args:
        points_world: (N, 3) in world frame
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)

    Returns:
        uv: (M, 2) pixel coordinates [u, v] for visible points
        valid_mask: (N,) boolean mask indicating which points are visible
        distances: (M,) distances from camera for visible points
    """
    h, w = image_shape

    # World → camera座標系に変換
    points_homo = np.hstack([points_world, np.ones((len(points_world), 1))])
    points_cam_homo = (w2c @ points_homo.T).T  # (N, 4)
    points_cam = points_cam_homo[:, :3]  # (N, 3)

    # カメラ背後の点をフィルタ（z > 0のみ）
    valid_mask = points_cam[:, 2] > 0

    # 2D投影
    points_2d = (K @ points_cam[valid_mask].T).T  # (M, 3)
    uv = points_2d[:, :2] / points_2d[:, 2:3]  # (M, 2)

    # 距離を取得（カメラ座標系のz値）
    distances = points_cam[valid_mask, 2]

    # 画像境界内の点のみ
    in_bounds = (
        (uv[:, 0] >= 0) & (uv[:, 0] < w) &
        (uv[:, 1] >= 0) & (uv[:, 1] < h)
    )

    # valid_maskを更新（カメラ背後 + 境界外をフィルタ）
    valid_indices = np.where(valid_mask)[0]
    valid_mask[valid_indices[~in_bounds]] = False

    return uv[in_bounds], valid_mask, distances[in_bounds]


def create_label_overlay(
    image_shape: tuple[int, int],
    uv: np.ndarray,
    labels: np.ndarray,
    colormap: dict[int, tuple[int, int, int]] | None = None,
    distances: np.ndarray | None = None,
    point_radius: int = 5,
) -> np.ndarray:
    """Semantic labelまたは距離に基づいてカラーマップオーバーレイを作成.

    Args:
        image_shape: (height, width)
        uv: (N, 2) pixel coordinates [u, v]
        labels: (N,) semantic class IDs
        colormap: dict mapping class ID to RGB color. If None, use default.
        distances: (N,) distances from camera. If provided, use distance-based coloring.
        point_radius: radius of each point in pixels

    Returns:
        overlay: (H, W, 3) RGB image with colored points
    """
    h, w = image_shape
    overlay = np.zeros((h, w, 3), dtype=np.uint8)

    # 距離ベースの色分けを使用する場合
    if distances is not None:
        # 距離を正規化（近い=0.0、遠い=1.0）
        min_dist = distances.min()
        max_dist = distances.max()
        normalized_dist = (distances - min_dist) / (max_dist - min_dist + 1e-6)

        # 各点を円として描画（距離で色分け）
        for (u, v), dist_norm in zip(uv, normalized_dist):
            u_int, v_int = int(round(u)), int(round(v))
            if 0 <= u_int < w and 0 <= v_int < h:
                # 青（近い） → 緑 → 黄 → 赤（遠い）のカラーマップ
                if dist_norm < 0.33:
                    # 青 → 緑
                    r = 0
                    g = int(255 * (dist_norm / 0.33))
                    b = int(255 * (1 - dist_norm / 0.33))
                elif dist_norm < 0.67:
                    # 緑 → 黄
                    r = int(255 * ((dist_norm - 0.33) / 0.34))
                    g = 255
                    b = 0
                else:
                    # 黄 → 赤
                    r = 255
                    g = int(255 * (1 - (dist_norm - 0.67) / 0.33))
                    b = 0

                color = (int(r), int(g), int(b))
                cv2.circle(overlay, (u_int, v_int), radius=point_radius, color=color, thickness=-1)
    else:
        # Semantic labelベースの色分けを使用
        if colormap is None:
            # 動的オブジェクトを赤系、静的背景を青/緑系で表現
            colormap = {
                # Vehicle (red-orange)
                17: (255, 50, 50), 18: (255, 100, 50), 19: (255, 150, 50),
                20: (200, 50, 50), 21: (200, 100, 50), 22: (200, 150, 50),
                23: (150, 50, 50),
                # Human (yellow)
                2: (255, 255, 0), 3: (200, 200, 0), 4: (150, 150, 0),
                5: (255, 200, 0), 6: (200, 150, 0), 7: (150, 100, 0),
                # Cycle (purple)
                14: (255, 0, 255), 15: (200, 0, 200), 16: (150, 0, 150),
                # Static background (blue-green)
                1: (0, 100, 200), 8: (0, 150, 150), 9: (0, 200, 100),
                10: (100, 200, 100), 11: (150, 200, 50), 12: (200, 200, 50),
                13: (100, 150, 100),
                # Movable objects (orange)
                24: (255, 150, 0), 25: (200, 120, 0), 26: (150, 100, 0),
                27: (100, 80, 0), 28: (255, 180, 50), 29: (200, 150, 50),
                30: (150, 120, 50), 31: (100, 90, 50),
            }

        # 各点を円として描画
        for (u, v), label in zip(uv, labels):
            u_int, v_int = int(round(u)), int(round(v))
            if 0 <= u_int < w and 0 <= v_int < h:
                color = colormap.get(label, (128, 128, 128))  # Gray for unknown
                cv2.circle(overlay, (u_int, v_int), radius=point_radius, color=color, thickness=-1)

    return overlay


def compute_w2c(ego_pose: dict, calibrated_sensor: dict) -> np.ndarray:
    """world-to-camera行列を計算（OpenCV座標系）.

    Args:
        ego_pose: ego_pose data
        calibrated_sensor: calibrated_sensor data

    Returns:
        w2c: 4x4 world-to-camera transform matrix (OpenCV convention)
    """
    # ego → world
    T_world_ego = make_transform(ego_pose['translation'], ego_pose['rotation'])

    # camera → ego
    T_ego_cam = make_transform(
        calibrated_sensor['translation'],
        calibrated_sensor['rotation']
    )

    # camera → world (OpenCV convention: x=右, y=下, z=前)
    c2w_opencv = T_world_ego @ T_ego_cam

    # world → camera (OpenCV convention)
    w2c = np.linalg.inv(c2w_opencv)

    return w2c
