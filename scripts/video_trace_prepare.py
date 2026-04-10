from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.video_assets import load_video_frame_assets, write_trace_csv


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a trace CSV cache from an actual video file."
    )
    parser.add_argument("--video-path", required=True, help="Path to the source MP4 file.")
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Output CSV path. Defaults to dataset/traces/<video_name>_trace.csv.",
    )
    parser.add_argument(
        "--playback-buffer-ms",
        type=float,
        default=50.0,
        help="Playback buffer used to derive display deadlines.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()


def resolve_default_output_path(video_path: Path) -> Path:
    return Path("dataset/traces") / f"{video_path.stem}_trace.csv"


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    video_path = Path(args.video_path).resolve()
    output_csv_path = (
        Path(args.output_csv).resolve()
        if args.output_csv
        else resolve_default_output_path(video_path).resolve()
    )

    frame_assets = load_video_frame_assets(
        video_path=video_path,
        playback_buffer_ms=float(args.playback_buffer_ms),
    )
    write_trace_csv(
        video_path=video_path,
        output_path=output_csv_path,
        playback_buffer_ms=float(args.playback_buffer_ms),
    )

    summary = {
        "video_path": str(video_path),
        "output_csv_path": str(output_csv_path),
        "frame_count": len(frame_assets),
        "gop_count": int(max((frame_asset.gop_id for frame_asset in frame_assets), default=-1) + 1),
        "total_payload_bytes": int(sum(frame_asset.payload_bytes for frame_asset in frame_assets)),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
