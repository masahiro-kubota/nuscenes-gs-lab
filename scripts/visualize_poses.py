"""transforms.json のカメラポーズを3Dプロットで可視化するスクリプト."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Visualize camera poses from a Nerfstudio transforms.json"
    )
    parser.add_argument(
        "transforms",
        type=str,
        help="Path to transforms.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output PNG path (default: same dir as transforms.json)",
    )
    parser.add_argument(
        "--arrow-length",
        type=float,
        default=2.0,
        help="Length of camera direction arrows (default: 2.0)",
    )
    args = parser.parse_args()

    transforms_path = Path(args.transforms)
    with open(transforms_path) as f:
        data = json.load(f)

    frames = data["frames"]
    positions = []
    forwards = []

    for frame in frames:
        c2w = np.array(frame["transform_matrix"])
        # カメラ位置: c2w の平行移動列
        positions.append(c2w[:3, 3])
        # カメラ前方向: OpenGL 系なので -z 軸が前方
        forwards.append(-c2w[:3, 2])

    positions = np.array(positions)
    forwards = np.array(forwards)

    # --- プロット ---
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # 軌跡
    ax.plot(
        positions[:, 0], positions[:, 1], positions[:, 2],
        "b-", alpha=0.4, linewidth=1,
    )

    # カメラ位置
    ax.scatter(
        positions[:, 0], positions[:, 1], positions[:, 2],
        c=np.arange(len(positions)), cmap="viridis", s=30, zorder=5,
    )

    # 前方向の矢印
    scale = args.arrow_length
    for i, (pos, fwd) in enumerate(zip(positions, forwards)):
        ax.quiver(
            pos[0], pos[1], pos[2],
            fwd[0] * scale, fwd[1] * scale, fwd[2] * scale,
            color="red", alpha=0.5, arrow_length_ratio=0.15,
        )

    # 始点・終点ラベル
    ax.text(*positions[0], " start", fontsize=8)
    ax.text(*positions[-1], " end", fontsize=8)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title(f"Camera Poses ({len(frames)} frames)")

    # アスペクト比を揃える
    all_coords = positions
    center = all_coords.mean(axis=0)
    max_range = (all_coords.max(axis=0) - all_coords.min(axis=0)).max() / 2
    margin = max_range * 0.2
    ax.set_xlim(center[0] - max_range - margin, center[0] + max_range + margin)
    ax.set_ylim(center[1] - max_range - margin, center[1] + max_range + margin)
    ax.set_zlim(center[2] - max_range - margin, center[2] + max_range + margin)

    # 保存
    output_path = args.output or str(transforms_path.parent / "poses.png")
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")

    # サマリ
    z_vals = positions[:, 2]
    print(f"  frames: {len(frames)}")
    print(f"  X range: {positions[:, 0].min():.1f} ~ {positions[:, 0].max():.1f}")
    print(f"  Y range: {positions[:, 1].min():.1f} ~ {positions[:, 1].max():.1f}")
    print(f"  Z (height) range: {z_vals.min():.2f} ~ {z_vals.max():.2f}")


if __name__ == "__main__":
    main()
