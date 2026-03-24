from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


FRAME_IMPORTANCE = {"I": 0, "P": 1, "B": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a frame-level video trace CSV from an H.264 source using ffprobe.")
    parser.add_argument("--input", required=True, help="Path to the source video file.")
    parser.add_argument("--output", required=True, help="Path to the output CSV file.")
    parser.add_argument(
        "--playback-buffer-ms",
        type=float,
        default=50.0,
        help="Playback buffer used to derive display deadlines.",
    )
    return parser.parse_args()


def _float_or_none(value: Any) -> Optional[float]:
    if value in (None, "", "N/A"):
        return None
    return float(value)


def _probe_frames(video_path: Path) -> List[Dict[str, Any]]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_frames",
        "-show_entries",
        "frame=best_effort_timestamp_time,pkt_pts_time,pkt_dts_time,pkt_duration_time,pict_type,pkt_size,key_frame",
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    return list(payload.get("frames", []))


def _resolve_pts_ms(frame: Dict[str, Any]) -> float:
    for key in ("best_effort_timestamp_time", "pkt_pts_time", "pkt_dts_time"):
        value = _float_or_none(frame.get(key))
        if value is not None:
            return value * 1000.0
    raise ValueError("Frame is missing usable timestamp fields")


def build_trace_rows(frames: List[Dict[str, Any]], playback_buffer_ms: float) -> List[Dict[str, Any]]:
    if not frames:
        return []

    rows: List[Dict[str, Any]] = []
    pts_values_ms = [_resolve_pts_ms(frame) for frame in frames]
    raw_durations_ms = []
    for frame in frames:
        duration = _float_or_none(frame.get("pkt_duration_time"))
        raw_durations_ms.append(duration * 1000.0 if duration is not None else None)

    inferred_diffs_ms = [later - earlier for earlier, later in zip(pts_values_ms, pts_values_ms[1:]) if later >= earlier]
    fallback_duration_ms = statistics.median(inferred_diffs_ms) if inferred_diffs_ms else 33.0

    gop_id = -1
    for index, frame in enumerate(frames):
        frame_type = str(frame.get("pict_type", "P")).upper()
        if frame_type not in FRAME_IMPORTANCE:
            frame_type = "P"
        key_frame = int(frame.get("key_frame", 0))
        if frame_type == "I":
            gop_id += 1
        elif gop_id < 0:
            gop_id = 0

        pts_ms = pts_values_ms[index]
        duration_ms = raw_durations_ms[index]
        if duration_ms is None or duration_ms <= 0:
            if index + 1 < len(pts_values_ms):
                duration_ms = max(pts_values_ms[index + 1] - pts_ms, 0.0)
            else:
                duration_ms = fallback_duration_ms
        payload_bytes = int(frame.get("pkt_size") or 0)
        rows.append(
            {
                "frame_idx": index,
                "pts_ms": round(pts_ms, 6),
                "duration_ms": round(float(duration_ms), 6),
                "frame_type": frame_type,
                "payload_bytes": payload_bytes,
                "key_frame": key_frame,
                "gop_id": gop_id,
                "importance_rank": FRAME_IMPORTANCE[frame_type],
                "display_deadline_ms": round(float(pts_ms + duration_ms + playback_buffer_ms), 6),
            }
        )

    return rows


def write_csv(rows: List[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "frame_idx",
        "pts_ms",
        "duration_ms",
        "frame_type",
        "payload_bytes",
        "key_frame",
        "gop_id",
        "importance_rank",
        "display_deadline_ms",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    video_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    frames = _probe_frames(video_path)
    rows = build_trace_rows(frames, playback_buffer_ms=float(args.playback_buffer_ms))
    write_csv(rows, output_path)

    trace_summary = {
        "input": str(video_path),
        "output": str(output_path),
        "frame_count": len(rows),
        "gop_count": int(max((row["gop_id"] for row in rows), default=-1) + 1),
    }
    print(json.dumps(trace_summary, indent=2))


if __name__ == "__main__":
    main()
