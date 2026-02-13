"""CAM_FRONT + LiDAR マスクを 1シーン分エクスポートするスクリプト."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# src/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nuscenes.nuscenes import NuScenes

from nuscenes_gs.nerfstudio_export import export_scene_front_with_lidar_masks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export CAM_FRONT with LiDAR masks from a nuScenes scene to Nerfstudio format"
    )
    parser.add_argument(
        "--dataroot",
        type=str,
        default="data/raw",
        help="nuScenes dataroot path",
    )
    parser.add_argument(
        "--scene-index",
        type=int,
        default=0,
        help="Scene index to export (default: 0)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: data/derived/scene-XXXX_front_lidar_masked)",
    )
    parser.add_argument(
        "--dynamic-classes",
        nargs="+",
        type=int,
        default=None,
        help="Semantic class IDs to mask (default: vehicle/human/cycle)",
    )
    parser.add_argument(
        "--dilation",
        type=int,
        default=8,
        help="Morphological dilation kernel size (default: 8)",
    )
    args = parser.parse_args()

    print(f"Loading nuScenes mini from {args.dataroot} ...")
    nusc = NuScenes(version="v1.0-mini", dataroot=args.dataroot, verbose=False)

    scene = nusc.scene[args.scene_index]
    scene_name = scene["name"]
    print(f"Scene: {scene_name} ({scene['description']})")

    output_dir = args.output or f"data/derived/{scene_name}_front_lidar_masked"

    print(f"Exporting with LiDAR masks (point_radius=3, dilation={args.dilation})...")
    out_path = export_scene_front_with_lidar_masks(
        nusc,
        scene["token"],
        output_dir,
        dynamic_classes=args.dynamic_classes,
        dilation_size=args.dilation,
    )
    print(f"Exported -> {out_path}")

    # サマリ表示
    import json

    with open(out_path) as f:
        data = json.load(f)
    print(f"  frames: {len(data['frames'])}")
    print(f"  resolution: {data['w']}x{data['h']}")
    print(f"  fl_x: {data['fl_x']:.1f}, fl_y: {data['fl_y']:.1f}")
    print(f"  cx: {data['cx']:.1f}, cy: {data['cy']:.1f}")

    # マスク統計
    masks_dir = Path(output_dir) / "masks"
    mask_files = list(masks_dir.glob("*.png"))
    print(f"\nMasks:")
    print(f"  count: {len(mask_files)}")
    print(f"  directory: {masks_dir}")


if __name__ == "__main__":
    main()
