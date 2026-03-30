"""정책 회귀 스모크 검증 스크립트.

핵심 정책 경로의 결과 컬럼/범위/기본 불변조건을 빠르게 점검한다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.simulator import run_simulation
from core.transport import TransportConfig
from core.workload import VideoTraceConfig, generate_workload
from policy.legacy import PolicyConfig


logger = logging.getLogger(__name__)


COMMON_REQUIRED_COLUMNS = [
    "policy",
    "frame_action_mode",
    "importance_scorer_type",
    "mean_importance_score",
    "dropped_frame_count",
    "dropped_frame_ratio",
    "action_reliable_single_count",
    "action_reliable_multi_count",
    "action_unreliable_count",
    "action_duplicate_count",
    "action_drop_count",
    "late_frame_ratio",
    "keyframe_late_ratio",
    "decodable_gop_ratio",
]


def _assert_keys(result: Dict[str, object], keys: List[str]) -> None:
    missing = [k for k in keys if k not in result]
    if missing:
        raise AssertionError(f"Missing result keys: {missing}")


def _as_float(result: Dict[str, object], key: str) -> float:
    value = result[key]
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"{key} must be numeric, got {type(value).__name__}")


def _as_int(result: Dict[str, object], key: str) -> int:
    value = result[key]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raise TypeError(f"{key} must be int-like, got {type(value).__name__}")


def _as_str(result: Dict[str, object], key: str) -> str:
    value = result[key]
    if isinstance(value, str):
        return value
    raise TypeError(f"{key} must be str, got {type(value).__name__}")


def _assert_ratio(name: str, value: float) -> None:
    if not (0.0 <= float(value) <= 1.0):
        raise AssertionError(f"{name} must be in [0,1], got {value}")


def _validate_common_metrics(result: Dict[str, object]) -> None:
    _assert_keys(result, COMMON_REQUIRED_COLUMNS)
    _assert_ratio("mean_importance_score", _as_float(result, "mean_importance_score"))
    _assert_ratio("dropped_frame_ratio", _as_float(result, "dropped_frame_ratio"))
    _assert_ratio("late_frame_ratio", _as_float(result, "late_frame_ratio"))
    _assert_ratio("keyframe_late_ratio", _as_float(result, "keyframe_late_ratio"))
    _assert_ratio("decodable_gop_ratio", _as_float(result, "decodable_gop_ratio"))


def _validate_action_sum(result: Dict[str, object], frame_count: int) -> None:
    action_sum = (
        _as_int(result, "action_reliable_single_count")
        + _as_int(result, "action_reliable_multi_count")
        + _as_int(result, "action_unreliable_count")
        + _as_int(result, "action_duplicate_count")
        + _as_int(result, "action_drop_count")
    )
    if action_sum != frame_count:
        raise AssertionError(
            f"Action count sum mismatch: expected {frame_count}, got {action_sum}"
        )


def run_smoke(
    trace_path: Path,
    model_path: Optional[Path],
    playback_buffer_ms: float,
    rtt_ms: float,
    bandwidth_mbps: float,
    delayed_ack_ms: float,
    available_paths: int,
) -> None:
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
    frame_count = int(len(generate_workload(workload_cfg)))

    logger.info("Running fixed_hybrid regression check")
    fixed_result = run_simulation(
        workload_cfg,
        transport_cfg,
        PolicyConfig(name="fixed_hybrid", batch_bytes=8192, flush_interval_ms=8.0),
    )
    _validate_common_metrics(fixed_result)
    if _as_int(fixed_result, "frame_action_mode") != 0:
        raise AssertionError("fixed_hybrid must keep frame_action_mode=0")

    logger.info("Running frame_action_adaptive regression check")
    adaptive_result = run_simulation(
        workload_cfg,
        transport_cfg,
        PolicyConfig(name="frame_action_adaptive", available_paths=available_paths),
    )
    _validate_common_metrics(adaptive_result)
    _validate_action_sum(adaptive_result, frame_count)
    if _as_str(adaptive_result, "importance_scorer_type") != "heuristic":
        raise AssertionError("frame_action_adaptive must use heuristic scorer")

    logger.info("Running frame_action_ml_adaptive regression check")
    ml_policy = PolicyConfig(
        name="frame_action_ml_adaptive",
        available_paths=available_paths,
        model_path=str(model_path) if model_path is not None else None,
    )
    ml_result = run_simulation(workload_cfg, transport_cfg, ml_policy)
    _validate_common_metrics(ml_result)
    _validate_action_sum(ml_result, frame_count)

    if model_path is not None and model_path.exists():
        expected_types = {"ml"}
    else:
        expected_types = {"ml_fallback_heuristic", "heuristic_fallback"}
    if _as_str(ml_result, "importance_scorer_type") not in expected_types:
        raise AssertionError(
            "Unexpected ML scorer type: "
            f"{ml_result['importance_scorer_type']} (expected one of {sorted(expected_types)})"
        )

    logger.info(
        "Smoke check passed: fixed_mode=%s, adaptive_mode=%s, ml_mode=%s",
        fixed_result["importance_scorer_type"],
        adaptive_result["importance_scorer_type"],
        ml_result["importance_scorer_type"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run simulator policy smoke regression checks")
    parser.add_argument("--trace", default="data/video-traces/bbb_720p_trace.csv")
    parser.add_argument("--model-path", default="")
    parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    parser.add_argument("--rtt-ms", type=float, default=30.0)
    parser.add_argument("--bandwidth-mbps", type=float, default=8.0)
    parser.add_argument("--delayed-ack-ms", type=float, default=20.0)
    parser.add_argument("--available-paths", type=int, default=2)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    model_path = Path(args.model_path) if args.model_path else None

    run_smoke(
        trace_path=trace_path,
        model_path=model_path,
        playback_buffer_ms=args.playback_buffer_ms,
        rtt_ms=args.rtt_ms,
        bandwidth_mbps=args.bandwidth_mbps,
        delayed_ack_ms=args.delayed_ack_ms,
        available_paths=max(1, int(args.available_paths)),
    )


if __name__ == "__main__":
    main()
