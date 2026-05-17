from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from scripts.mininet_actual_experiment import (
    DEFAULT_BANDWIDTH_VALUES_MBPS,
    DEFAULT_LOSS_RATE_VALUES,
    DEFAULT_RTT_VALUES_MS,
    EXPERIMENT_POLICY_NAMES,
    build_condition_directory_name,
    build_output_directory,
)


class ExperimentMatrixTest(unittest.TestCase):
    def test_default_matrix_matches_paper_experiment_scope(self) -> None:
        self.assertEqual((1.0, 2.0, 3.0, 5.0), DEFAULT_BANDWIDTH_VALUES_MBPS)
        self.assertEqual((10.0, 50.0, 100.0), DEFAULT_RTT_VALUES_MS)
        self.assertEqual((0.0, 1.0, 3.0), DEFAULT_LOSS_RATE_VALUES)
        self.assertIn("deadline_feasible_frame_action", EXPERIMENT_POLICY_NAMES)
        self.assertIn("gop_aware_deadline_frame_action", EXPERIMENT_POLICY_NAMES)

    def test_non_default_rtt_or_loss_gets_distinct_output_directory(self) -> None:
        self.assertEqual("5mbps", build_condition_directory_name(5.0, 10.0, 0.0))
        self.assertEqual("5mbps_rtt50ms_loss1pct", build_condition_directory_name(5.0, 50.0, 1.0))

        args = argparse.Namespace(
            output_dir="output/mininet_actual_experiment",
            video_name="archive_popeye_512kb",
            policy_name="deadline_feasible_frame_action",
            bandwidth_mbps=5.0,
            round_trip_time_ms=50.0,
            loss_rate=1.0,
        )

        output_directory = build_output_directory(args)

        self.assertEqual(
            Path("output/mininet_actual_experiment")
            .resolve()
            .joinpath("archive_popeye_512kb", "deadline_feasible_frame_action", "5mbps_rtt50ms_loss1pct"),
            output_directory,
        )


if __name__ == "__main__":
    unittest.main()
