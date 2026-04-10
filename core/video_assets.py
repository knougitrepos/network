"""Utilities for extracting actual frame payloads from real video files."""

from __future__ import annotations

import csv
import json
import logging
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import av  # type: ignore
except ImportError:  # pragma: no cover - dependency is validated at runtime
    av = None


logger = logging.getLogger(__name__)

FRAME_IMPORTANCE_RANK = {"I": 0, "P": 1, "B": 2}


@dataclass(frozen=True)
class VideoFrameAsset:
    video_name: str
    video_path: Path
    frame_index: int
    pts_ms: float
    duration_ms: float
    frame_type: str
    payload_bytes: int
    key_frame: int
    gop_id: int
    importance_rank: int
    display_deadline_ms: float
    packet_position: int
    payload: bytes


def _float_or_none(value: Any) -> Optional[float]:
    if value in (None, "", "N/A"):
        return None
    return float(value)


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, "", "N/A"):
        return None
    return int(value)


def require_pyav() -> None:
    if av is None:
        raise RuntimeError(
            "PyAV is required for actual-video experiments. "
            "Install it in the execution environment before running this command."
        )


def verify_video_with_pyav(video_path: Path) -> None:
    require_pyav()
    with av.open(str(video_path)) as container:  # type: ignore[union-attr]
        if not container.streams.video:
            raise RuntimeError(f"Video stream not found: {video_path}")


def _run_ffprobe(video_path: Path) -> list[dict[str, Any]]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_frames",
        "-show_entries",
        (
            "frame=best_effort_timestamp_time,pkt_pts_time,pkt_dts_time,"
            "pkt_duration_time,pict_type,pkt_size,key_frame,pkt_pos"
        ),
        "-of",
        "json",
        str(video_path),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    frames = payload.get("frames", [])
    if not isinstance(frames, list) or not frames:
        raise RuntimeError(f"ffprobe returned no video frames: {video_path}")
    return [frame for frame in frames if isinstance(frame, dict)]


def _resolve_pts_ms(frame_payload: dict[str, Any]) -> float:
    for key in ("best_effort_timestamp_time", "pkt_pts_time", "pkt_dts_time"):
        value = _float_or_none(frame_payload.get(key))
        if value is not None:
            return value * 1000.0
    raise RuntimeError("Frame timestamp is missing in ffprobe output.")


def _resolve_duration_series(frame_payloads: list[dict[str, Any]], pts_series_ms: list[float]) -> list[float]:
    duration_series_ms: list[float] = []
    inferred_differences_ms = [
        later_pts_ms - current_pts_ms
        for current_pts_ms, later_pts_ms in zip(pts_series_ms, pts_series_ms[1:])
        if later_pts_ms >= current_pts_ms
    ]
    fallback_duration_ms = statistics.median(inferred_differences_ms) if inferred_differences_ms else 33.0

    for frame_index, frame_payload in enumerate(frame_payloads):
        explicit_duration_ms = _float_or_none(frame_payload.get("pkt_duration_time"))
        if explicit_duration_ms is not None and explicit_duration_ms > 0:
            duration_series_ms.append(explicit_duration_ms * 1000.0)
            continue

        if frame_index + 1 < len(pts_series_ms):
            inferred_duration_ms = pts_series_ms[frame_index + 1] - pts_series_ms[frame_index]
            duration_series_ms.append(max(inferred_duration_ms, 0.0))
            continue

        duration_series_ms.append(fallback_duration_ms)

    return duration_series_ms


def _read_packet_payload(video_path: Path, packet_position: int, payload_bytes: int) -> bytes:
    with video_path.open("rb") as video_file:
        video_file.seek(packet_position)
        payload = video_file.read(payload_bytes)
    if len(payload) != payload_bytes:
        raise RuntimeError(
            f"Failed to read exact packet payload bytes from {video_path}: "
            f"expected={payload_bytes}, actual={len(payload)}"
        )
    return payload


def load_video_frame_assets(video_path: Path, playback_buffer_ms: float = 50.0) -> list[VideoFrameAsset]:
    resolved_video_path = Path(video_path).resolve()
    if not resolved_video_path.exists():
        raise FileNotFoundError(f"Video file not found: {resolved_video_path}")

    verify_video_with_pyav(resolved_video_path)
    frame_payloads = _run_ffprobe(resolved_video_path)
    frame_payloads = sorted(
        frame_payloads,
        key=lambda frame_payload: (
            _resolve_pts_ms(frame_payload),
            _int_or_none(frame_payload.get("pkt_pos")) or 0,
        ),
    )
    pts_series_ms = [_resolve_pts_ms(frame_payload) for frame_payload in frame_payloads]
    duration_series_ms = _resolve_duration_series(frame_payloads, pts_series_ms)

    video_name = resolved_video_path.stem
    frame_assets: list[VideoFrameAsset] = []
    gop_id = -1

    for frame_index, frame_payload in enumerate(frame_payloads):
        frame_type = str(frame_payload.get("pict_type", "")).upper()
        if frame_type not in FRAME_IMPORTANCE_RANK:
            raise RuntimeError(f"Unsupported frame type '{frame_type}' in {resolved_video_path}")

        key_frame = int(frame_payload.get("key_frame") or 0)
        if frame_type == "I":
            gop_id += 1
        elif gop_id < 0:
            gop_id = 0

        payload_bytes = _int_or_none(frame_payload.get("pkt_size"))
        packet_position = _int_or_none(frame_payload.get("pkt_pos"))
        if payload_bytes is None or payload_bytes <= 0:
            raise RuntimeError(f"Invalid packet size in ffprobe output for {resolved_video_path}")
        if packet_position is None or packet_position < 0:
            raise RuntimeError(f"Invalid packet position in ffprobe output for {resolved_video_path}")

        pts_ms = pts_series_ms[frame_index]
        duration_ms = duration_series_ms[frame_index]
        payload = _read_packet_payload(resolved_video_path, packet_position, payload_bytes)
        display_deadline_ms = pts_ms + duration_ms + float(playback_buffer_ms)

        frame_assets.append(
            VideoFrameAsset(
                video_name=video_name,
                video_path=resolved_video_path,
                frame_index=frame_index,
                pts_ms=round(pts_ms, 6),
                duration_ms=round(duration_ms, 6),
                frame_type=frame_type,
                payload_bytes=payload_bytes,
                key_frame=key_frame,
                gop_id=gop_id,
                importance_rank=FRAME_IMPORTANCE_RANK[frame_type],
                display_deadline_ms=round(display_deadline_ms, 6),
                packet_position=packet_position,
                payload=payload,
            )
        )

    logger.info("Loaded %s frame assets from %s", len(frame_assets), resolved_video_path)
    return frame_assets


def write_trace_csv(video_path: Path, output_path: Path, playback_buffer_ms: float = 50.0) -> Path:
    frame_assets = load_video_frame_assets(video_path=video_path, playback_buffer_ms=playback_buffer_ms)
    resolved_output_path = Path(output_path).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

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
        "packet_position",
        "source_video_path",
    ]
    with resolved_output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_asset in frame_assets:
            writer.writerow(
                {
                    "frame_idx": frame_asset.frame_index,
                    "pts_ms": frame_asset.pts_ms,
                    "duration_ms": frame_asset.duration_ms,
                    "frame_type": frame_asset.frame_type,
                    "payload_bytes": frame_asset.payload_bytes,
                    "key_frame": frame_asset.key_frame,
                    "gop_id": frame_asset.gop_id,
                    "importance_rank": frame_asset.importance_rank,
                    "display_deadline_ms": frame_asset.display_deadline_ms,
                    "packet_position": frame_asset.packet_position,
                    "source_video_path": str(frame_asset.video_path),
                }
            )

    logger.info("Wrote trace cache to %s", resolved_output_path)
    return resolved_output_path
