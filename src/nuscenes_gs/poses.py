"""nuScenes pose → 4x4 変換行列の計算."""

from __future__ import annotations

import numpy as np
from pyquaternion import Quaternion


def make_transform(translation: list[float], rotation: list[float]) -> np.ndarray:
    """quaternion + translation → 4x4 同次変換行列.

    Args:
        translation: [x, y, z]
        rotation: [w, x, y, z] quaternion

    Returns:
        4x4 transformation matrix
    """
    T = np.eye(4)
    T[:3, :3] = Quaternion(rotation).rotation_matrix
    T[:3, 3] = translation
    return T


# OpenCV camera (x右, y下, z前) → OpenGL camera (x右, y上, z後ろ)
_CV2GL = np.diag([1.0, -1.0, -1.0, 1.0])


def compute_c2w(ego_pose: dict, calibrated_sensor: dict) -> np.ndarray:
    """nuScenes ego_pose + calibrated_sensor → camera-to-world (OpenGL convention).

    座標変換チェーン:
        camera --[T_ego_cam]--> ego --[T_world_ego]--> world

    Nerfstudio は c2w を OpenGL カメラ座標系で期待する。
    nuScenes カメラは OpenCV 系なので最後に変換を挟む。

    Returns:
        4x4 c2w matrix (OpenGL convention)
    """
    T_world_ego = make_transform(
        ego_pose["translation"], ego_pose["rotation"]
    )
    T_ego_cam = make_transform(
        calibrated_sensor["translation"], calibrated_sensor["rotation"]
    )

    c2w_cv = T_world_ego @ T_ego_cam  # c2w in OpenCV camera frame
    c2w_gl = c2w_cv @ _CV2GL           # c2w in OpenGL camera frame
    return c2w_gl
