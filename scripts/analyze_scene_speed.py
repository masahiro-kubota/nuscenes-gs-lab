#!/usr/bin/env python3
"""nuScenes mini の各シーンの平均速度を分析"""

import argparse
import numpy as np
from nuscenes.nuscenes import NuScenes


def analyze_scene_speeds(nusc: NuScenes):
    """各シーンの平均速度・停止割合を計算"""
    results = []

    for scene in nusc.scene:
        sample_token = scene["first_sample_token"]
        speeds = []
        prev_pos = None

        while sample_token:
            sample = nusc.get("sample", sample_token)
            cam_token = sample["data"]["CAM_FRONT"]
            cam_data = nusc.get("sample_data", cam_token)
            ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])

            pos = np.array(ego_pose["translation"])

            if prev_pos is not None:
                # 2Hz サンプリング → 0.5秒間隔
                dist = np.linalg.norm(pos - prev_pos)
                speed = dist / 0.5  # m/s
                speeds.append(speed)

            prev_pos = pos
            sample_token = sample["next"] if sample["next"] else None

        avg_speed = np.mean(speeds) if speeds else 0
        stop_ratio = np.sum(np.array(speeds) < 1.0) / len(speeds) if speeds else 0

        results.append({
            "name": scene["name"],
            "avg_speed_ms": avg_speed,
            "avg_speed_kmh": avg_speed * 3.6,
            "stop_ratio": stop_ratio,
            "n_frames": len(speeds) + 1
        })

    return sorted(results, key=lambda x: x["avg_speed_ms"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataroot", type=str, default="data/raw")
    args = parser.parse_args()

    nusc = NuScenes(version="v1.0-mini", dataroot=args.dataroot, verbose=True)
    results = analyze_scene_speeds(nusc)

    print("\n=== Scene Speed Analysis ===")
    print(f"{'Scene':<15} {'Frames':<8} {'Avg Speed (km/h)':<18} {'Stop Ratio':<12}")
    print("-" * 60)
    for r in results:
        print(f"{r['name']:<15} {r['n_frames']:<8} {r['avg_speed_kmh']:>10.1f}       {r['stop_ratio']:>8.1%}")

    print("\n推奨: 低速シーン（< 20 km/h）または停止率が高いシーンを選択")
    print(f"最も低速: {results[0]['name']} ({results[0]['avg_speed_kmh']:.1f} km/h)")


if __name__ == "__main__":
    main()
