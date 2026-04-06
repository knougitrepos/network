"""기존 batch/flush 기반 정책 정의 (하위 호환)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.constants import FIXED_BATCH_GRID, FIXED_FLUSH_GRID_MS, snap
from core.workload import StaticFileConfig, VideoTraceConfig, WorkloadConfig


@dataclass(frozen=True)
class PolicyConfig:
    name: str
    batch_bytes: Optional[int] = None
    flush_interval_ms: Optional[float] = None
    available_paths: int = 1
    model_path: Optional[str] = None
    path_profile: Optional[str] = None


def _resolve_static_heuristic(
    workload_cfg: StaticFileConfig,
    transport_cfg: "TransportConfig",
) -> Tuple[int, float]:
    from core.transport import TransportConfig as _TC  # noqa: F811
    bdp = (transport_cfg.bandwidth_mbps * 1_000_000.0 / 8.0) * (transport_cfg.rtt_ms / 1000.0)
    batch = max(4 * transport_cfg.mss_bytes, 0.5 * bdp)
    flush_ms = min(0.5 * transport_cfg.rtt_ms, transport_cfg.delayed_ack_ms)
    return int(max(1, snap(batch, FIXED_BATCH_GRID))), float(max(0.0, snap(flush_ms, FIXED_FLUSH_GRID_MS)))


def _resolve_video_queue_policy(
    queue_rows: List[Dict[str, object]],
    workload_cfg: VideoTraceConfig,
    transport_cfg: "TransportConfig",
    frame_interval_ms: float,
    now_ms: float,
) -> Tuple[int, float, bool]:
    if not queue_rows:
        return 1, 0.0, False

    min_slack_ms = min(float(row["display_deadline_ms"]) - now_ms for row in queue_rows)
    has_key_frame = any(int(row["key_frame"]) == 1 for row in queue_rows)
    frame_types = {str(row["frame_type"]).upper() for row in queue_rows}

    immediate_flush = has_key_frame or min_slack_ms <= max(frame_interval_ms, 1.0)
    if has_key_frame or min_slack_ms <= max(frame_interval_ms, 1.0):
        batch = 2 * transport_cfg.mss_bytes
        flush_ms = 4.0
    elif "P" in frame_types:
        batch = 4 * transport_cfg.mss_bytes
        flush_ms = 8.0
    else:
        batch = 8 * transport_cfg.mss_bytes
        flush_ms = 16.0

    if transport_cfg.rtt_ms > workload_cfg.playback_buffer_ms / 2.0:
        batch *= 0.5
        flush_ms *= 0.5

    return (
        int(max(1, snap(batch, FIXED_BATCH_GRID))),
        float(max(0.0, snap(flush_ms, FIXED_FLUSH_GRID_MS))),
        immediate_flush,
    )


def resolve_policy(
    workload_cfg: WorkloadConfig,
    transport_cfg: "TransportConfig",
    policy_cfg: PolicyConfig,
) -> Tuple[int, float]:
    if policy_cfg.name == "immediate":
        return 1, 0.0
    if policy_cfg.name == "fixed_size":
        return int(policy_cfg.batch_bytes or 8192), math.inf
    if policy_cfg.name == "fixed_time":
        return math.inf, float(10.0 if policy_cfg.flush_interval_ms is None else policy_cfg.flush_interval_ms)
    if policy_cfg.name in {"fixed_hybrid", "ml_regression_adaptive"}:
        batch = 8192 if policy_cfg.batch_bytes is None else int(policy_cfg.batch_bytes)
        flush_ms = 10.0 if policy_cfg.flush_interval_ms is None else float(policy_cfg.flush_interval_ms)
        return batch, flush_ms
    if policy_cfg.name in {"frame_action_adaptive", "frame_action_ml_adaptive"}:
        batch = 4 * transport_cfg.mss_bytes if policy_cfg.batch_bytes is None else int(policy_cfg.batch_bytes)
        flush_ms = 8.0 if policy_cfg.flush_interval_ms is None else float(policy_cfg.flush_interval_ms)
        return batch, flush_ms
    if policy_cfg.name == "heuristic_frame_aware":
        if isinstance(workload_cfg, StaticFileConfig):
            return _resolve_static_heuristic(workload_cfg, transport_cfg)
        return 4 * transport_cfg.mss_bytes, 8.0
    raise ValueError(f"Unsupported policy: {policy_cfg.name}")
