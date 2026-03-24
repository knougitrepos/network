from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union
import math

import numpy as np
import pandas as pd


DEFAULT_SEED = 20260309
FIXED_BATCH_GRID = [512, 1460, 2920, 8192, 16384, 32768, 65536]
FIXED_FLUSH_GRID_MS = [0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 33.0, 50.0]
STATIC_OBJECTIVE_WEIGHTS = {
    "throughput_mbps": 0.40,
    "goodput_bytes": 0.25,
    "latency_p95_ms": 0.20,
    "flush_count": 0.15,
}
VIDEO_OBJECTIVE_WEIGHTS = {
    "decodable_gop_ratio": 0.30,
    "late_frame_ratio": 0.25,
    "keyframe_late_ratio": 0.20,
    "useful_goodput_bytes": 0.15,
    "latency_p95_ms": 0.10,
}
OBJECTIVE_WEIGHTS = {
    "static_file": STATIC_OBJECTIVE_WEIGHTS,
    "video_stream_trace": VIDEO_OBJECTIVE_WEIGHTS,
}
REVERSE_SCORE_METRICS = {
    "latency_p95_ms",
    "flush_count",
    "late_frame_ratio",
    "keyframe_late_ratio",
}


@dataclass(frozen=True)
class TransportConfig:
    rtt_ms: float
    bandwidth_mbps: float
    delayed_ack_ms: float
    mss_bytes: int = 1460
    nagle_penalty_factor: float = 0.25
    propagation_factor: float = 0.5


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


@dataclass(frozen=True)
class PolicyConfig:
    name: str
    batch_bytes: Optional[int] = None
    flush_interval_ms: Optional[float] = None


WorkloadConfig = Union[StaticFileConfig, VideoTraceConfig]


def resolve_repo_root(start: Optional[Path] = None) -> Path:
    base = (start or Path.cwd()).resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".git").exists():
            return candidate
    return base


def snap(value: float, grid: Sequence[float]) -> float:
    if not grid:
        raise ValueError("grid must not be empty")
    return min(grid, key=lambda candidate: abs(candidate - value))


def _safe_mean(values: Iterable[float]) -> float:
    series = list(values)
    return float(sum(series) / len(series)) if series else 0.0


def _safe_quantile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.quantile(values, q))


def workload_kind(cfg: WorkloadConfig) -> str:
    return "static_file" if isinstance(cfg, StaticFileConfig) else "video_stream_trace"


def serialize_workload_config(cfg: WorkloadConfig) -> Dict[str, object]:
    data = asdict(cfg)
    if isinstance(cfg, VideoTraceConfig):
        data["trace_csv_path"] = str(Path(cfg.trace_csv_path).resolve())
        data["trace_name"] = Path(cfg.trace_csv_path).stem
    return {"workload_kind": workload_kind(cfg), **data}


def serialize_transport_config(cfg: TransportConfig) -> Dict[str, float]:
    return {key: float(value) if isinstance(value, (int, float)) else value for key, value in asdict(cfg).items()}


def scenario_id(workload_cfg: WorkloadConfig, transport_cfg: TransportConfig) -> str:
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


def generate_static_file_events(cfg: StaticFileConfig) -> pd.DataFrame:
    count = int(math.ceil(cfg.file_size_bytes / max(cfg.chunk_size_bytes, 1)))
    if count <= 0:
        return pd.DataFrame(
            columns=[
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
        )

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
        return pd.DataFrame(
            columns=[
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
        )

    required = {
        "frame_idx",
        "pts_ms",
        "duration_ms",
        "frame_type",
        "payload_bytes",
        "key_frame",
        "gop_id",
        "importance_rank",
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


def _frame_interval_ms(events: pd.DataFrame) -> float:
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
    transport_cfg: TransportConfig,
    events: Optional[pd.DataFrame] = None,
) -> Dict[str, object]:
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
    frame_interval_ms = _frame_interval_ms(events)
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
        "p95_frame_bytes": _safe_quantile(payload.to_numpy(dtype=float), 0.95) if not payload.empty else 0.0,
        "frame_interval_ms": frame_interval_ms,
        "keyframe_interval_frames": keyframe_interval_frames,
        "i_ratio": float((frame_types == "I").sum() / total),
        "p_ratio": float((frame_types == "P").sum() / total),
        "b_ratio": float((frame_types == "B").sum() / total),
        "estimated_rtt": float(transport_cfg.rtt_ms),
        "bandwidth_mbps": float(transport_cfg.bandwidth_mbps),
        "delayed_ack_ms": float(transport_cfg.delayed_ack_ms),
        "playback_buffer_ms": float(workload_cfg.playback_buffer_ms),
    }


def _resolve_static_heuristic(
    workload_cfg: StaticFileConfig,
    transport_cfg: TransportConfig,
) -> Tuple[int, float]:
    bdp = (transport_cfg.bandwidth_mbps * 1_000_000.0 / 8.0) * (transport_cfg.rtt_ms / 1000.0)
    batch = max(4 * transport_cfg.mss_bytes, 0.5 * bdp)
    flush_ms = min(0.5 * transport_cfg.rtt_ms, transport_cfg.delayed_ack_ms)
    return int(max(1, snap(batch, FIXED_BATCH_GRID))), float(max(0.0, snap(flush_ms, FIXED_FLUSH_GRID_MS)))


def _resolve_video_queue_policy(
    queue_rows: List[Dict[str, object]],
    workload_cfg: VideoTraceConfig,
    transport_cfg: TransportConfig,
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
    transport_cfg: TransportConfig,
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
    if policy_cfg.name == "heuristic_frame_aware":
        if isinstance(workload_cfg, StaticFileConfig):
            return _resolve_static_heuristic(workload_cfg, transport_cfg)
        return 4 * transport_cfg.mss_bytes, 8.0
    raise ValueError(f"Unsupported policy: {policy_cfg.name}")


def _policy_uses_timer(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {"fixed_time", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive"}


def _policy_uses_size(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {"fixed_size", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive"}


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
    frame_interval_ms = _frame_interval_ms(events)

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
        nonlocal queue_rows
        nonlocal queue_bytes
        nonlocal batch_start_ms
        nonlocal flush_count
        nonlocal total_payload
        nonlocal useful_goodput_bytes
        nonlocal last_link_release_ms
        nonlocal last_completion_ms

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
            frame_records.append(
                {
                    "gop_id": int(row["gop_id"]),
                    "key_frame": int(row["key_frame"]),
                    "payload_bytes": int(row["payload_bytes"]),
                    "on_time": on_time,
                }
            )

        batch_sizes.append(float(payload_bytes))
        total_payload += payload_bytes
        flush_count += 1
        last_link_release_ms = completion_ms
        last_completion_ms = completion_ms
        queue_rows = []
        queue_bytes = 0
        batch_start_ms = None

    for row in events.itertuples(index=False):
        now_ms = float(row.event_time_ms)

        if queue_rows and batch_start_ms is not None:
            if policy_cfg.name == "heuristic_frame_aware" and isinstance(workload_cfg, VideoTraceConfig):
                current_batch_target, current_flush_limit, _ = _resolve_video_queue_policy(
                    queue_rows,
                    workload_cfg,
                    transport_cfg,
                    frame_interval_ms,
                    now_ms,
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
                queue_rows,
                workload_cfg,
                transport_cfg,
                frame_interval_ms,
                now_ms,
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
                queue_rows,
                workload_cfg,
                transport_cfg,
                frame_interval_ms,
                final_event_time_ms,
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
        "latency_p95_ms": _safe_quantile(latency_array, 0.95),
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


def build_metric_ranges(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    metric_weights = OBJECTIVE_WEIGHTS[str(df["workload_kind"].iloc[0])]
    return {metric: (float(df[metric].min()), float(df[metric].max())) for metric in metric_weights}


def normalize_metric(value: float, lower: float, upper: float, reverse: bool = False) -> float:
    if upper > lower:
        normalized = (value - lower) / (upper - lower)
    else:
        normalized = 0.5
    normalized = float(np.clip(normalized, 0.0, 1.0))
    return 1.0 - normalized if reverse else normalized


def score_policy_rows(df: pd.DataFrame, metric_ranges: Dict[str, Tuple[float, float]]) -> pd.DataFrame:
    scored = df.copy()
    workload = str(scored["workload_kind"].iloc[0])
    objective = np.zeros(len(scored), dtype=float)
    for metric, weight in OBJECTIVE_WEIGHTS[workload].items():
        lower, upper = metric_ranges[metric]
        reverse = metric in REVERSE_SCORE_METRICS
        normalized = scored[metric].apply(lambda value: normalize_metric(float(value), lower, upper, reverse=reverse))
        scored[f"{metric}_score"] = normalized
        objective += weight * normalized.to_numpy(dtype=float)
    scored["objective_score"] = objective
    return scored


def score_policy_result(policy_result: Dict[str, object], metric_ranges: Dict[str, Tuple[float, float]]) -> float:
    policy_result_df = pd.DataFrame([policy_result])
    scored = score_policy_rows(policy_result_df, metric_ranges)
    return float(scored.iloc[0]["objective_score"])


def select_best_fixed_config(
    fixed_grid_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Tuple[float, float]]]]:
    scored_groups: List[pd.DataFrame] = []
    metric_ranges_by_scenario: Dict[str, Dict[str, Tuple[float, float]]] = {}
    for scenario_key, group in fixed_grid_df.groupby("scenario_id", sort=False):
        local = group.reset_index(drop=True)
        metric_ranges = build_metric_ranges(local)
        scored_local = score_policy_rows(local, metric_ranges)
        scored_groups.append(scored_local)
        metric_ranges_by_scenario[str(scenario_key)] = metric_ranges
    scored = pd.concat(scored_groups, ignore_index=True) if scored_groups else pd.DataFrame()
    if scored.empty:
        return scored, scored, metric_ranges_by_scenario
    best_row_index = scored.groupby("scenario_id")["objective_score"].idxmax()
    best_fixed_config_df = scored.loc[best_row_index].copy().reset_index(drop=True)
    return scored, best_fixed_config_df, metric_ranges_by_scenario
