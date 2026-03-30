"""공유 상수 및 유틸리티."""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


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


def snap(value: float, grid: Sequence[float]) -> float:
    if not grid:
        raise ValueError("grid must not be empty")
    return min(grid, key=lambda candidate: abs(candidate - value))


def safe_mean(values: Iterable[float]) -> float:
    series = list(values)
    return float(sum(series) / len(series)) if series else 0.0


def safe_quantile(values: np.ndarray, q: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.quantile(values, q))
