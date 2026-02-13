"""Streamlit インタラクティブポーズビューア.

起動: uv run streamlit run scripts/pose_viewer.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# src ディレクトリを Python パスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

st.set_page_config(layout="wide", page_title="Pose Viewer")

# --- サイドバー: データ選択 ---

derived_dir = Path("data/derived")
available = sorted(derived_dir.glob("*/transforms.json")) if derived_dir.exists() else []

if not available:
    st.error("data/derived/ に transforms.json が見つかりません。先に export を実行してください。")
    st.stop()

scene_options = {p.parent.name: p for p in available}
selected_scene = st.sidebar.selectbox("Scene", list(scene_options.keys()))
transforms_path = scene_options[selected_scene]

# --- 表示モード設定 ---
st.sidebar.markdown("---")
st.sidebar.subheader("Display Mode")
display_mode = st.sidebar.radio(
    "Select Mode",
    ["Image Only", "Image + LiDAR", "LiDAR Only"],
    index=0
)

# LiDAR が必要な場合のみ nuScenes を読み込む
show_lidar = display_mode in ["Image + LiDAR", "LiDAR Only"]
nusc = None
has_lidarseg = False
if show_lidar:
    try:
        from nuscenes.nuscenes import NuScenes
        from nuscenes_gs.masks import (
            compute_w2c,
            create_label_overlay,
            load_lidar_points_and_labels,
            project_points_to_image,
            transform_lidar_to_world,
        )

        # nuScenes 読み込み
        @st.cache_resource
        def load_nuscenes(dataroot: str):
            return NuScenes(version="v1.0-mini", dataroot=dataroot, verbose=False)

        dataroot = st.sidebar.text_input("NuScenes dataroot", "data/raw")
        nusc = load_nuscenes(dataroot)

        # lidarseg データパックの確認
        try:
            sample_token = nusc.sample[0]["data"]["LIDAR_TOP"]
            nusc.get("lidarseg", sample_token)
            has_lidarseg = True
        except:
            has_lidarseg = False
            st.sidebar.warning("⚠ nuScenes-lidarseg データパック未検出")
    except Exception as e:
        st.sidebar.error(f"nuScenes 読み込みエラー: {e}")
        show_lidar = False

# --- データ読み込み ---

@st.cache_data
def load_transforms(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


data = load_transforms(str(transforms_path))
frames = data["frames"]
n_frames = len(frames)

positions = np.array([np.array(f["transform_matrix"])[:3, 3] for f in frames])
forwards = np.array([-np.array(f["transform_matrix"])[:3, 2] for f in frames])

# --- フレーム選択 ---

frame_idx = st.slider("Frame", 0, n_frames - 1, 0)

# --- レイアウト ---

col_plot, col_image = st.columns([1, 1])

# --- 左: 3D プロット ---

with col_plot:
    fig = go.Figure()

    # 軌跡ライン
    fig.add_trace(go.Scatter3d(
        x=positions[:, 0], y=positions[:, 1], z=positions[:, 2],
        mode="lines",
        line=dict(color="steelblue", width=3),
        name="trajectory",
        hoverinfo="skip",
    ))

    # 全フレームポイント
    fig.add_trace(go.Scatter3d(
        x=positions[:, 0], y=positions[:, 1], z=positions[:, 2],
        mode="markers",
        marker=dict(
            size=4,
            color=np.arange(n_frames),
            colorscale="Viridis",
            showscale=False,
        ),
        text=[f"Frame {i}" for i in range(n_frames)],
        hoverinfo="text",
        name="frames",
    ))

    # 選択フレーム（赤）
    pos = positions[frame_idx]
    fig.add_trace(go.Scatter3d(
        x=[pos[0]], y=[pos[1]], z=[pos[2]],
        mode="markers",
        marker=dict(size=8, color="red"),
        name=f"selected ({frame_idx})",
        hoverinfo="skip",
    ))

    # 前方向の矢印（コーン）
    fwd = forwards[frame_idx]
    arrow_len = 3.0
    fig.add_trace(go.Cone(
        x=[pos[0]], y=[pos[1]], z=[pos[2]],
        u=[fwd[0] * arrow_len],
        v=[fwd[1] * arrow_len],
        w=[fwd[2] * arrow_len],
        sizemode="absolute",
        sizeref=1.5,
        colorscale=[[0, "red"], [1, "red"]],
        showscale=False,
        name="direction",
        hoverinfo="skip",
    ))

    # アスペクト比を揃える
    center = positions.mean(axis=0)
    max_range = (positions.max(axis=0) - positions.min(axis=0)).max() / 2
    margin = max_range * 0.2

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[center[0] - max_range - margin, center[0] + max_range + margin]),
            yaxis=dict(range=[center[1] - max_range - margin, center[1] + max_range + margin]),
            zaxis=dict(range=[center[2] - max_range - margin, center[2] + max_range + margin]),
            aspectmode="cube",
        ),
        margin=dict(l=0, r=0, t=30, b=0),
        height=500,
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

# --- 右: 画像 + メタデータ ---

with col_image:
    img_path = transforms_path.parent / frames[frame_idx]["file_path"]

    if img_path.exists():
        img = Image.open(img_path)

        # LiDAR overlay の処理
        if show_lidar and nusc and has_lidarseg:
            try:
                # シーン名をディレクトリ名から抽出
                dir_name = transforms_path.parent.name
                # "scene-0757_front" -> "scene-0757" または "scene-0061_front" -> "scene-0061"
                if "_front" in dir_name:
                    scene_name = dir_name.replace("_front", "")
                else:
                    scene_name = dir_name.split("_")[0]

                st.sidebar.info(f"Debug: シーン名={scene_name}, フレーム={frame_idx}")

                # シーンを検索
                scene_idx = [s["name"] for s in nusc.scene].index(scene_name)
                scene = nusc.scene[scene_idx]

                # フレーム token を取得
                sample_token = scene["first_sample_token"]
                for _ in range(frame_idx):
                    sample = nusc.get("sample", sample_token)
                    sample_token = sample["next"]
                    if not sample_token:
                        break

                if sample_token:
                    sample = nusc.get("sample", sample_token)
                    cam_token = sample["data"]["CAM_FRONT"]
                    lidar_token = sample["data"]["LIDAR_TOP"]

                    # データ取得
                    cam_data = nusc.get("sample_data", cam_token)
                    lidar_data = nusc.get("sample_data", lidar_token)

                    # LiDAR 点群と labels 読み込み
                    points_lidar, labels = load_lidar_points_and_labels(nusc, lidar_token)

                    # 座標変換
                    lidar_ego_pose = nusc.get("ego_pose", lidar_data["ego_pose_token"])
                    lidar_calib = nusc.get("calibrated_sensor", lidar_data["calibrated_sensor_token"])
                    points_world = transform_lidar_to_world(points_lidar, lidar_ego_pose, lidar_calib)

                    # カメラパラメータ
                    cam_ego_pose = nusc.get("ego_pose", cam_data["ego_pose_token"])
                    cam_calib = nusc.get("calibrated_sensor", cam_data["calibrated_sensor_token"])
                    w2c = compute_w2c(cam_ego_pose, cam_calib)

                    # intrinsics
                    K = np.array(cam_calib["camera_intrinsic"])
                    image_shape = (img.height, img.width)

                    # 2D 投影
                    uv, valid_mask, distances = project_points_to_image(points_world, w2c, K, image_shape)
                    valid_labels = labels[valid_mask]

                    st.sidebar.success(f"Debug: 投影点数={len(uv)}/{len(points_lidar)}")
                    st.sidebar.info(f"Debug: 距離範囲={distances.min():.1f}m ~ {distances.max():.1f}m")

                    # オーバーレイ生成（距離ベースの色分け）
                    overlay = create_label_overlay(image_shape, uv, valid_labels, distances=distances, point_radius=5)

                    # デバッグ: overlay のピクセル数を確認
                    overlay_pixels = (overlay.sum(axis=2) > 0).sum()
                    st.sidebar.info(f"Debug: overlay ピクセル数={overlay_pixels}")

                    # 表示モードに応じた処理
                    if display_mode == "Image + LiDAR":
                        # 2D画像とオーバーレイを合成
                        img_array = np.array(img)
                        overlay_mask = overlay.sum(axis=2) > 0
                        img_array[overlay_mask] = (img_array[overlay_mask] * 0.3 + overlay[overlay_mask] * 0.7).astype(np.uint8)
                        img_with_overlay = Image.fromarray(img_array)
                        st.image(img_with_overlay, caption=f"Frame {frame_idx} (with LiDAR)", use_container_width=True)

                    elif display_mode == "LiDAR Only":
                        # 3D点群ビュー
                        # カメラ位置を取得
                        cam_pos = np.array(cam_ego_pose["translation"])

                        # 距離で色分け（RGB値を計算）
                        min_dist = distances.min()
                        max_dist = distances.max()
                        normalized_dist = (distances - min_dist) / (max_dist - min_dist + 1e-6)

                        # RGB配列を生成
                        colors = []
                        for dist_norm in normalized_dist:
                            if dist_norm < 0.33:
                                r, g, b = 0, int(255 * (dist_norm / 0.33)), int(255 * (1 - dist_norm / 0.33))
                            elif dist_norm < 0.67:
                                r, g, b = int(255 * ((dist_norm - 0.33) / 0.34)), 255, 0
                            else:
                                r, g, b = 255, int(255 * (1 - (dist_norm - 0.67) / 0.33)), 0
                            colors.append(f'rgb({r},{g},{b})')

                        # 画像境界内の点のworld座標を取得
                        valid_points_world = points_world[valid_mask]

                        # 3D scatter plot
                        fig_3d = go.Figure()

                        # LiDAR点群
                        fig_3d.add_trace(go.Scatter3d(
                            x=valid_points_world[:, 0],
                            y=valid_points_world[:, 1],
                            z=valid_points_world[:, 2],
                            mode='markers',
                            marker=dict(
                                size=2,
                                color=colors,
                                opacity=0.6
                            ),
                            name='LiDAR points',
                            hovertemplate='<b>Position</b><br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
                        ))

                        # カメラ位置
                        fig_3d.add_trace(go.Scatter3d(
                            x=[cam_pos[0]],
                            y=[cam_pos[1]],
                            z=[cam_pos[2]],
                            mode='markers',
                            marker=dict(size=8, color='red', symbol='diamond'),
                            name='Camera',
                            hovertemplate='<b>Camera</b><br>X: %{x:.2f}<br>Y: %{y:.2f}<br>Z: %{z:.2f}<extra></extra>'
                        ))

                        # カメラの向き（矢印）
                        c2w_opencv = np.linalg.inv(w2c)
                        cam_forward = -c2w_opencv[:3, 2]  # OpenCV: z軸の負方向が前
                        arrow_len = 5.0
                        fig_3d.add_trace(go.Scatter3d(
                            x=[cam_pos[0], cam_pos[0] + cam_forward[0] * arrow_len],
                            y=[cam_pos[1], cam_pos[1] + cam_forward[1] * arrow_len],
                            z=[cam_pos[2], cam_pos[2] + cam_forward[2] * arrow_len],
                            mode='lines',
                            line=dict(color='red', width=4),
                            name='Camera direction',
                            showlegend=False
                        ))

                        # レイアウト設定
                        fig_3d.update_layout(
                            scene=dict(
                                aspectmode='data',
                                xaxis_title='X (m)',
                                yaxis_title='Y (m)',
                                zaxis_title='Z (m)',
                                camera=dict(
                                    eye=dict(x=1.5, y=1.5, z=1.5)
                                )
                            ),
                            margin=dict(l=0, r=0, t=30, b=0),
                            height=500,
                            title=f"3D LiDAR Point Cloud (Frame {frame_idx})"
                        )

                        st.plotly_chart(fig_3d, use_container_width=True)
                else:
                    st.image(img, caption=f"Frame {frame_idx} / {n_frames - 1}  —  {frames[frame_idx]['file_path']}", use_container_width=True)
                    st.warning(f"フレーム {frame_idx} のデータが見つかりません")
            except Exception as e:
                st.image(img, caption=f"Frame {frame_idx} / {n_frames - 1}  —  {frames[frame_idx]['file_path']}", use_container_width=True)
                st.error(f"LiDAR overlay エラー: {e}")
        else:
            st.image(img, caption=f"Frame {frame_idx} / {n_frames - 1}  —  {frames[frame_idx]['file_path']}", use_container_width=True)
    else:
        st.warning(f"画像が見つかりません: {img_path}")

    fwd = forwards[frame_idx]

    # 速度計算（前フレームとの距離 / 0.5秒）
    if frame_idx > 0:
        prev_pos = positions[frame_idx - 1]
        dist = np.linalg.norm(pos - prev_pos)
        speed_ms = dist / 0.5  # m/s (2Hz = 0.5秒間隔)
        speed_kmh = speed_ms * 3.6  # km/h
        speed_str = f"{speed_kmh:.1f} km/h ({speed_ms:.2f} m/s)"
    else:
        speed_str = "N/A (first frame)"

    st.code(
        f"Position : ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.2f})\n"
        f"Height   : {pos[2]:.2f} m\n"
        f"Forward  : ({fwd[0]:.3f}, {fwd[1]:.3f}, {fwd[2]:.3f})\n"
        f"Speed    : {speed_str}",
        language=None,
    )

    # intrinsics
    st.caption(
        f"Intrinsics: fl={data['fl_x']:.1f}  cx={data['cx']:.1f}  cy={data['cy']:.1f}  "
        f"({data['w']}x{data['h']})"
    )
