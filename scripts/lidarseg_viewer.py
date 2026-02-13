#!/usr/bin/env python3
"""LiDAR segmentation 可視化ツール

使用方法:
  uv run streamlit run scripts/lidarseg_viewer.py

機能:
  - シーン速度分析結果の表示
  - LiDAR点群のカメラ投影可視化
  - Semantic segmentation の確認
  - マスク生成結果の確認
"""

import streamlit as st
import numpy as np
from pathlib import Path
from nuscenes.nuscenes import NuScenes
from PIL import Image

st.set_page_config(layout="wide", page_title="LiDAR Segmentation Viewer")

# --- サイドバー: データ読み込み ---
st.sidebar.title("Settings")

dataroot = st.sidebar.text_input("NuScenes dataroot", "data/raw")

@st.cache_resource
def load_nuscenes(dataroot: str):
    return NuScenes(version="v1.0-mini", dataroot=dataroot, verbose=False)

try:
    nusc = load_nuscenes(dataroot)
except Exception as e:
    st.error(f"NuScenes読み込みエラー: {e}")
    st.stop()

# --- シーン選択 ---
scene_names = [s["name"] for s in nusc.scene]
selected_scene_name = st.sidebar.selectbox("Scene", scene_names)
scene = nusc.scene[[s["name"] for s in nusc.scene].index(selected_scene_name)]

# --- フレーム選択 ---
sample_token = scene["first_sample_token"]
frame_tokens = []
while sample_token:
    frame_tokens.append(sample_token)
    sample = nusc.get("sample", sample_token)
    sample_token = sample["next"] if sample["next"] else None

frame_idx = st.sidebar.slider("Frame", 0, len(frame_tokens) - 1, 0)
sample = nusc.get("sample", frame_tokens[frame_idx])

# --- データ取得 ---
cam_token = sample["data"]["CAM_FRONT"]
cam_data = nusc.get("sample_data", cam_token)

# 画像読み込み
img_path = Path(nusc.dataroot) / cam_data["filename"]
img = Image.open(img_path)

# LiDAR読み込み（lidarsegパック未インストール時の対応）
lidar_token = sample["data"]["LIDAR_TOP"]
try:
    lidarseg = nusc.get("lidarseg", lidar_token)
    has_lidarseg = True
except:
    has_lidarseg = False
    st.warning("⚠ nuScenes-lidarseg データパックが見つかりません。Experiment 02でインストールしてください。")

# --- レイアウト ---
st.title("LiDAR Segmentation Viewer")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Camera Image")
    st.image(img, use_container_width=True)

with col2:
    st.subheader("LiDAR Projection")
    if has_lidarseg:
        st.info("LiDAR投影の実装（Experiment 02で追加予定）")
    else:
        st.warning("lidarsegデータパックをインストール後、LiDAR投影が表示されます")

# --- 統計情報 ---
st.subheader("Statistics")
st.write(f"Scene: {selected_scene_name}")
st.write(f"Frame: {frame_idx + 1} / {len(frame_tokens)}")
st.write(f"Camera token: {cam_token[:8]}...")
st.write(f"LiDAR token: {lidar_token[:8]}...")

if has_lidarseg:
    st.success("✓ nuScenes-lidarseg データパック検出")
else:
    st.error("✗ nuScenes-lidarseg データパック未検出")
