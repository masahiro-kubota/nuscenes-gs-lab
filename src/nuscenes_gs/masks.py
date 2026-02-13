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
) -> tuple[np.ndarray, np.ndarray]:
    """World座標系の点群を2D画像に投影.

    Args:
        points_world: (N, 3) in world frame
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)

    Returns:
        uv: (M, 2) pixel coordinates [u, v] for visible points
        valid_mask: (N,) boolean mask indicating which points are visible
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

    # 画像境界内の点のみ
    in_bounds = (
        (uv[:, 0] >= 0) & (uv[:, 0] < w) &
        (uv[:, 1] >= 0) & (uv[:, 1] < h)
    )

    # valid_maskを更新（カメラ背後 + 境界外をフィルタ）
    valid_indices = np.where(valid_mask)[0]
    valid_mask[valid_indices[~in_bounds]] = False

    return uv[in_bounds], valid_mask


def create_label_overlay(
    image_shape: tuple[int, int],
    uv: np.ndarray,
    labels: np.ndarray,
    colormap: dict[int, tuple[int, int, int]] | None = None,
) -> np.ndarray:
    """Semantic labelに基づいてカラーマップオーバーレイを作成.

    Args:
        image_shape: (height, width)
        uv: (N, 2) pixel coordinates [u, v]
        labels: (N,) semantic class IDs
        colormap: dict mapping class ID to RGB color. If None, use default.

    Returns:
        overlay: (H, W, 3) RGB image with colored points
    """
    h, w = image_shape
    overlay = np.zeros((h, w, 3), dtype=np.uint8)

    # デフォルトカラーマップ（nuScenes semantic classes）
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

    # 各点を描画
    for (u, v), label in zip(uv, labels):
        u_int, v_int = int(round(u)), int(round(v))
        if 0 <= u_int < w and 0 <= v_int < h:
            color = colormap.get(label, (128, 128, 128))  # Gray for unknown
            overlay[v_int, u_int] = color

    return overlay


def compute_w2c(ego_pose: dict, calibrated_sensor: dict) -> np.ndarray:
    """world-to-camera行列を計算（c2wの逆行列）.

    Args:
        ego_pose: ego_pose data
        calibrated_sensor: calibrated_sensor data

    Returns:
        w2c: 4x4 world-to-camera transform matrix
    """
    c2w = compute_c2w(ego_pose, calibrated_sensor)
    return np.linalg.inv(c2w)
