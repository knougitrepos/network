"""QoE 및 전송 품질 지표 계산.

기존 video utility 지표를 유지하면서 rebuffer, ssim_proxy, block_completion을 추가한다.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def late_frame_ratio(frame_df: pd.DataFrame) -> float:
    if frame_df.empty:
        return 0.0
    return float((~frame_df["on_time"]).mean())


def keyframe_late_ratio(frame_df: pd.DataFrame) -> float:
    keyframes = frame_df[frame_df["key_frame"] == 1]
    if keyframes.empty:
        return 0.0
    return float((~keyframes["on_time"]).mean())


def decodable_gop_ratio(frame_df: pd.DataFrame) -> float:
    if frame_df.empty:
        return 0.0
    gop_results: List[bool] = []
    for _, group in frame_df.groupby("gop_id", sort=False):
        key_on_time = (
            bool(group.loc[group["key_frame"] == 1, "on_time"].all())
            if (group["key_frame"] == 1).any()
            else False
        )
        on_time_ratio = float(group["on_time"].mean()) if not group.empty else 0.0
        gop_results.append(key_on_time and on_time_ratio >= 0.8)
    return float(np.mean(gop_results)) if gop_results else 0.0


def useful_goodput_bytes(frame_df: pd.DataFrame) -> float:
    if frame_df.empty:
        return 0.0
    on_time_mask = frame_df["on_time"].astype(bool)
    return float(frame_df.loc[on_time_mask, "payload_bytes"].sum())


def rebuffer_ratio(frame_df: pd.DataFrame) -> float:
    """연속으로 late인 프레임 구간의 비율 (재생 중단 근사).

    연속 late 구간이 2프레임 이상이면 rebuffer event로 간주.
    """
    if frame_df.empty:
        return 0.0
    late_flags = (~frame_df["on_time"]).astype(int).values
    total = len(late_flags)
    if total == 0:
        return 0.0

    rebuffer_frames = 0
    streak = 0
    for flag in late_flags:
        if flag:
            streak += 1
        else:
            if streak >= 2:
                rebuffer_frames += streak
            streak = 0
    if streak >= 2:
        rebuffer_frames += streak
    return float(rebuffer_frames) / total


def ssim_proxy(frame_df: pd.DataFrame) -> float:
    """프레임 도착률 기반 근사 품질 점수 (0~1).

    실제 SSIM/VMAF 계산 없이, on-time 비율과 keyframe 완전성으로 근사한다.
    """
    if frame_df.empty:
        return 0.0
    on_time_rate = float(frame_df["on_time"].mean())
    kf = frame_df[frame_df["key_frame"] == 1]
    kf_on_time_rate = float(kf["on_time"].mean()) if not kf.empty else 0.0
    return 0.6 * on_time_rate + 0.4 * kf_on_time_rate


def block_completion_ratio(frame_df: pd.DataFrame) -> float:
    """GOP 내 모든 프레임이 on-time인 GOP의 비율."""
    if frame_df.empty:
        return 0.0
    results: List[bool] = []
    for _, group in frame_df.groupby("gop_id", sort=False):
        results.append(bool(group["on_time"].all()))
    return float(np.mean(results)) if results else 0.0


def compute_all_video_metrics(frame_records: List[Dict[str, object]]) -> Dict[str, float]:
    """frame_records 리스트로부터 모든 video QoE 지표를 한번에 계산한다."""
    if not frame_records:
        return {
            "late_frame_ratio": 0.0,
            "keyframe_late_ratio": 0.0,
            "decodable_gop_ratio": 0.0,
            "useful_goodput_bytes": 0.0,
            "rebuffer_ratio": 0.0,
            "ssim_proxy": 0.0,
            "block_completion_ratio": 0.0,
        }
    df = pd.DataFrame(frame_records)
    return {
        "late_frame_ratio": late_frame_ratio(df),
        "keyframe_late_ratio": keyframe_late_ratio(df),
        "decodable_gop_ratio": decodable_gop_ratio(df),
        "useful_goodput_bytes": useful_goodput_bytes(df),
        "rebuffer_ratio": rebuffer_ratio(df),
        "ssim_proxy": ssim_proxy(df),
        "block_completion_ratio": block_completion_ratio(df),
    }
