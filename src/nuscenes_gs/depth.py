"""LiDAR-based sparse depth map generation for nuScenes data.

This module provides functions to:
1. Load LiDAR point clouds with semantic labels
2. Filter dynamic objects (vehicles, humans, cycles)
3. Project static LiDAR points onto 2D images
4. Generate sparse depth maps for depth supervision
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from .masks import load_lidar_points_and_labels, transform_lidar_to_world, compute_w2c

if TYPE_CHECKING:
    from nuscenes.nuscenes import NuScenes


def project_lidar_to_depth(
    points_world: np.ndarray,
    labels: np.ndarray,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
    dynamic_classes: list[int] | None = None,
    depth_range: tuple[float, float] = (0.1, 80.0),
) -> np.ndarray:
    """LiDAR 静的点群からスパース深度マップを生成.

    Args:
        points_world: (N, 3) LiDAR points in world frame
        labels: (N,) semantic class IDs
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)
        dynamic_classes: List of semantic class IDs to exclude. If None, use default.
        depth_range: (min_depth, max_depth) in meters

    Returns:
        Depth map (H, W) uint16, values in millimeters (0 = no depth)
    """
    h, w = image_shape
    min_depth, max_depth = depth_range

    # デフォルトの動的クラス
    if dynamic_classes is None:
        dynamic_classes = (
            [17, 18, 19, 20, 21, 22, 23] +  # vehicle.*
            [2, 3, 4, 5, 6, 7] +             # human.*
            [14, 15, 16]                     # cycle.*
        )

    # 動的オブジェクトを除外（静的点のみ残す）
    static_mask = ~np.isin(labels, dynamic_classes)
    static_points = points_world[static_mask]

    if len(static_points) == 0:
        # 静的点がない場合は空の深度マップを返す
        return np.zeros((h, w), dtype=np.uint16)

    # World → camera 座標系に変換
    points_homo = np.hstack([static_points, np.ones((len(static_points), 1))])
    points_cam_homo = (w2c @ points_homo.T).T  # (N, 4)
    points_cam = points_cam_homo[:, :3]  # (N, 3)

    # カメラ背後の点をフィルタ（z > 0のみ）
    valid_mask = points_cam[:, 2] > 0
    points_cam = points_cam[valid_mask]

    if len(points_cam) == 0:
        return np.zeros((h, w), dtype=np.uint16)

    # 深度値を取得（カメラ座標系の z 値）
    depths = points_cam[:, 2]

    # 深度範囲でフィルタ
    depth_valid = (depths >= min_depth) & (depths <= max_depth)
    points_cam = points_cam[depth_valid]
    depths = depths[depth_valid]

    if len(points_cam) == 0:
        return np.zeros((h, w), dtype=np.uint16)

    # 2D 投影
    points_2d_homo = (K @ points_cam.T).T  # (M, 3)
    uv = points_2d_homo[:, :2] / points_2d_homo[:, 2:3]  # (M, 2)

    # 画像境界内の点のみ
    in_bounds = (
        (uv[:, 0] >= 0) & (uv[:, 0] < w) &
        (uv[:, 1] >= 0) & (uv[:, 1] < h)
    )

    uv = uv[in_bounds]
    depths = depths[in_bounds]

    # 深度マップを初期化（0 = 深度なし）
    depth_map = np.zeros((h, w), dtype=np.float32)

    # 各ピクセルに深度値を格納（複数点が同じピクセルに投影される場合は最小深度を使用）
    for (u, v), depth in zip(uv, depths):
        u_int, v_int = int(round(u)), int(round(v))
        if 0 <= u_int < w and 0 <= v_int < h:
            # 既に深度値がある場合は最小値を保持（手前の点を優先）
            if depth_map[v_int, u_int] == 0 or depth < depth_map[v_int, u_int]:
                depth_map[v_int, u_int] = depth

    # メートル → ミリメートルに変換して 16-bit に格納
    # 0 = 深度なし、1~ = 深度値（mm）
    depth_map_mm = (depth_map * 1000).astype(np.uint16)

    return depth_map_mm


def generate_depth_maps_for_scene(
    nusc,
    scene_token: str,
    output_dir: Path,
    dynamic_classes: list[int] | None = None,
    depth_range: tuple[float, float] = (0.1, 80.0),
) -> dict[int, Path]:
    """シーン全体の全フレームについてスパース深度マップを生成.

    Args:
        nusc: NuScenes instance
        scene_token: Scene token
        output_dir: Output directory for depth maps
        dynamic_classes: List of semantic class IDs to exclude. If None, use default.
        depth_range: (min_depth, max_depth) in meters

    Returns:
        Dictionary mapping frame_idx to depth_path
    """
    scene = nusc.get("scene", scene_token)
    depth_dir = Path(output_dir) / "depth"
    depth_dir.mkdir(parents=True, exist_ok=True)

    depth_paths = {}
    sample_token = scene["first_sample_token"]
    frame_idx = 0

    while sample_token:
        sample = nusc.get("sample", sample_token)

        # CAM_FRONT と LIDAR_TOP のデータを取得
        cam_token = sample["data"]["CAM_FRONT"]
        lidar_token = sample["data"]["LIDAR_TOP"]

        cam_data = nusc.get("sample_data", cam_token)
        lidar_data = nusc.get("sample_data", lidar_token)

        # LiDAR点群とlabelsを読み込み
        points_lidar, labels = load_lidar_points_and_labels(nusc, lidar_token)

        # LiDAR → world座標変換
        lidar_ego_pose = nusc.get("ego_pose", lidar_data["ego_pose_token"])
        lidar_calib = nusc.get("calibrated_sensor", lidar_data["calibrated_sensor_token"])
        points_world = transform_lidar_to_world(points_lidar, lidar_ego_pose, lidar_calib)

        # カメラパラメータ
        cam_ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
        cam_calib = nusc.get("calibrated_sensor", cam_data["calibrated_sensor_token"])
        w2c = compute_w2c(cam_ego_pose, cam_calib)
        K = np.array(cam_calib["camera_intrinsic"])

        # 画像サイズを取得
        from PIL import Image as PILImage
        img_path = Path(nusc.dataroot) / cam_data["filename"]
        with PILImage.open(img_path) as img:
            image_shape = (img.height, img.width)

        # 深度マップ生成
        depth_map = project_lidar_to_depth(
            points_world,
            labels,
            w2c,
            K,
            image_shape,
            dynamic_classes=dynamic_classes,
            depth_range=depth_range,
        )

        # 深度マップを保存
        depth_path = depth_dir / f"{frame_idx:04d}.png"
        cv2.imwrite(str(depth_path), depth_map)
        depth_paths[frame_idx] = depth_path

        # 次のフレームへ
        sample_token = sample["next"] if sample["next"] else None
        frame_idx += 1

    return depth_paths
