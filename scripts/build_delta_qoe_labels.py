"""ΔQoE 기반 프레임 중요도 라벨 생성 스크립트 (초안).

현재 구현은 baseline frame record에서 단일 프레임 drop 영향을 계산하는 방식이다.
향후 실제 재생 파이프라인/실측 VMAF 기반 라벨로 교체 가능하도록 CSV 포맷을 고정한다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.transport import TCPTransportModel, TransportConfig
from core.workload import VideoTraceConfig, generate_workload
from eval.metrics import compute_all_video_metrics


logger = logging.getLogger(__name__)


def _as_int(value: object, key: str) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raise TypeError(f"{key} must be int-like, got {type(value).__name__}")


def _as_bool(value: object, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    raise TypeError(f"{key} must be bool-like, got {type(value).__name__}")


def _build_baseline_records(
    events: pd.DataFrame,
    transport_cfg: TransportConfig,
) -> List[Dict[str, object]]:
    model = TCPTransportModel(transport_cfg)
    last_completion_ms = 0.0
    records: List[Dict[str, object]] = []

    for row in events.itertuples(index=False):
        event_time_ms = float(row.event_time_ms)
        send_start_ms = max(event_time_ms, last_completion_ms)
        completion_ms = model.estimate_completion(int(row.payload_bytes), send_start_ms)
        last_completion_ms = completion_ms

        deadline_ms = float(row.display_deadline_ms)
        on_time = completion_ms <= deadline_ms

        records.append(
            {
                "event_idx": int(row.event_idx),
                "gop_id": int(row.gop_id),
                "key_frame": int(row.key_frame),
                "payload_bytes": int(row.payload_bytes),
                "on_time": bool(on_time),
                "dropped": False,
                "frame_type": str(row.frame_type),
                "event_time_ms": event_time_ms,
                "display_deadline_ms": deadline_ms,
            }
        )
    return records


def _apply_drop_scenario(
    baseline_records: List[Dict[str, object]],
    target_event_idx: int,
) -> List[Dict[str, object]]:
    scenario = [dict(record) for record in baseline_records]

    target = None
    for record in scenario:
        if _as_int(record["event_idx"], "event_idx") == target_event_idx:
            target = record
            break

    if target is None:
        raise ValueError(f"target_event_idx not found: {target_event_idx}")

    target["on_time"] = False
    target["dropped"] = True

    # 초안 규칙: key frame drop 시 동일 GOP는 디코딩 실패로 간주.
    if _as_int(target["key_frame"], "key_frame") == 1:
        target_gop = _as_int(target["gop_id"], "gop_id")
        for record in scenario:
            if _as_int(record["gop_id"], "gop_id") == target_gop:
                record["on_time"] = False

    return scenario


def _qoe_score(metrics: Dict[str, float], baseline_goodput: float) -> float:
    useful_ratio = float(metrics["useful_goodput_bytes"]) / max(float(baseline_goodput), 1.0)
    useful_ratio = float(np.clip(useful_ratio, 0.0, 1.0))

    score = (
        0.25 * (1.0 - float(metrics["late_frame_ratio"]))
        + 0.20 * (1.0 - float(metrics["keyframe_late_ratio"]))
        + 0.20 * float(metrics["decodable_gop_ratio"])
        + 0.20 * float(metrics["block_completion_ratio"])
        + 0.10 * float(metrics["ssim_proxy"])
        + 0.05 * useful_ratio
    )
    return float(np.clip(score, 0.0, 1.0))


def _compute_delta_labels(
    events: pd.DataFrame,
    baseline_records: List[Dict[str, object]],
) -> pd.DataFrame:
    baseline_metrics = compute_all_video_metrics(baseline_records)
    baseline_qoe = _qoe_score(
        baseline_metrics,
        baseline_goodput=float(baseline_metrics["useful_goodput_bytes"]),
    )

    label_rows: List[Dict[str, object]] = []
    for row in events.itertuples(index=False):
        target_event_idx = int(row.event_idx)
        scenario_records = _apply_drop_scenario(baseline_records, target_event_idx)
        scenario_metrics = compute_all_video_metrics(scenario_records)
        scenario_qoe = _qoe_score(
            scenario_metrics,
            baseline_goodput=float(baseline_metrics["useful_goodput_bytes"]),
        )
        delta_qoe = max(0.0, baseline_qoe - scenario_qoe)

        baseline_on_time = next(
            _as_bool(r["on_time"], "on_time")
            for r in baseline_records
            if _as_int(r["event_idx"], "event_idx") == target_event_idx
        )

        label_rows.append(
            {
                "event_idx": target_event_idx,
                "frame_type": str(row.frame_type),
                "key_frame": int(row.key_frame),
                "gop_id": int(row.gop_id),
                "payload_bytes": int(row.payload_bytes),
                "event_time_ms": float(row.event_time_ms),
                "display_deadline_ms": float(row.display_deadline_ms),
                "baseline_on_time": baseline_on_time,
                "baseline_qoe": baseline_qoe,
                "drop_qoe": scenario_qoe,
                "delta_qoe": float(delta_qoe),
                "label_mode": "delta_qoe_proxy_v1",
            }
        )

    df = pd.DataFrame(label_rows)
    max_delta = float(df["delta_qoe"].max()) if not df.empty else 0.0
    if max_delta > 0.0:
        df["delta_qoe_norm"] = df["delta_qoe"] / max_delta
    else:
        df["delta_qoe_norm"] = 0.0

    return df


def build_labels(
    trace_path: Path,
    output_path: Path,
    playback_buffer_ms: float,
    rtt_ms: float,
    bandwidth_mbps: float,
    delayed_ack_ms: float,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    workload_cfg = VideoTraceConfig(
        trace_csv_path=trace_path,
        playback_buffer_ms=playback_buffer_ms,
        loop_count=1,
    )
    transport_cfg = TransportConfig(
        rtt_ms=rtt_ms,
        bandwidth_mbps=bandwidth_mbps,
        delayed_ack_ms=delayed_ack_ms,
    )

    events = generate_workload(workload_cfg)
    if events.empty:
        raise ValueError(f"Trace is empty: {trace_path}")

    baseline_records = _build_baseline_records(events, transport_cfg)
    labels_df = _compute_delta_labels(events, baseline_records)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels_df.to_csv(output_path, index=False)

    summary_df = (
        labels_df.groupby("frame_type", sort=False)["delta_qoe_norm"]
        .agg(["count", "mean", "median", "max"])
        .reset_index()
    )

    return labels_df, summary_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build proxy ΔQoE labels for Stage A v2")
    parser.add_argument("--trace", default="data/video-traces/bbb_720p_trace.csv")
    parser.add_argument("--output", default="data/video-traces/bbb_720p_delta_qoe_labels.csv")
    parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    parser.add_argument("--rtt-ms", type=float, default=30.0)
    parser.add_argument("--bandwidth-mbps", type=float, default=8.0)
    parser.add_argument("--delayed-ack-ms", type=float, default=20.0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    trace_path = Path(args.trace)
    output_path = Path(args.output)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    logger.info("Building delta labels from trace: %s", trace_path)
    labels_df, summary_df = build_labels(
        trace_path=trace_path,
        output_path=output_path,
        playback_buffer_ms=args.playback_buffer_ms,
        rtt_ms=args.rtt_ms,
        bandwidth_mbps=args.bandwidth_mbps,
        delayed_ack_ms=args.delayed_ack_ms,
    )
    logger.info("Saved labels: %s (rows=%d)", output_path, len(labels_df))
    logger.info("Label summary by frame_type:\n%s", summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
