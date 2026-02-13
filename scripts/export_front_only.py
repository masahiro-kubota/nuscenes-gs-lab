"""CAM_FRONT を 1シーン分エクスポートするスクリプト."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# src/ をインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nuscenes.nuscenes import NuScenes

from nuscenes_gs.nerfstudio_export import export_scene_front


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export CAM_FRONT from a nuScenes scene to Nerfstudio format"
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
        help="Output directory (default: data/derived/scene-XXXX_front)",
    )
    args = parser.parse_args()

    print(f"Loading nuScenes mini from {args.dataroot} ...")
    nusc = NuScenes(version="v1.0-mini", dataroot=args.dataroot, verbose=False)

    scene = nusc.scene[args.scene_index]
    scene_name = scene["name"]
    print(f"Scene: {scene_name} ({scene['description']})")

    output_dir = args.output or f"data/derived/{scene_name}_front"

    out_path = export_scene_front(nusc, scene["token"], output_dir)
    print(f"Exported -> {out_path}")

    # サマリ表示
    import json

    with open(out_path) as f:
        data = json.load(f)
    print(f"  frames: {len(data['frames'])}")
    print(f"  resolution: {data['w']}x{data['h']}")
    print(f"  fl_x: {data['fl_x']:.1f}, fl_y: {data['fl_y']:.1f}")
    print(f"  cx: {data['cx']:.1f}, cy: {data['cy']:.1f}")


if __name__ == "__main__":
    main()
