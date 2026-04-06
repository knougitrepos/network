"""프레임/배치 기반 전송 시뮬레이션 엔진."""

from __future__ import annotations

import logging
import math
from collections import Counter
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
from policy.action import FrameAction, select_action
from policy.importance import HeuristicImportanceScorer, MLImportanceScorer, NetworkState
from policy.legacy import PolicyConfig, resolve_policy


logger = logging.getLogger(__name__)


def _policy_uses_timer(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {
        "fixed_time", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive", "frame_action_adaptive", "frame_action_ml_adaptive",
    }


def _policy_uses_size(policy_cfg: PolicyConfig) -> bool:
    return policy_cfg.name in {
        "fixed_size", "fixed_hybrid", "heuristic_frame_aware", "ml_regression_adaptive", "frame_action_adaptive", "frame_action_ml_adaptive",
    }


def _policy_uses_frame_actions(policy_cfg: PolicyConfig, workload_cfg: WorkloadConfig) -> bool:
    return (
        policy_cfg.name in {"frame_action_adaptive", "frame_action_ml_adaptive"}
        and isinstance(workload_cfg, VideoTraceConfig)
    )


def _build_path_states(
    transport_cfg: TransportConfig,
    available_paths: int,
    path_profile: str,
) -> List[Dict[str, float]]:
    """멀티패스 근사용 경로 상태를 구성한다.

    실제 QUIC 구현이 아니라, 경로 이질성(rtt/bw/loss) 차이가
    completion 계산에 반영되도록 하는 경량 근사 모델이다.
    """
    if available_paths <= 1:
        return [{
            "rtt_ms": float(transport_cfg.rtt_ms),
            "bandwidth_mbps": float(transport_cfg.bandwidth_mbps),
            "loss_rate": 0.0,
        }]

    base_rtt = float(transport_cfg.rtt_ms)
    base_bw = float(transport_cfg.bandwidth_mbps)

    if path_profile == "balanced":
        factors = [(1.0, 1.0, 0.01), (1.1, 0.95, 0.02), (0.95, 1.05, 0.015)]
    else:
        # 기본: heterogeneous (Han et al. MPR-QUIC 대비 효과 관찰용)
        factors = [(0.7, 0.65, 0.01), (1.0, 1.0, 0.02), (1.6, 1.5, 0.05)]

    paths: List[Dict[str, float]] = []
    for i in range(available_paths):
        rtt_mul, bw_mul, loss = factors[i % len(factors)]
        paths.append({
            "rtt_ms": max(1.0, base_rtt * rtt_mul),
            "bandwidth_mbps": max(0.1, base_bw * bw_mul),
            "loss_rate": float(loss),
        })
    return paths


def _estimate_action_completion_ms(
    row_payload_bytes: int,
    action_name: str,
    send_start_ms: float,
    transport_cfg: TransportConfig,
    path_states: Sequence[Dict[str, float]],
) -> float:
    """행동별 completion 근사.

    - RELIABLE_MULTI: 경로별 분할 전송 후 가장 느린 경로 완료시각 사용
    - DUPLICATE: 상위 2경로 중 먼저 도착하는 완료시각 사용
    - UNRELIABLE: ACK penalty 제거 + propagation 축소
    - RELIABLE_SINGLE/기타: 기존 단일경로 근사
    """
    def single_path_completion(payload: int, rtt_ms: float, bw_mbps: float, ack_penalty: bool) -> float:
        tx_time_ms = (payload * 8.0) / (max(bw_mbps, 0.001) * 1_000_000.0) * 1000.0
        ack_ms = (
            min(transport_cfg.delayed_ack_ms, transport_cfg.nagle_penalty_factor * rtt_ms)
            if ack_penalty and payload < transport_cfg.mss_bytes
            else 0.0
        )
        return send_start_ms + tx_time_ms + transport_cfg.propagation_factor * rtt_ms + ack_ms

    primary = path_states[0]
    base_single = single_path_completion(
        row_payload_bytes,
        primary["rtt_ms"],
        primary["bandwidth_mbps"],
        ack_penalty=True,
    )

    if action_name == FrameAction.UNRELIABLE.name:
        tx_time_ms = (row_payload_bytes * 8.0) / (max(primary["bandwidth_mbps"], 0.001) * 1_000_000.0) * 1000.0
        return send_start_ms + tx_time_ms + 0.35 * primary["rtt_ms"]

    if action_name == FrameAction.RELIABLE_MULTI.name and len(path_states) > 1:
        bw_sum = sum(max(p["bandwidth_mbps"], 0.001) for p in path_states)
        completion_candidates: List[float] = []
        for p in path_states:
            share = max(p["bandwidth_mbps"], 0.001) / bw_sum
            path_payload = max(1, int(round(row_payload_bytes * share)))
            completion = single_path_completion(path_payload, p["rtt_ms"], p["bandwidth_mbps"], ack_penalty=True)
            completion += p["rtt_ms"] * p["loss_rate"] * 0.5
            completion_candidates.append(completion)
        return max(completion_candidates) if completion_candidates else base_single

    if action_name == FrameAction.DUPLICATE.name and len(path_states) > 1:
        top2 = sorted(path_states, key=lambda p: (p["rtt_ms"], -p["bandwidth_mbps"]))[:2]
        dup_candidates = [
            single_path_completion(row_payload_bytes, p["rtt_ms"], p["bandwidth_mbps"], ack_penalty=True)
            + p["rtt_ms"] * p["loss_rate"] * 0.2
            for p in top2
        ]
        return min(dup_candidates) if dup_candidates else base_single

    return base_single


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

    frame_action_mode = _policy_uses_frame_actions(policy_cfg, workload_cfg)
    available_paths = max(1, int(getattr(policy_cfg, "available_paths", 1)))
    path_profile = str(getattr(policy_cfg, "path_profile", "heterogeneous") or "heterogeneous").lower()
    path_states = _build_path_states(transport_cfg, available_paths, path_profile)
    scorer = None
    importance_scorer_type = "none"
    importance_thresholds: tuple[float, float] | None = None
    if frame_action_mode and isinstance(workload_cfg, VideoTraceConfig):
        playback_buffer_ms = float(workload_cfg.playback_buffer_ms)
        if policy_cfg.name == "frame_action_ml_adaptive":
            try:
                scorer = MLImportanceScorer(
                    model_path=policy_cfg.model_path,
                    playback_buffer_ms=playback_buffer_ms,
                )
                importance_scorer_type = "ml" if scorer.model is not None else "ml_fallback_heuristic"
                importance_thresholds = scorer.importance_thresholds
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to initialize MLImportanceScorer; fallback to heuristic scorer: %s",
                    exc,
                )
                scorer = HeuristicImportanceScorer(playback_buffer_ms=playback_buffer_ms)
                importance_scorer_type = "heuristic_fallback"
        else:
            scorer = HeuristicImportanceScorer(playback_buffer_ms=playback_buffer_ms)
            importance_scorer_type = "heuristic"

    action_counts: Counter[str] = Counter()
    importance_values: List[float] = []
    dropped_frame_count = 0

    def flush(now_ms: float) -> None:
        nonlocal queue_rows, queue_bytes, batch_start_ms
        nonlocal flush_count, total_payload, useful_goodput_bytes
        nonlocal last_link_release_ms, last_completion_ms

        if not queue_rows:
            return

        payload_bytes = int(sum(int(row.get("tx_payload_bytes", row["payload_bytes"])) for row in queue_rows))
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
            row_action = str(row.get("selected_action", "LEGACY"))
            row_payload = int(row.get("tx_payload_bytes", row["payload_bytes"]))
            row_completion_ms = completion_ms
            if frame_action_mode and row_action != "LEGACY":
                row_completion_ms = _estimate_action_completion_ms(
                    row_payload_bytes=row_payload,
                    action_name=row_action,
                    send_start_ms=flush_start_ms,
                    transport_cfg=transport_cfg,
                    path_states=path_states,
                )

            latency_ms = row_completion_ms - arrival_ms
            latencies.append(latency_ms)
            if math.isfinite(float(row["display_deadline_ms"])):
                deadline_miss_ms = max(0.0, row_completion_ms - float(row["display_deadline_ms"]))
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
                "dropped": False,
                "action": str(row.get("selected_action", "LEGACY")),
                "importance_score": float(row.get("importance_score", np.nan)),
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
        selected_action: Optional[FrameAction] = None
        selected_action_name = "LEGACY"
        importance_score = float("nan")
        deadline_slack_ms = float("inf")
        tx_payload_bytes = int(row.payload_bytes)

        if frame_action_mode and scorer is not None:
            frame_dict = {
                "event_time_ms": now_ms,
                "display_deadline_ms": float(row.display_deadline_ms),
                "frame_type": str(row.frame_type),
                "key_frame": int(row.key_frame),
                "payload_bytes": int(row.payload_bytes),
                "gop_id": int(row.gop_id),
            }
            # cross-layer 배칭 이득 추정 (Borisov 2025 관점)
            # 현재 큐에 MSS 이상의 데이터가 쌓여 있으면 배칭으로 인한
            # throughput 향상이 예상됨 — Nagle 패널티 회피 비율로 근사
            _est_batch_gain = min(
                1.0,
                queue_bytes / max(transport_cfg.mss_bytes, 1),
            ) * transport_cfg.nagle_penalty_factor
            network = NetworkState(
                rtt_ms=float(transport_cfg.rtt_ms),
                bandwidth_mbps=float(transport_cfg.bandwidth_mbps),
                buffer_level_ms=max(0.0, float(row.display_deadline_ms) - max(now_ms, last_link_release_ms)),
                queue_bytes=queue_bytes,
                estimated_batch_gain=_est_batch_gain,
            )
            importance_score = scorer.score(frame_dict, network)
            deadline_slack_ms = float(row.display_deadline_ms) - max(now_ms, last_link_release_ms)
            selected_action = select_action(
                importance_score,
                deadline_slack_ms,
                network,
                available_paths=available_paths,
                queue_bytes=queue_bytes,
                estimated_batch_gain=_est_batch_gain,
                importance_thresholds=importance_thresholds,
            )
            selected_action_name = selected_action.name
            action_counts[selected_action_name] += 1
            importance_values.append(importance_score)

            if selected_action == FrameAction.DROP:
                dropped_frame_count += 1
                deadline_miss_values.append(max(0.0, -deadline_slack_ms))
                frame_records.append({
                    "gop_id": int(row.gop_id),
                    "key_frame": int(row.key_frame),
                    "payload_bytes": int(row.payload_bytes),
                    "on_time": False,
                    "dropped": True,
                    "action": selected_action_name,
                    "importance_score": float(importance_score),
                })
                logger.debug(
                    "Frame dropped by policy: event_idx=%s gop_id=%s slack_ms=%.3f score=%.3f",
                    int(row.event_idx),
                    int(row.gop_id),
                    deadline_slack_ms,
                    importance_score,
                )
                continue

            if selected_action == FrameAction.DUPLICATE and available_paths > 1:
                tx_payload_bytes = int(row.payload_bytes) * 2

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
            "importance_score": float(importance_score),
            "deadline_slack_ms": float(deadline_slack_ms),
            "selected_action": selected_action_name,
            "tx_payload_bytes": int(tx_payload_bytes),
        }
        queue_rows.append(queue_row)
        queue_bytes += int(tx_payload_bytes)
        queue_sizes.append(float(queue_bytes))
        flush_ages.append(0.0 if batch_start_ms is None else now_ms - batch_start_ms)

        if policy_cfg.name == "immediate":
            flush(now_ms)
            continue

        if frame_action_mode and selected_action in {FrameAction.RELIABLE_MULTI, FrameAction.DUPLICATE}:
            flush(now_ms)
            continue

        if frame_action_mode and selected_action == FrameAction.RELIABLE_SINGLE and deadline_slack_ms <= max(fi_ms, 1.0):
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

    frame_count = int(len(events)) if isinstance(workload_cfg, VideoTraceConfig) else 0
    drop_ratio = float(dropped_frame_count / frame_count) if frame_count > 0 else 0.0
    mean_importance_score = float(np.mean(importance_values)) if importance_values else 0.0
    action_reliable_single_count = int(action_counts.get(FrameAction.RELIABLE_SINGLE.name, 0))
    action_reliable_multi_count = int(action_counts.get(FrameAction.RELIABLE_MULTI.name, 0))
    action_unreliable_count = int(action_counts.get(FrameAction.UNRELIABLE.name, 0))
    action_duplicate_count = int(action_counts.get(FrameAction.DUPLICATE.name, 0))

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
        "frame_action_mode": int(frame_action_mode),
        "importance_scorer_type": importance_scorer_type,
        "available_paths": int(available_paths),
        "path_profile": path_profile,
        "mean_importance_score": mean_importance_score,
        "dropped_frame_count": int(dropped_frame_count),
        "dropped_frame_ratio": drop_ratio,
        "action_reliable_single_count": action_reliable_single_count,
        "action_reliable_multi_count": action_reliable_multi_count,
        "action_unreliable_count": action_unreliable_count,
        "action_duplicate_count": action_duplicate_count,
        "action_drop_count": int(dropped_frame_count),
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
