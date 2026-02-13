#!/usr/bin/env python3
"""Phase 1 用の 3D bbox マスク付き CAM_FRONT データエクスポート."""

import argparse
from pathlib import Path

from nuscenes.nuscenes import NuScenes

from nuscenes_gs.nerfstudio_export import export_scene_front_with_bbox_masks


def main():
    parser = argparse.ArgumentParser(
        description="Export CAM_FRONT with 3D bbox masks for Phase 1"
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
        "--dynamic-categories",
        nargs="+",
        type=str,
        default=None,
        help='Category prefixes to mask (default: ["vehicle.", "human.", "cycle."])',
    )
    parser.add_argument(
        "--dilation",
        type=int,
        default=5,
        help="Morphological dilation kernel size (default: 5)",
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
    output_dir = Path(f"data/derived/{scene_name}_front_bbox_masked")
    print(f"Output directory: {output_dir}")

    # エクスポート実行
    export_scene_front_with_bbox_masks(
        nusc,
        scene["token"],
        output_dir,
        dynamic_categories=args.dynamic_categories,
        dilation_size=args.dilation,
    )

    print(f"\n✓ Export complete!")
    print(f"  Images: {len(list((output_dir / 'images').glob('*.jpg')))} files")
    print(f"  Masks: {len(list((output_dir / 'masks').glob('*.png')))} files")
    print(f"  Config: {output_dir / 'transforms.json'}")


if __name__ == "__main__":
    main()
