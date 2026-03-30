"""Stage A v2 bootstrap 학습 스크립트.

현재는 ΔQoE 라벨 대신 heuristic 점수를 모사하는 회귀 모델을 학습한다.
향후 라벨 파이프라인이 준비되면 y 구성 로직만 교체하면 된다.
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.workload import VideoTraceConfig, generate_workload
from policy.importance import (
    HeuristicImportanceScorer,
    NetworkState,
    build_importance_features,
)


logger = logging.getLogger(__name__)


def _build_dataset(
    trace_path: Path,
    playback_buffer_ms: float,
    rtt_ms: float,
    bandwidth_mbps: float,
    loss_rate: float,
    label_csv_path: Optional[Path] = None,
    label_column: str = "delta_qoe_norm",
) -> Tuple[np.ndarray, np.ndarray, str]:
    workload_cfg = VideoTraceConfig(
        trace_csv_path=trace_path,
        playback_buffer_ms=playback_buffer_ms,
        loop_count=1,
    )
    events = generate_workload(workload_cfg)
    if events.empty:
        raise ValueError(f"Trace is empty: {trace_path}")

    label_mode = "heuristic_bootstrap"

    if label_csv_path is not None:
        if not label_csv_path.exists():
            raise FileNotFoundError(f"Label CSV not found: {label_csv_path}")
        label_df = pd.read_csv(label_csv_path)
        required_columns = {"event_idx", label_column}
        missing_cols = sorted(required_columns.difference(label_df.columns))
        if missing_cols:
            raise ValueError(f"Label CSV missing required columns: {missing_cols}")

        events = events.merge(
            label_df[["event_idx", label_column]],
            on="event_idx",
            how="left",
            suffixes=("", "_label"),
        )
        missing_rows = int(events[label_column].isna().sum())
        if missing_rows > 0:
            raise ValueError(
                f"Missing labels after merge: {missing_rows} rows do not have '{label_column}'"
            )

        label_mode = f"external:{label_column}"

    scorer = HeuristicImportanceScorer(playback_buffer_ms=playback_buffer_ms)
    xs: List[List[float]] = []
    ys: List[float] = []

    for row in events.itertuples(index=False):
        row_dict = row._asdict()
        frame: Dict[str, object] = {
            "event_time_ms": float(row.event_time_ms),
            "display_deadline_ms": float(row.display_deadline_ms),
            "frame_type": str(row.frame_type),
            "key_frame": int(row.key_frame),
            "payload_bytes": int(row.payload_bytes),
            "gop_id": int(row.gop_id),
        }
        slack_ms = float(row.display_deadline_ms) - float(row.event_time_ms)
        network = NetworkState(
            rtt_ms=rtt_ms,
            bandwidth_mbps=bandwidth_mbps,
            loss_rate=loss_rate,
            buffer_level_ms=max(0.0, slack_ms),
        )
        xs.append(build_importance_features(frame, network, playback_buffer_ms=playback_buffer_ms))
        if label_mode.startswith("external:"):
            ys.append(float(row_dict[label_column]))
        else:
            ys.append(float(scorer.score(frame, network)))

    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), label_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Stage A v2 bootstrap importance model")
    parser.add_argument("--trace", required=True, help="Input frame trace CSV path")
    parser.add_argument("--output", required=True, help="Output pickle model path")
    parser.add_argument("--meta-output", default="", help="Optional metadata JSON output path")
    parser.add_argument("--playback-buffer-ms", type=float, default=50.0)
    parser.add_argument("--rtt-ms", type=float, default=30.0)
    parser.add_argument("--bandwidth-mbps", type=float, default=8.0)
    parser.add_argument("--loss-rate", type=float, default=0.0)
    parser.add_argument("--label-csv", default="", help="Optional external label CSV path")
    parser.add_argument("--label-column", default="delta_qoe_norm", help="Label column name in label CSV")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260330)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=8)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    trace_path = Path(args.trace)
    output_path = Path(args.output)
    meta_output_path = Path(args.meta_output) if args.meta_output else output_path.with_suffix(".meta.json")
    label_csv_path = Path(args.label_csv) if args.label_csv else None

    logger.info("Building dataset from trace: %s", trace_path)
    if label_csv_path is not None:
        logger.info("Using external labels: %s (column=%s)", label_csv_path, args.label_column)

    x, y, label_mode = _build_dataset(
        trace_path=trace_path,
        playback_buffer_ms=args.playback_buffer_ms,
        rtt_ms=args.rtt_ms,
        bandwidth_mbps=args.bandwidth_mbps,
        loss_rate=args.loss_rate,
        label_csv_path=label_csv_path,
        label_column=args.label_column,
    )
    logger.info("Dataset shape: X=%s y=%s (label_mode=%s)", x.shape, y.shape, label_mode)

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.seed,
    )

    model = RandomForestRegressor(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        random_state=args.seed,
        n_jobs=1,
    )
    model.fit(x_train, y_train)

    pred = model.predict(x_test)
    mae = float(mean_absolute_error(y_test, pred))
    r2 = float(r2_score(y_test, pred))
    logger.info("Validation metrics: MAE=%.6f R2=%.6f", mae, r2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        pickle.dump(model, f)
    logger.info("Saved model: %s", output_path)

    metadata = {
        "trace": str(trace_path.resolve()),
        "label_csv": str(label_csv_path.resolve()) if label_csv_path is not None else "",
        "label_column": str(args.label_column),
        "output_model": str(output_path.resolve()),
        "playback_buffer_ms": float(args.playback_buffer_ms),
        "rtt_ms": float(args.rtt_ms),
        "bandwidth_mbps": float(args.bandwidth_mbps),
        "loss_rate": float(args.loss_rate),
        "test_size": float(args.test_size),
        "seed": int(args.seed),
        "n_estimators": int(args.n_estimators),
        "max_depth": int(args.max_depth),
        "dataset_rows": int(x.shape[0]),
        "dataset_features": int(x.shape[1]),
        "val_mae": mae,
        "val_r2": r2,
        "label_mode": label_mode,
    }
    meta_output_path.parent.mkdir(parents=True, exist_ok=True)
    meta_output_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved metadata: %s", meta_output_path)


if __name__ == "__main__":
    main()
