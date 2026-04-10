"""Legacy queue heuristics used by the actual heuristic TCP policy."""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.constants import FIXED_BATCH_GRID, FIXED_FLUSH_GRID_MS, snap


def resolve_video_queue_policy(
    queue_rows: List[Dict[str, object]],
    playback_buffer_ms: float,
    transport_cfg: "TransportConfig",
    frame_interval_ms: float,
    now_ms: float,
) -> Tuple[int, float, bool]:
    if not queue_rows:
        return 1, 0.0, False

    minimum_deadline_slack_ms = min(float(row["display_deadline_ms"]) - now_ms for row in queue_rows)
    contains_key_frame = any(int(row["key_frame"]) == 1 for row in queue_rows)
    frame_types = {str(row["frame_type"]).upper() for row in queue_rows}

    immediate_flush = contains_key_frame or minimum_deadline_slack_ms <= max(frame_interval_ms, 1.0)
    if contains_key_frame or minimum_deadline_slack_ms <= max(frame_interval_ms, 1.0):
        batch_bytes = 2 * transport_cfg.mss_bytes
        flush_interval_ms = 4.0
    elif "P" in frame_types:
        batch_bytes = 4 * transport_cfg.mss_bytes
        flush_interval_ms = 8.0
    else:
        batch_bytes = 8 * transport_cfg.mss_bytes
        flush_interval_ms = 16.0

    if transport_cfg.rtt_ms > float(playback_buffer_ms) / 2.0:
        batch_bytes *= 0.5
        flush_interval_ms *= 0.5

    return (
        int(max(1, snap(batch_bytes, FIXED_BATCH_GRID))),
        float(max(0.0, snap(flush_interval_ms, FIXED_FLUSH_GRID_MS))),
        immediate_flush,
    )
