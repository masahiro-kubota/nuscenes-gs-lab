"""Streamlit インタラクティブポーズビューア.

起動: uv run streamlit run scripts/pose_viewer.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st

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
        st.image(str(img_path), caption=f"Frame {frame_idx} / {n_frames - 1}  —  {frames[frame_idx]['file_path']}")
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
