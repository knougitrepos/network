from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.mininet_actual_experiment import (
    ExperimentConfig,
    aggregate_experiment_summaries,
    build_experiment_summary,
)


class MininetSummaryMetricsTest(unittest.TestCase):
    def test_summary_tracks_byte_and_action_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ExperimentConfig(
                video_name="sample",
                video_path=Path(temp_dir) / "sample.mp4",
                policy_name="deadline_feasible_frame_action",
                python_executable="python3",
                bandwidth_mbps=1.0,
                round_trip_time_ms=50.0,
                loss_rate=1.0,
                playback_buffer_ms=50.0,
                repeat_index=1,
                output_directory=Path(temp_dir),
            )
            client_events = [
                {
                    "experiment_start_time_ns": 1_000_000_000,
                    "video_name": "sample",
                    "policy_name": "deadline_feasible_frame_action",
                    "frame_index": 0,
                    "frame_type": "I",
                    "key_frame": 1,
                    "gop_id": 0,
                    "payload_bytes": 100,
                    "frame_pts_ms": 0.0,
                    "display_deadline_ms": 50.0,
                    "selected_action_name": "RELIABLE_SINGLE",
                    "transport_protocol": "tcp",
                    "send_start_time_ns": 1_000_000_000,
                    "dropped_by_policy": False,
                },
                {
                    "experiment_start_time_ns": 1_000_000_000,
                    "video_name": "sample",
                    "policy_name": "deadline_feasible_frame_action",
                    "frame_index": 1,
                    "frame_type": "P",
                    "key_frame": 0,
                    "gop_id": 0,
                    "payload_bytes": 200,
                    "frame_pts_ms": 30.0,
                    "display_deadline_ms": 50.0,
                    "selected_action_name": "UNRELIABLE",
                    "transport_protocol": "udp",
                    "send_start_time_ns": 1_030_000_000,
                    "dropped_by_policy": False,
                },
                {
                    "experiment_start_time_ns": 1_000_000_000,
                    "video_name": "sample",
                    "policy_name": "deadline_feasible_frame_action",
                    "frame_index": 2,
                    "frame_type": "I",
                    "key_frame": 1,
                    "gop_id": 1,
                    "payload_bytes": 300,
                    "frame_pts_ms": 60.0,
                    "display_deadline_ms": 80.0,
                    "selected_action_name": "DROP",
                    "transport_protocol": "drop",
                    "send_start_time_ns": 1_060_000_000,
                    "dropped_by_policy": True,
                },
            ]
            server_events = [
                {
                    "frame_index": 0,
                    "transport_protocol": "tcp",
                    "receive_time_ns": 1_030_000_000,
                    "payload_bytes": 100,
                },
                {
                    "frame_index": 1,
                    "transport_protocol": "udp",
                    "receive_time_ns": 1_070_000_000,
                    "payload_bytes": 200,
                },
            ]

            summary = build_experiment_summary(config, client_events, server_events)

        self.assertEqual(300.0, summary.sent_bytes)
        self.assertEqual(100.0, summary.on_time_bytes)
        self.assertEqual(200.0, summary.late_bytes)
        self.assertEqual(300.0, summary.dropped_bytes)
        self.assertAlmostEqual(200.0 / 300.0, summary.wasted_late_bytes_ratio)
        self.assertAlmostEqual(100.0 / 300.0, summary.on_time_goodput_ratio)
        self.assertEqual(1, summary.dropped_keyframe_count)
        self.assertEqual(1, summary.reliable_single_count)
        self.assertEqual(1, summary.unreliable_count)
        self.assertEqual(1, summary.drop_count)
        self.assertEqual(0, summary.reliable_single_late_count)
        self.assertEqual(1, summary.unreliable_late_count)

    def test_aggregate_recomputes_ratio_metrics_from_sums(self) -> None:
        summaries = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for repeat_index, payload in enumerate((100, 300), start=1):
                config = ExperimentConfig(
                    video_name="sample",
                    video_path=Path(temp_dir) / "sample.mp4",
                    policy_name="deadline_feasible_frame_action",
                    python_executable="python3",
                    bandwidth_mbps=1.0,
                    round_trip_time_ms=50.0,
                    loss_rate=1.0,
                    playback_buffer_ms=50.0,
                    repeat_index=repeat_index,
                    output_directory=Path(temp_dir),
                )
                summaries.append(
                    build_experiment_summary(
                        config,
                        [
                            {
                                "experiment_start_time_ns": 1_000_000_000,
                                "video_name": "sample",
                                "policy_name": "deadline_feasible_frame_action",
                                "frame_index": repeat_index,
                                "frame_type": "P",
                                "key_frame": 0,
                                "gop_id": 0,
                                "payload_bytes": payload,
                                "frame_pts_ms": 0.0,
                                "display_deadline_ms": 50.0,
                                "selected_action_name": "UNRELIABLE",
                                "transport_protocol": "udp",
                                "send_start_time_ns": 1_000_000_000,
                                "dropped_by_policy": False,
                            }
                        ],
                        [
                            {
                                "frame_index": repeat_index,
                                "transport_protocol": "udp",
                                "receive_time_ns": 1_070_000_000,
                                "payload_bytes": payload,
                            }
                        ],
                    )
                )

        aggregate = aggregate_experiment_summaries(summaries)

        self.assertEqual(400.0, aggregate.sent_bytes)
        self.assertEqual(400.0, aggregate.late_bytes)
        self.assertEqual(1.0, aggregate.wasted_late_bytes_ratio)


if __name__ == "__main__":
    unittest.main()
