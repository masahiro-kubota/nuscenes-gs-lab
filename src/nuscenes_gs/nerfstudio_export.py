"""nuScenes 1シーン → Nerfstudio transforms.json + images/ へのエクスポート."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from nuscenes.nuscenes import NuScenes

from nuscenes_gs.poses import compute_c2w


def export_scene_front(
    nusc: NuScenes,
    scene_token: str,
    output_dir: str | Path,
) -> Path:
    """1シーンの CAM_FRONT を Nerfstudio 形式でエクスポートする.

    Args:
        nusc: NuScenes インスタンス
        scene_token: 対象シーンの token
        output_dir: 出力ディレクトリ

    Returns:
        生成した transforms.json のパス
    """
    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene = nusc.get("scene", scene_token)
    sample_token = scene["first_sample_token"]

    frames: list[dict] = []
    intrinsic = None
    width, height = None, None
    idx = 0

    while sample_token:
        sample = nusc.get("sample", sample_token)
        cam_token = sample["data"]["CAM_FRONT"]
        cam_data = nusc.get("sample_data", cam_token)

        ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
        calib = nusc.get(
            "calibrated_sensor", cam_data["calibrated_sensor_token"]
        )

        # intrinsic は1回だけ取得（CAM_FRONTはシーン内で固定）
        if intrinsic is None:
            K = np.array(calib["camera_intrinsic"])
            intrinsic = {
                "fl_x": K[0, 0],
                "fl_y": K[1, 1],
                "cx": K[0, 2],
                "cy": K[1, 2],
            }
            width = cam_data["width"]
            height = cam_data["height"]

        # c2w 計算
        c2w = compute_c2w(ego_pose, calib)

        # 画像コピー
        src_path = Path(nusc.dataroot) / cam_data["filename"]
        dst_name = f"{idx:04d}.jpg"
        shutil.copy2(src_path, images_dir / dst_name)

        frames.append(
            {
                "file_path": f"images/{dst_name}",
                "transform_matrix": c2w.tolist(),
            }
        )

        idx += 1
        sample_token = sample["next"] if sample["next"] else None

    transforms = {
        "camera_model": "OPENCV",
        "w": width,
        "h": height,
        **intrinsic,
        "frames": frames,
    }

    out_path = output_dir / "transforms.json"
    with open(out_path, "w") as f:
        json.dump(transforms, f, indent=2)

    return out_path


def export_scene_front_with_lidar_masks(
    nusc: NuScenes,
    scene_token: str,
    output_dir: str | Path,
    dynamic_classes: list[int] | None = None,
    dilation_size: int = 8,
) -> Path:
    """1シーンの CAM_FRONT を LiDAR マスク付きで Nerfstudio 形式でエクスポートする.

    Args:
        nusc: NuScenes インスタンス
        scene_token: 対象シーンの token
        output_dir: 出力ディレクトリ
        dynamic_classes: マスクする semantic class IDs のリスト. None の場合はデフォルト.
        dilation_size: モルフォロジー膨張カーネルサイズ

    Returns:
        生成した transforms.json のパス
    """
    from nuscenes_gs.masks import generate_lidar_masks_for_scene

    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene = nusc.get("scene", scene_token)
    sample_token = scene["first_sample_token"]

    frames: list[dict] = []
    intrinsic = None
    width, height = None, None
    idx = 0

    # 1. 画像をエクスポート
    while sample_token:
        sample = nusc.get("sample", sample_token)
        cam_token = sample["data"]["CAM_FRONT"]
        cam_data = nusc.get("sample_data", cam_token)

        ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
        calib = nusc.get(
            "calibrated_sensor", cam_data["calibrated_sensor_token"]
        )

        # intrinsic は1回だけ取得（CAM_FRONTはシーン内で固定）
        if intrinsic is None:
            K = np.array(calib["camera_intrinsic"])
            intrinsic = {
                "fl_x": K[0, 0],
                "fl_y": K[1, 1],
                "cx": K[0, 2],
                "cy": K[1, 2],
            }
            width = cam_data["width"]
            height = cam_data["height"]

        # c2w 計算
        c2w = compute_c2w(ego_pose, calib)

        # 画像コピー
        src_path = Path(nusc.dataroot) / cam_data["filename"]
        dst_name = f"{idx:04d}.jpg"
        shutil.copy2(src_path, images_dir / dst_name)

        frames.append(
            {
                "file_path": f"images/{dst_name}",
                "transform_matrix": c2w.tolist(),
                "mask_path": f"masks/{idx:04d}.png",  # マスクパスを追加
            }
        )

        idx += 1
        sample_token = sample["next"] if sample["next"] else None

    # 2. LiDAR マスクを生成
    print(f"Generating LiDAR masks for {idx} frames...")
    mask_paths = generate_lidar_masks_for_scene(
        nusc,
        scene_token,
        output_dir,
        dynamic_classes=dynamic_classes,
        dilation_size=dilation_size,
    )
    print(f"Generated {len(mask_paths)} masks")

    # 3. transforms.json を保存
    transforms = {
        "camera_model": "OPENCV",
        "w": width,
        "h": height,
        **intrinsic,
        "frames": frames,
    }

    out_path = output_dir / "transforms.json"
    with open(out_path, "w") as f:
        json.dump(transforms, f, indent=2)

    return out_path


def export_scene_front_with_bbox_masks(
    nusc: NuScenes,
    scene_token: str,
    output_dir: str | Path,
    dynamic_categories: list[str] | None = None,
    dilation_size: int = 5,
) -> Path:
    """1シーンの CAM_FRONT を bbox マスク付きで Nerfstudio 形式でエクスポートする.

    Args:
        nusc: NuScenes インスタンス
        scene_token: 対象シーンの token
        output_dir: 出力ディレクトリ
        dynamic_categories: マスクする category prefix のリスト. None の場合はデフォルト.
        dilation_size: モルフォロジー膨張カーネルサイズ

    Returns:
        生成した transforms.json のパス
    """
    from nuscenes_gs.masks import generate_bbox_masks_for_scene

    output_dir = Path(output_dir)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    scene = nusc.get("scene", scene_token)
    sample_token = scene["first_sample_token"]

    frames: list[dict] = []
    intrinsic = None
    width, height = None, None
    idx = 0

    # 1. 画像をエクスポート
    while sample_token:
        sample = nusc.get("sample", sample_token)
        cam_token = sample["data"]["CAM_FRONT"]
        cam_data = nusc.get("sample_data", cam_token)

        ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
        calib = nusc.get(
            "calibrated_sensor", cam_data["calibrated_sensor_token"]
        )

        # intrinsic は1回だけ取得（CAM_FRONTはシーン内で固定）
        if intrinsic is None:
            K = np.array(calib["camera_intrinsic"])
            intrinsic = {
                "fl_x": K[0, 0],
                "fl_y": K[1, 1],
                "cx": K[0, 2],
                "cy": K[1, 2],
            }
            width = cam_data["width"]
            height = cam_data["height"]

        # c2w 計算
        c2w = compute_c2w(ego_pose, calib)

        # 画像コピー
        src_path = Path(nusc.dataroot) / cam_data["filename"]
        dst_name = f"{idx:04d}.jpg"
        shutil.copy2(src_path, images_dir / dst_name)

        frames.append(
            {
                "file_path": f"images/{dst_name}",
                "transform_matrix": c2w.tolist(),
                "mask_path": f"masks/{idx:04d}.png",  # マスクパスを追加
            }
        )

        idx += 1
        sample_token = sample["next"] if sample["next"] else None

    # 2. bbox マスクを生成
    print(f"Generating bbox masks for {idx} frames...")
    mask_paths = generate_bbox_masks_for_scene(
        nusc,
        scene_token,
        output_dir,
        dynamic_categories=dynamic_categories,
        dilation_size=dilation_size,
    )
    print(f"Generated {len(mask_paths)} masks")

    # 3. transforms.json を保存
    transforms = {
        "camera_model": "OPENCV",
        "w": width,
        "h": height,
        **intrinsic,
        "frames": frames,
    }

    out_path = output_dir / "transforms.json"
    with open(out_path, "w") as f:
        json.dump(transforms, f, indent=2)

    return out_path
