#!/usr/bin/env python3
"""Phase 3 用の深度マップ付き CAM_FRONT データエクスポート."""

import argparse
from pathlib import Path

from nuscenes.nuscenes import NuScenes

from nuscenes_gs.nerfstudio_export import export_scene_front_with_depth


def main():
    parser = argparse.ArgumentParser(
        description="Export CAM_FRONT with sparse depth maps for Phase 3"
    )
    parser.add_argument(
        "--dataroot",
        type=str,
        required=True,
        help="Path to nuScenes data root",
    )
    parser.add_argument(
        "--scene-index",
        type=int,
        default=0,
        help="Scene index in nuScenes v1.0-mini (0-9)",
    )
    parser.add_argument(
        "--mask-type",
        type=str,
        choices=["lidar", "bbox", "none"],
        default="none",
        help='Mask type: "lidar" (LiDAR segmentation), "bbox" (3D bbox), "none" (no mask)',
    )
    parser.add_argument(
        "--dilation",
        type=int,
        default=None,
        help="Morphological dilation kernel size (default: 64 for lidar, 5 for bbox)",
    )
    parser.add_argument(
        "--depth-range",
        nargs=2,
        type=float,
        default=[0.1, 80.0],
        help="Depth range in meters (default: 0.1 80.0)",
    )
    args = parser.parse_args()

    # NuScenes読み込み
    print(f"Loading nuScenes from {args.dataroot}...")
    nusc = NuScenes(version="v1.0-mini", dataroot=args.dataroot, verbose=True)

    # シーン取得
    scene = nusc.scene[args.scene_index]
    scene_name = scene["name"]
    print(f"\nExporting scene: {scene_name} (index: {args.scene_index})")

    # 出力ディレクトリ
    suffix = ""
    if args.mask_type != "none":
        suffix = f"_{args.mask_type}_masked"
    output_dir = Path(f"data/derived/{scene_name}_front_depth{suffix}")
    print(f"Output directory: {output_dir}")

    # マスクパラメータ
    mask_type = None if args.mask_type == "none" else args.mask_type
    mask_params = {}
    if mask_type == "lidar":
        mask_params["dilation_size"] = args.dilation or 64
    elif mask_type == "bbox":
        mask_params["dilation_size"] = args.dilation or 5

    # エクスポート実行
    export_scene_front_with_depth(
        nusc,
        scene["token"],
        output_dir,
        mask_type=mask_type,
        mask_params=mask_params,
        depth_range=tuple(args.depth_range),
    )

    print(f"\n✓ Export complete!")
    print(f"  Images: {len(list((output_dir / 'images').glob('*.jpg')))} files")
    print(f"  Depth maps: {len(list((output_dir / 'depth').glob('*.png')))} files")
    if mask_type:
        print(f"  Masks: {len(list((output_dir / 'masks').glob('*.png')))} files")
    print(f"  Config: {output_dir / 'transforms.json'}")


if __name__ == "__main__":
    main()
