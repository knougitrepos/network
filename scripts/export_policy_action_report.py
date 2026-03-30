"""정책별 action/핵심 지표 요약 보고서를 CSV+PNG로 내보낸다."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.simulator import run_simulation
from core.transport import TransportConfig
from core.workload import VideoTraceConfig
from policy.legacy import PolicyConfig


logger = logging.getLogger(__name__)


ACTION_COLUMNS = [
    "action_reliable_single_count",
    "action_reliable_multi_count",
    "action_unreliable_count",
    "action_duplicate_count",
    "action_drop_count",
]


def _run_policy_suite(
    trace_path: Path,
    playback_buffer_ms: float,
    rtt_ms: float,
    bandwidth_mbps: float,
    delayed_ack_ms: float,
    available_paths: int,
    model_path: str,
) -> pd.DataFrame:
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

    policy_list: List[PolicyConfig] = [
        PolicyConfig(name="fixed_hybrid", batch_bytes=8192, flush_interval_ms=8.0),
        PolicyConfig(name="frame_action_adaptive", available_paths=available_paths),
        PolicyConfig(
            name="frame_action_ml_adaptive",
            available_paths=available_paths,
            model_path=model_path or None,
        ),
    ]

    rows: List[Dict[str, object]] = []
    for policy_cfg in policy_list:
        logger.info("Running policy: %s", policy_cfg.name)
        result = run_simulation(workload_cfg, transport_cfg, policy_cfg)
        rows.append(
            {
                "policy": result["policy"],
                "importance_scorer_type": result["importance_scorer_type"],
                "frame_action_mode": result["frame_action_mode"],
                "mean_importance_score": result["mean_importance_score"],
                "dropped_frame_ratio": result["dropped_frame_ratio"],
                "late_frame_ratio": result["late_frame_ratio"],
                "keyframe_late_ratio": result["keyframe_late_ratio"],
                "decodable_gop_ratio": result["decodable_gop_ratio"],
                "latency_p95_ms": result["latency_p95_ms"],
                "throughput_mbps": result["throughput_mbps"],
                **{k: result[k] for k in ACTION_COLUMNS},
            }
        )
    return pd.DataFrame(rows)


def _save_action_bar_chart(df: pd.DataFrame, out_path: Path) -> None:
    action_df = df[df["frame_action_mode"].astype(int) > 0][["policy", *ACTION_COLUMNS]].copy()
    if action_df.empty:
        action_df = df[["policy", *ACTION_COLUMNS]].copy()

    melted = action_df.melt(id_vars=["policy"], var_name="action", value_name="count")
    pivot_df = melted.pivot(index="policy", columns="action", values="count").fillna(0.0)

    ax = pivot_df.plot(kind="bar", figsize=(10, 5), width=0.85)
    ax.set_title("Policy Action Count Comparison")
    ax.set_xlabel("Policy")
    ax.set_ylabel("Count")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def _save_qoe_scatter(df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    x = df["dropped_frame_ratio"].astype(float)
    y = df["late_frame_ratio"].astype(float)

    ax.scatter(x, y, s=120)
    for idx, row in df.reset_index(drop=True).iterrows():
        x_val = float(row["dropped_frame_ratio"])
        y_val = float(row["late_frame_ratio"])
        # 겹침 완화를 위해 라벨 오프셋을 정책 순서 기반으로 준다.
        x_offset = 0.002 + idx * 0.002
        y_offset = idx * 0.00001
        ax.annotate(str(row["policy"]), (x_val + x_offset, y_val + y_offset))

    ax.set_title("Drop Ratio vs Late Ratio")
    ax.set_xlabel("dropped_frame_ratio")
    ax.set_ylabel("late_frame_ratio")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export policy action summary report")
    parser.add_argument("--trace", default="data/video-traces/bbb_720p_trace.csv")
    parser.add_argument("--model-path", default="")
    parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    parser.add_argument("--rtt-ms", type=float, default=30.0)
    parser.add_argument("--bandwidth-mbps", type=float, default=8.0)
    parser.add_argument("--delayed-ack-ms", type=float, default=20.0)
    parser.add_argument("--available-paths", type=int, default=2)
    parser.add_argument(
        "--output-csv",
        default="output/jupyter-notebook/assets/policy_action_summary.csv",
    )
    parser.add_argument(
        "--output-action-png",
        default="output/jupyter-notebook/assets/policy_action_counts.png",
    )
    parser.add_argument(
        "--output-qoe-png",
        default="output/jupyter-notebook/assets/policy_qoe_scatter.png",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    trace_path = Path(args.trace)
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    summary_df = _run_policy_suite(
        trace_path=trace_path,
        playback_buffer_ms=args.playback_buffer_ms,
        rtt_ms=args.rtt_ms,
        bandwidth_mbps=args.bandwidth_mbps,
        delayed_ack_ms=args.delayed_ack_ms,
        available_paths=max(1, int(args.available_paths)),
        model_path=args.model_path,
    )

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(output_csv, index=False)
    logger.info("Saved summary CSV: %s", output_csv)

    output_action_png = Path(args.output_action_png)
    _save_action_bar_chart(summary_df, output_action_png)
    logger.info("Saved action plot: %s", output_action_png)

    output_qoe_png = Path(args.output_qoe_png)
    _save_qoe_scatter(summary_df, output_qoe_png)
    logger.info("Saved QoE scatter: %s", output_qoe_png)


if __name__ == "__main__":
    main()
