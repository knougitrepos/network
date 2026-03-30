"""Workload 설정 및 이벤트 생성."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from core.constants import safe_quantile


@dataclass(frozen=True)
class StaticFileConfig:
    file_size_bytes: int
    chunk_size_bytes: int
    generation_gap_ms: float = 0.05


@dataclass(frozen=True)
class VideoTraceConfig:
    trace_csv_path: Path
    playback_buffer_ms: float = 50.0
    loop_count: int = 1


WorkloadConfig = Union[StaticFileConfig, VideoTraceConfig]

EVENT_COLUMNS = [
    "event_idx",
    "event_time_ms",
    "payload_bytes",
    "duration_ms",
    "frame_type",
    "key_frame",
    "gop_id",
    "importance_rank",
    "display_deadline_ms",
]


def workload_kind(cfg: WorkloadConfig) -> str:
    return "static_file" if isinstance(cfg, StaticFileConfig) else "video_stream_trace"


def serialize_workload_config(cfg: WorkloadConfig) -> Dict[str, object]:
    data = asdict(cfg)
    if isinstance(cfg, VideoTraceConfig):
        data["trace_csv_path"] = str(Path(cfg.trace_csv_path).resolve())
        data["trace_name"] = Path(cfg.trace_csv_path).stem
    return {"workload_kind": workload_kind(cfg), **data}


def generate_static_file_events(cfg: StaticFileConfig) -> pd.DataFrame:
    count = int(math.ceil(cfg.file_size_bytes / max(cfg.chunk_size_bytes, 1)))
    if count <= 0:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    payloads = np.full(count, cfg.chunk_size_bytes, dtype=int)
    overflow = count * cfg.chunk_size_bytes - cfg.file_size_bytes
    payloads[-1] -= max(0, overflow)
    event_time_ms = np.arange(count, dtype=float) * cfg.generation_gap_ms
    return pd.DataFrame(
        {
            "event_idx": np.arange(count, dtype=int),
            "event_time_ms": event_time_ms,
            "payload_bytes": payloads,
            "duration_ms": np.zeros(count, dtype=float),
            "frame_type": np.full(count, "FILE", dtype=object),
            "key_frame": np.zeros(count, dtype=int),
            "gop_id": np.full(count, -1, dtype=int),
            "importance_rank": np.full(count, 3, dtype=int),
            "display_deadline_ms": np.full(count, np.inf, dtype=float),
        }
    )


def load_video_trace_events(cfg: VideoTraceConfig) -> pd.DataFrame:
    trace_path = Path(cfg.trace_csv_path)
    trace_df = pd.read_csv(trace_path)
    if trace_df.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    required = {
        "frame_idx", "pts_ms", "duration_ms", "frame_type",
        "payload_bytes", "key_frame", "gop_id", "importance_rank",
    }
    missing = sorted(required.difference(trace_df.columns))
    if missing:
        raise ValueError(f"Missing required trace columns: {missing}")

    trace_df = trace_df.sort_values(["pts_ms", "frame_idx"]).reset_index(drop=True)
    base_pts = float(trace_df["pts_ms"].iloc[0])
    trace_df["pts_ms"] = trace_df["pts_ms"].astype(float) - base_pts
    trace_df["duration_ms"] = trace_df["duration_ms"].astype(float)
    trace_df["payload_bytes"] = trace_df["payload_bytes"].astype(int)
    trace_df["key_frame"] = trace_df["key_frame"].astype(int)
    trace_df["gop_id"] = trace_df["gop_id"].astype(int)
    trace_df["importance_rank"] = trace_df["importance_rank"].astype(int)
    trace_df["frame_type"] = trace_df["frame_type"].astype(str).str.upper()

    if trace_df["duration_ms"].le(0).all():
        diffs = trace_df["pts_ms"].diff().dropna()
        inferred = float(diffs.median()) if not diffs.empty else 33.0
        trace_df["duration_ms"] = inferred
    else:
        positive = trace_df["duration_ms"][trace_df["duration_ms"] > 0]
        fallback = float(positive.median()) if not positive.empty else 33.0
        trace_df.loc[trace_df["duration_ms"] <= 0, "duration_ms"] = fallback

    if cfg.loop_count > 1:
        clip_duration = float((trace_df["pts_ms"] + trace_df["duration_ms"]).max())
        replicas: List[pd.DataFrame] = []
        for loop_idx in range(cfg.loop_count):
            replica = trace_df.copy()
            offset = clip_duration * loop_idx
            replica["frame_idx"] = replica["frame_idx"] + loop_idx * len(trace_df)
            replica["pts_ms"] = replica["pts_ms"] + offset
            replica["gop_id"] = replica["gop_id"] + loop_idx * (int(trace_df["gop_id"].max()) + 1)
            replicas.append(replica)
        trace_df = pd.concat(replicas, ignore_index=True)

    trace_df["display_deadline_ms"] = trace_df["pts_ms"] + trace_df["duration_ms"] + float(cfg.playback_buffer_ms)
    return pd.DataFrame(
        {
            "event_idx": trace_df["frame_idx"].astype(int),
            "event_time_ms": trace_df["pts_ms"].astype(float),
            "payload_bytes": trace_df["payload_bytes"].astype(int),
            "duration_ms": trace_df["duration_ms"].astype(float),
            "frame_type": trace_df["frame_type"].astype(str),
            "key_frame": trace_df["key_frame"].astype(int),
            "gop_id": trace_df["gop_id"].astype(int),
            "importance_rank": trace_df["importance_rank"].astype(int),
            "display_deadline_ms": trace_df["display_deadline_ms"].astype(float),
        }
    )


def generate_workload(cfg: WorkloadConfig) -> pd.DataFrame:
    if isinstance(cfg, StaticFileConfig):
        return generate_static_file_events(cfg)
    return load_video_trace_events(cfg)


def frame_interval_ms(events: pd.DataFrame) -> float:
    if events.empty:
        return 0.0
    if "duration_ms" in events.columns:
        positive = events["duration_ms"][events["duration_ms"] > 0]
        if not positive.empty:
            return float(positive.median())
    diffs = events["event_time_ms"].diff().dropna()
    return float(diffs.median()) if not diffs.empty else 0.0


def build_policy_features(
    workload_cfg: WorkloadConfig,
    transport_cfg: "TransportConfig",
    events: Optional[pd.DataFrame] = None,
) -> Dict[str, object]:
    from core.transport import TransportConfig as _TC  # noqa: F811
    events = generate_workload(workload_cfg) if events is None else events

    if isinstance(workload_cfg, StaticFileConfig):
        payload = events["payload_bytes"].astype(float) if not events.empty else pd.Series(dtype=float)
        inter_arrival = events["event_time_ms"].diff().dropna() if len(events) > 1 else pd.Series(dtype=float)
        message_size_mean = float(payload.mean()) if not payload.empty else 0.0
        inter_arrival_time = float(inter_arrival.mean()) if not inter_arrival.empty else float(workload_cfg.generation_gap_ms)
        queue_size = float(message_size_mean * max(1.0, transport_cfg.rtt_ms / max(inter_arrival_time, 1e-6)))
        return {
            "workload_kind": "static_file",
            "chunk_size_bytes": int(workload_cfg.chunk_size_bytes),
            "message_size_mean": message_size_mean,
            "inter_arrival_time": inter_arrival_time,
            "queue_size": queue_size,
            "estimated_rtt": float(transport_cfg.rtt_ms),
            "bandwidth_mbps": float(transport_cfg.bandwidth_mbps),
            "delayed_ack_ms": float(transport_cfg.delayed_ack_ms),
        }

    payload = events["payload_bytes"].astype(float) if not events.empty else pd.Series(dtype=float)
    fi_ms = frame_interval_ms(events)
    key_indices = events.index[events["key_frame"] == 1].to_list()
    if len(key_indices) >= 2:
        keyframe_interval_frames = float(np.median(np.diff(key_indices)))
    else:
        keyframe_interval_frames = float(len(events)) if len(events) else 0.0
    frame_types = events["frame_type"].astype(str).str.upper() if not events.empty else pd.Series(dtype=str)
    total = float(len(events)) if len(events) else 1.0
    return {
        "workload_kind": "video_stream_trace",
        "trace_name": Path(workload_cfg.trace_csv_path).stem,
        "mean_frame_bytes": float(payload.mean()) if not payload.empty else 0.0,
        "p95_frame_bytes": safe_quantile(payload.to_numpy(dtype=float), 0.95) if not payload.empty else 0.0,
        "frame_interval_ms": fi_ms,
        "keyframe_interval_frames": keyframe_interval_frames,
        "i_ratio": float((frame_types == "I").sum() / total),
        "p_ratio": float((frame_types == "P").sum() / total),
        "b_ratio": float((frame_types == "B").sum() / total),
        "estimated_rtt": float(transport_cfg.rtt_ms),
        "bandwidth_mbps": float(transport_cfg.bandwidth_mbps),
        "delayed_ack_ms": float(transport_cfg.delayed_ack_ms),
        "playback_buffer_ms": float(workload_cfg.playback_buffer_ms),
    }


def resolve_repo_root(start: Optional[Path] = None) -> Path:
    base = (start or Path.cwd()).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return base


def scenario_id(workload_cfg: WorkloadConfig, transport_cfg: "TransportConfig") -> str:
    if isinstance(workload_cfg, StaticFileConfig):
        return (
            f"static_{workload_cfg.file_size_bytes}_{workload_cfg.chunk_size_bytes}_"
            f"{transport_cfg.rtt_ms}_{transport_cfg.bandwidth_mbps}_{transport_cfg.delayed_ack_ms}"
        )
    trace_name = Path(workload_cfg.trace_csv_path).stem
    return (
        f"video_{trace_name}_{workload_cfg.playback_buffer_ms}_{workload_cfg.loop_count}_"
        f"{transport_cfg.rtt_ms}_{transport_cfg.bandwidth_mbps}_{transport_cfg.delayed_ack_ms}"
    )
