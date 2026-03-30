"""프레임/배치 기반 전송 시뮬레이션 엔진."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from core.constants import (
    FIXED_BATCH_GRID,
    FIXED_FLUSH_GRID_MS,
    safe_quantile,
    snap,
)
from core.transport import TransportConfig, serialize_transport_config
from core.workload import (
    StaticFileConfig,
    VideoTraceConfig,
    WorkloadConfig,
    build_policy_features,
    frame_interval_ms,
    generate_workload,
    scenario_id,
    serialize_workload_config,
)
from policy.legacy import PolicyConfig, resolve_policy


def _policy_uses_timer(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {
        "fixed_time", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive",
    }


def _policy_uses_size(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {
        "fixed_size", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive",
    }


def run_simulation(
    workload_cfg: WorkloadConfig,
    transport_cfg: TransportConfig,
    policy_cfg: PolicyConfig,
) -> Dict[str, object]:
    events = generate_workload(workload_cfg)
    features = build_policy_features(workload_cfg, transport_cfg, events)
    scenario_key = scenario_id(workload_cfg, transport_cfg)
    static_batch, static_flush = resolve_policy(workload_cfg, transport_cfg, policy_cfg)

    queue_rows: List[Dict[str, object]] = []
    queue_bytes = 0
    batch_start_ms: Optional[float] = None
    current_batch_target = static_batch
    current_flush_limit = static_flush
    fi_ms = frame_interval_ms(events)

    latencies: List[float] = []
    batch_sizes: List[float] = []
    queue_sizes: List[float] = []
    flush_ages: List[float] = []
    deadline_miss_values: List[float] = []
    frame_records: List[Dict[str, object]] = []

    flush_count = 0
    total_payload = 0
    useful_goodput_bytes = 0
    last_link_release_ms = 0.0
    first_arrival_ms = float(events["event_time_ms"].iloc[0]) if not events.empty else 0.0
    last_completion_ms = first_arrival_ms

    def flush(now_ms: float) -> None:
        nonlocal queue_rows, queue_bytes, batch_start_ms
        nonlocal flush_count, total_payload, useful_goodput_bytes
        nonlocal last_link_release_ms, last_completion_ms

        if not queue_rows:
            return

        payload_bytes = int(sum(int(row["payload_bytes"]) for row in queue_rows))
        flush_start_ms = max(now_ms, last_link_release_ms)
        tx_time_ms = (payload_bytes * 8.0) / (transport_cfg.bandwidth_mbps * 1_000_000.0) * 1000.0
        ack_penalty_ms = (
            min(transport_cfg.delayed_ack_ms, transport_cfg.nagle_penalty_factor * transport_cfg.rtt_ms)
            if payload_bytes < transport_cfg.mss_bytes
            else 0.0
        )
        completion_ms = (
            flush_start_ms
            + tx_time_ms
            + transport_cfg.propagation_factor * transport_cfg.rtt_ms
            + ack_penalty_ms
        )

        for row in queue_rows:
            arrival_ms = float(row["event_time_ms"])
            latency_ms = completion_ms - arrival_ms
            latencies.append(latency_ms)
            if math.isfinite(float(row["display_deadline_ms"])):
                deadline_miss_ms = max(0.0, completion_ms - float(row["display_deadline_ms"]))
            else:
                deadline_miss_ms = 0.0
            on_time = deadline_miss_ms <= 0.0
            if on_time:
                useful_goodput_bytes += int(row["payload_bytes"])
            deadline_miss_values.append(deadline_miss_ms)
            frame_records.append({
                "gop_id": int(row["gop_id"]),
                "key_frame": int(row["key_frame"]),
                "payload_bytes": int(row["payload_bytes"]),
                "on_time": on_time,
            })

        batch_sizes.append(float(payload_bytes))
        total_payload += payload_bytes
        flush_count += 1
        last_link_release_ms = completion_ms
        last_completion_ms = completion_ms
        queue_rows = []
        queue_bytes = 0
        batch_start_ms = None

    from policy.legacy import _resolve_video_queue_policy

    for row in events.itertuples(index=False):
        now_ms = float(row.event_time_ms)

        if queue_rows and batch_start_ms is not None:
            if policy_cfg.name == "heuristic_frame_aware" and isinstance(workload_cfg, VideoTraceConfig):
                current_batch_target, current_flush_limit, _ = _resolve_video_queue_policy(
                    queue_rows, workload_cfg, transport_cfg, fi_ms, now_ms,
                )
            if _policy_uses_timer(policy_cfg) and math.isfinite(current_flush_limit) and current_flush_limit > 0:
                if now_ms - batch_start_ms >= current_flush_limit:
                    flush(batch_start_ms + current_flush_limit)

        if not queue_rows:
            batch_start_ms = now_ms
            current_batch_target, current_flush_limit = static_batch, static_flush

        queue_row = {
            "event_idx": int(row.event_idx),
            "event_time_ms": now_ms,
            "payload_bytes": int(row.payload_bytes),
            "duration_ms": float(row.duration_ms),
            "frame_type": str(row.frame_type),
            "key_frame": int(row.key_frame),
            "gop_id": int(row.gop_id),
            "importance_rank": int(row.importance_rank),
            "display_deadline_ms": float(row.display_deadline_ms),
        }
        queue_rows.append(queue_row)
        queue_bytes += int(row.payload_bytes)
        queue_sizes.append(float(queue_bytes))
        flush_ages.append(0.0 if batch_start_ms is None else now_ms - batch_start_ms)

        if policy_cfg.name == "immediate":
            flush(now_ms)
            continue

        if policy_cfg.name == "heuristic_frame_aware" and isinstance(workload_cfg, VideoTraceConfig):
            current_batch_target, current_flush_limit, immediate_flush = _resolve_video_queue_policy(
                queue_rows, workload_cfg, transport_cfg, fi_ms, now_ms,
            )
            if immediate_flush:
                flush(now_ms)
                continue

        should_flush_size = _policy_uses_size(policy_cfg) and math.isfinite(current_batch_target) and queue_bytes >= current_batch_target
        should_flush_time = (
            _policy_uses_timer(policy_cfg)
            and math.isfinite(current_flush_limit)
            and current_flush_limit <= 0.0
        )
        if should_flush_size or should_flush_time:
            flush(now_ms)

    if queue_rows:
        final_event_time_ms = float(events["event_time_ms"].iloc[-1]) if not events.empty else 0.0
        if policy_cfg.name == "heuristic_frame_aware" and isinstance(workload_cfg, VideoTraceConfig):
            current_batch_target, current_flush_limit, immediate_flush = _resolve_video_queue_policy(
                queue_rows, workload_cfg, transport_cfg, fi_ms, final_event_time_ms,
            )
            if immediate_flush:
                flush(final_event_time_ms)
            else:
                final_flush_time = (
                    float(batch_start_ms + current_flush_limit)
                    if batch_start_ms is not None and math.isfinite(current_flush_limit) and current_flush_limit > 0
                    else final_event_time_ms
                )
                flush(final_flush_time)
        elif _policy_uses_timer(policy_cfg) and batch_start_ms is not None and math.isfinite(current_flush_limit) and current_flush_limit > 0:
            flush(batch_start_ms + current_flush_limit)
        else:
            flush(final_event_time_ms)

    latency_array = np.asarray(latencies, dtype=float)
    batch_array = np.asarray(batch_sizes, dtype=float)
    queue_array = np.asarray(queue_sizes, dtype=float)
    flush_age_array = np.asarray(flush_ages, dtype=float)
    deadline_miss_array = np.asarray(deadline_miss_values, dtype=float)

    duration_ms = max(last_completion_ms - first_arrival_ms, 1e-6)
    throughput_mbps = float((total_payload * 8.0) / duration_ms / 1000.0) if total_payload else 0.0

    if isinstance(workload_cfg, VideoTraceConfig) and frame_records:
        frame_df = pd.DataFrame(frame_records)
        late_frame_ratio = float((~frame_df["on_time"]).mean())
        keyframes = frame_df[frame_df["key_frame"] == 1]
        keyframe_late_ratio = float((~keyframes["on_time"]).mean()) if not keyframes.empty else 0.0

        gop_results = []
        for _, group in frame_df.groupby("gop_id", sort=False):
            key_on_time = bool(group.loc[group["key_frame"] == 1, "on_time"].all()) if (group["key_frame"] == 1).any() else False
            on_time_ratio = float(group["on_time"].mean()) if not group.empty else 0.0
            gop_results.append(key_on_time and on_time_ratio >= 0.8)
        decodable_gop_ratio = float(np.mean(gop_results)) if gop_results else 0.0
    else:
        late_frame_ratio = 0.0
        keyframe_late_ratio = 0.0
        decodable_gop_ratio = 0.0

    return {
        **serialize_workload_config(workload_cfg),
        **serialize_transport_config(transport_cfg),
        **features,
        "scenario_id": scenario_key,
        "policy": policy_cfg.name,
        "resolved_batch_bytes": float(current_batch_target if math.isfinite(current_batch_target) else 0.0),
        "resolved_flush_interval_ms": float(current_flush_limit if math.isfinite(current_flush_limit) else 0.0),
        "latency_mean_ms": float(latency_array.mean()) if latency_array.size else 0.0,
        "latency_p95_ms": safe_quantile(latency_array, 0.95),
        "throughput_mbps": throughput_mbps,
        "goodput_bytes": float(total_payload),
        "flush_count": int(flush_count),
        "syscall_count": int(flush_count),
        "mean_batch_size_bytes": float(batch_array.mean()) if batch_array.size else 0.0,
        "mean_queue_size_bytes": float(queue_array.mean()) if queue_array.size else 0.0,
        "max_queue_size_bytes": float(queue_array.max()) if queue_array.size else 0.0,
        "mean_elapsed_time_since_last_flush_ms": float(flush_age_array.mean()) if flush_age_array.size else 0.0,
        "deadline_miss_ms_sum": float(deadline_miss_array.sum()) if deadline_miss_array.size else 0.0,
        "late_frame_ratio": late_frame_ratio,
        "keyframe_late_ratio": keyframe_late_ratio,
        "decodable_gop_ratio": decodable_gop_ratio,
        "useful_goodput_bytes": float(useful_goodput_bytes),
        "best_fixed_score_gap": 0.0,
    }


def evaluate_fixed_policy_grid(
    scenario_configs: Sequence[Tuple[WorkloadConfig, TransportConfig]],
    batches: Sequence[int] = FIXED_BATCH_GRID,
    flush_intervals_ms: Sequence[float] = FIXED_FLUSH_GRID_MS,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for workload_cfg, transport_cfg in scenario_configs:
        for batch_bytes in batches:
            for flush_interval_ms in flush_intervals_ms:
                result = run_simulation(
                    workload_cfg,
                    transport_cfg,
                    PolicyConfig("fixed_hybrid", batch_bytes=int(batch_bytes), flush_interval_ms=float(flush_interval_ms)),
                )
                result["batch_bytes"] = int(batch_bytes)
                result["flush_interval_ms"] = float(flush_interval_ms)
                rows.append(result)
    return pd.DataFrame(rows)
