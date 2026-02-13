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


def project_lidar_to_mask(
    points_world: np.ndarray,
    labels: np.ndarray,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
    dynamic_classes: list[int] | None = None,
    dilation_size: int = 8,
) -> np.ndarray:
    """LiDAR点群から2Dバイナリマスクを生成.

    Args:
        points_world: (N, 3) LiDAR points in world frame
        labels: (N,) semantic class IDs
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)
        dynamic_classes: List of semantic class IDs to mask. If None, use default.
        dilation_size: Morphological dilation kernel size

    Returns:
        Binary mask (H, W) uint8 (Nerfstudio convention: 0=exclude from training, 255=include)
    """
    h, w = image_shape

    # デフォルトの動的クラス
    if dynamic_classes is None:
        dynamic_classes = (
            [17, 18, 19, 20, 21, 22, 23] +  # vehicle.*
            [2, 3, 4, 5, 6, 7] +             # human.*
            [14, 15, 16]                     # cycle.*
        )

    # 動的オブジェクトの点をフィルタ
    dynamic_mask = np.isin(labels, dynamic_classes)
    dynamic_points = points_world[dynamic_mask]

    if len(dynamic_points) == 0:
        # 動的点がない場合は全体を学習対象とする（Nerfstudio規約: 255=include）
        return np.full((h, w), 255, dtype=np.uint8)

    # 2D投影（既存の関数を利用）
    uv, _, _ = project_points_to_image(dynamic_points, w2c, K, image_shape)

    # バイナリマスクを初期化
    mask = np.zeros((h, w), dtype=np.uint8)

    # 投影された点の位置に円を描画（半径3ピクセル）
    # LiDAR点は疎なので、各点を小さい円として描画することで連続した領域を作る
    for u, v in uv:
        u_int, v_int = int(round(u)), int(round(v))
        if 0 <= u_int < w and 0 <= v_int < h:
            # 1ピクセルではなく、半径3の円として描画
            cv2.circle(mask, (u_int, v_int), radius=3, color=255, thickness=-1)

    # モルフォロジー膨張を適用
    if dilation_size > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
        mask = cv2.dilate(mask, kernel, iterations=1)

    # Nerfstudio規約に合わせてマスクを反転
    # Nerfstudio: 0=exclude from training (dynamic), 255=include (static)
    # 現在のmask: 動的領域=255, 静的領域=0 → 反転が必要
    mask = cv2.bitwise_not(mask)

    return mask


def generate_lidar_masks_for_scene(
    nusc,
    scene_token: str,
    output_dir: Path,
    dynamic_classes: list[int] | None = None,
    dilation_size: int = 8,
) -> dict[int, Path]:
    """シーン全体の全フレームについてLiDARマスクを生成.

    Args:
        nusc: NuScenes instance
        scene_token: Scene token
        output_dir: Output directory for masks
        dynamic_classes: List of semantic class IDs to mask. If None, use default.
        dilation_size: Morphological dilation kernel size

    Returns:
        Dictionary mapping frame_idx to mask_path
    """
    from pathlib import Path

    scene = nusc.get("scene", scene_token)
    masks_dir = Path(output_dir) / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    mask_paths = {}
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

        # マスク生成
        mask = project_lidar_to_mask(
            points_world,
            labels,
            w2c,
            K,
            image_shape,
            dynamic_classes=dynamic_classes,
            dilation_size=dilation_size,
        )

        # マスクを保存
        mask_path = masks_dir / f"{frame_idx:04d}.png"
        cv2.imwrite(str(mask_path), mask)
        mask_paths[frame_idx] = mask_path

        # 次のフレームへ
        sample_token = sample["next"] if sample["next"] else None
        frame_idx += 1

    return mask_paths


def get_bbox_corners_3d(bbox_center: np.ndarray, bbox_size: np.ndarray, bbox_rotation: np.ndarray) -> np.ndarray:
    """3D bounding box の 8 corners を計算.

    Args:
        bbox_center: (3,) bbox center in world frame [x, y, z]
        bbox_size: (3,) bbox size [width, length, height]
        bbox_rotation: (3, 3) rotation matrix

    Returns:
        corners: (8, 3) bbox corners in world frame
    """
    # bbox の半分のサイズ
    w, l, h = bbox_size

    # bbox center を原点とした 8 corners（ローカル座標）
    # nuScenes の座標系: x=前, y=左, z=上
    corners_local = np.array([
        [-l/2, -w/2, -h/2],
        [ l/2, -w/2, -h/2],
        [ l/2,  w/2, -h/2],
        [-l/2,  w/2, -h/2],
        [-l/2, -w/2,  h/2],
        [ l/2, -w/2,  h/2],
        [ l/2,  w/2,  h/2],
        [-l/2,  w/2,  h/2],
    ])

    # 回転を適用
    corners_rotated = (bbox_rotation @ corners_local.T).T

    # 平行移動を適用
    corners_world = corners_rotated + bbox_center

    return corners_world


def project_bbox_to_image(
    bbox_center: np.ndarray,
    bbox_size: np.ndarray,
    bbox_rotation: np.ndarray,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
) -> tuple[np.ndarray | None, bool]:
    """3D bounding box を 2D 画像に投影.

    Args:
        bbox_center: (3,) bbox center in world frame [x, y, z]
        bbox_size: (3,) bbox size [width, length, height]
        bbox_rotation: (3, 3) rotation matrix
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)

    Returns:
        corners_2d: (N, 2) 2D corners in image, or None if not visible
        is_visible: bool indicating if bbox is visible in camera view
    """
    h, w = image_shape

    # 3D corners を取得
    corners_3d = get_bbox_corners_3d(bbox_center, bbox_size, bbox_rotation)

    # World → camera 座標系に変換
    corners_homo = np.hstack([corners_3d, np.ones((8, 1))])
    corners_cam_homo = (w2c @ corners_homo.T).T  # (8, 4)
    corners_cam = corners_cam_homo[:, :3]  # (8, 3)

    # カメラ背後の点をチェック
    in_front = corners_cam[:, 2] > 0
    if not in_front.any():
        # 全ての corners がカメラ背後 → 見えない
        return None, False

    # 2D 投影
    corners_2d_homo = (K @ corners_cam.T).T  # (8, 3)
    corners_2d = corners_2d_homo[:, :2] / corners_2d_homo[:, 2:3]  # (8, 2)

    # カメラ背後の点を除外
    corners_2d_visible = corners_2d[in_front]

    # 画像境界内にあるかチェック
    in_bounds = (
        (corners_2d_visible[:, 0] >= 0) & (corners_2d_visible[:, 0] < w) &
        (corners_2d_visible[:, 1] >= 0) & (corners_2d_visible[:, 1] < h)
    )

    # 少なくとも 1 点が画像内にあれば可視と判定
    is_visible = in_bounds.any()

    return corners_2d_visible, is_visible


def draw_bbox_on_image(
    image: np.ndarray,
    corners_2d: np.ndarray,
    category_name: str,
    color: tuple[int, int, int] = (0, 255, 0),
    thickness: int = 2,
) -> np.ndarray:
    """2D corners から bounding box を画像に描画.

    Args:
        image: (H, W, 3) RGB image
        corners_2d: (N, 2) 2D corners
        category_name: bbox の category 名
        color: RGB color tuple
        thickness: line thickness

    Returns:
        image: (H, W, 3) RGB image with bbox drawn
    """
    if len(corners_2d) < 2:
        # 点が少なすぎる場合はスキップ
        return image

    # corners_2d を整数に変換
    corners_int = corners_2d.astype(np.int32)

    # 凸包を計算して polygon を描画
    from scipy.spatial import ConvexHull
    try:
        hull = ConvexHull(corners_int)
        hull_points = corners_int[hull.vertices]
        cv2.polylines(image, [hull_points], isClosed=True, color=color, thickness=thickness)

        # category name を表示
        # polygon の中心を計算
        center = hull_points.mean(axis=0).astype(int)
        cv2.putText(
            image,
            category_name.split('.')[-1],  # "vehicle.car" -> "car"
            tuple(center),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            thickness=1,
        )
    except:
        # ConvexHull が失敗した場合は、単純に点を線で結ぶ
        for i in range(len(corners_int)):
            pt1 = tuple(corners_int[i])
            pt2 = tuple(corners_int[(i + 1) % len(corners_int)])
            cv2.line(image, pt1, pt2, color, thickness)

    return image


def project_bbox_to_mask(
    bbox_center: np.ndarray,
    bbox_size: np.ndarray,
    bbox_rotation: np.ndarray,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
) -> np.ndarray | None:
    """単一の3D bounding boxから2Dバイナリマスクを生成.

    Args:
        bbox_center: (3,) bbox center in world frame [x, y, z]
        bbox_size: (3,) bbox size [width, length, height]
        bbox_rotation: (3, 3) rotation matrix
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)

    Returns:
        Binary mask (H, W) uint8 (255=bbox領域, 0=背景), or None if not visible
    """
    h, w = image_shape

    # bbox を 2D に投影
    corners_2d, is_visible = project_bbox_to_image(
        bbox_center, bbox_size, bbox_rotation, w2c, K, image_shape
    )

    if not is_visible or corners_2d is None:
        return None

    # マスク初期化
    mask = np.zeros((h, w), dtype=np.uint8)

    # corners_2d を整数に変換
    corners_int = corners_2d.astype(np.int32)

    # 凸包を計算してpolygonを塗りつぶし
    from scipy.spatial import ConvexHull
    try:
        hull = ConvexHull(corners_int)
        hull_points = corners_int[hull.vertices]
        cv2.fillPoly(mask, [hull_points], color=255)
    except:
        # ConvexHullが失敗した場合は、全ての点を含む最小矩形を使用
        x_min = max(0, int(corners_int[:, 0].min()))
        x_max = min(w, int(corners_int[:, 0].max()))
        y_min = max(0, int(corners_int[:, 1].min()))
        y_max = min(h, int(corners_int[:, 1].max()))
        mask[y_min:y_max, x_min:x_max] = 255

    return mask


def project_bboxes_to_mask(
    nusc,
    sample: dict,
    w2c: np.ndarray,
    K: np.ndarray,
    image_shape: tuple[int, int],
    dynamic_categories: list[str] | None = None,
    dilation_size: int = 5,
) -> np.ndarray:
    """1フレームの全bboxから統合された2Dバイナリマスクを生成.

    Args:
        nusc: NuScenes instance
        sample: sample データ
        w2c: 4x4 world-to-camera transform matrix
        K: 3x3 camera intrinsic matrix
        image_shape: (height, width)
        dynamic_categories: マスク対象のcategory prefix list. If None, use default.
        dilation_size: Morphological dilation kernel size

    Returns:
        Binary mask (H, W) uint8 (Nerfstudio convention: 0=exclude, 255=include)
    """
    from pyquaternion import Quaternion

    h, w = image_shape

    # デフォルトの動的category
    if dynamic_categories is None:
        dynamic_categories = ["vehicle.", "human.", "cycle."]

    # マスク初期化（全て0 = 動的領域なし）
    combined_mask = np.zeros((h, w), dtype=np.uint8)

    # 各annotationを処理
    for ann_token in sample["anns"]:
        ann = nusc.get("sample_annotation", ann_token)
        category_name = ann["category_name"]

        # 動的カテゴリかチェック
        is_dynamic = any(category_name.startswith(prefix) for prefix in dynamic_categories)
        if not is_dynamic:
            continue

        # bbox パラメータを取得
        bbox_center = np.array(ann["translation"])
        bbox_size = np.array(ann["size"])
        bbox_rotation = Quaternion(ann["rotation"]).rotation_matrix

        # マスク生成
        bbox_mask = project_bbox_to_mask(
            bbox_center, bbox_size, bbox_rotation, w2c, K, image_shape
        )

        if bbox_mask is not None:
            # 論理和（複数のbboxを統合）
            combined_mask = cv2.bitwise_or(combined_mask, bbox_mask)

    # モルフォロジー膨張を適用
    if dilation_size > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation_size, dilation_size))
        combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)

    # Nerfstudio規約に合わせてマスクを反転
    # Nerfstudio: 0=exclude from training (dynamic), 255=include (static)
    # 現在のcombined_mask: 動的領域=255, 静的領域=0 → 反転が必要
    combined_mask = cv2.bitwise_not(combined_mask)

    return combined_mask


def generate_bbox_masks_for_scene(
    nusc,
    scene_token: str,
    output_dir: Path,
    dynamic_categories: list[str] | None = None,
    dilation_size: int = 5,
) -> dict[int, Path]:
    """シーン全体の全フレームについてbboxマスクを生成.

    Args:
        nusc: NuScenes instance
        scene_token: Scene token
        output_dir: Output directory for masks
        dynamic_categories: マスク対象のcategory prefix list. If None, use default.
        dilation_size: Morphological dilation kernel size

    Returns:
        Dictionary mapping frame_idx to mask_path
    """
    scene = nusc.get("scene", scene_token)
    masks_dir = Path(output_dir) / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)

    mask_paths = {}
    sample_token = scene["first_sample_token"]
    frame_idx = 0

    while sample_token:
        sample = nusc.get("sample", sample_token)

        # CAM_FRONT データを取得
        cam_token = sample["data"]["CAM_FRONT"]
        cam_data = nusc.get("sample_data", cam_token)

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

        # マスク生成
        mask = project_bboxes_to_mask(
            nusc,
            sample,
            w2c,
            K,
            image_shape,
            dynamic_categories=dynamic_categories,
            dilation_size=dilation_size,
        )

        # マスクを保存
        mask_path = masks_dir / f"{frame_idx:04d}.png"
        cv2.imwrite(str(mask_path), mask)
        mask_paths[frame_idx] = mask_path

        # 次のフレームへ
        sample_token = sample["next"] if sample["next"] else None
        frame_idx += 1

    return mask_paths
