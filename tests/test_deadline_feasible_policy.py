from __future__ import annotations

import unittest

from policy.action import FrameAction, select_deadline_feasible_action
from policy.importance import HeuristicImportanceScorer, NetworkState


class HeuristicImportanceScorerTest(unittest.TestCase):
    def test_key_frame_scores_above_same_deadline_p_frame(self) -> None:
        scorer = HeuristicImportanceScorer(playback_buffer_ms=50.0)
        network = NetworkState(rtt_ms=10.0, bandwidth_mbps=2.0)

        p_frame_score = scorer.score(
            {
                "frame_type": "P",
                "key_frame": 0,
                "payload_bytes": 1200,
                "max_payload_bytes": 10000,
                "display_deadline_ms": 80.0,
                "event_time_ms": 40.0,
            },
            network,
        )
        key_frame_score = scorer.score(
            {
                "frame_type": "I",
                "key_frame": 1,
                "payload_bytes": 1200,
                "max_payload_bytes": 10000,
                "display_deadline_ms": 80.0,
                "event_time_ms": 40.0,
            },
            network,
        )

        self.assertGreater(key_frame_score, p_frame_score)

    def test_payload_cost_lowers_score_for_same_type_and_deadline(self) -> None:
        scorer = HeuristicImportanceScorer(playback_buffer_ms=50.0)
        network = NetworkState(rtt_ms=10.0, bandwidth_mbps=2.0)
        base_frame = {
            "frame_type": "P",
            "key_frame": 0,
            "max_payload_bytes": 10000,
            "display_deadline_ms": 80.0,
            "event_time_ms": 40.0,
        }

        small_payload_score = scorer.score({**base_frame, "payload_bytes": 500}, network)
        large_payload_score = scorer.score({**base_frame, "payload_bytes": 10000}, network)

        self.assertGreater(small_payload_score, large_payload_score)

    def test_score_is_clamped_to_unit_interval(self) -> None:
        scorer = HeuristicImportanceScorer(playback_buffer_ms=1.0)
        network = NetworkState(rtt_ms=10.0, bandwidth_mbps=2.0)

        score = scorer.score(
            {
                "frame_type": "I",
                "key_frame": 1,
                "payload_bytes": 1,
                "max_payload_bytes": 1,
                "display_deadline_ms": 0.0,
                "event_time_ms": 100.0,
            },
            network,
        )

        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class DeadlineFeasibleActionTest(unittest.TestCase):
    def test_low_importance_infeasible_frame_is_dropped_before_deadline(self) -> None:
        action = select_deadline_feasible_action(
            importance_score=0.2,
            payload_bytes=100_000,
            current_time_ms=0.0,
            display_deadline_ms=100.0,
            network=NetworkState(rtt_ms=50.0, bandwidth_mbps=1.0),
        )

        self.assertEqual(FrameAction.DROP, action)

    def test_high_importance_infeasible_frame_stays_reliable(self) -> None:
        action = select_deadline_feasible_action(
            importance_score=0.9,
            payload_bytes=100_000,
            current_time_ms=0.0,
            display_deadline_ms=100.0,
            network=NetworkState(rtt_ms=50.0, bandwidth_mbps=1.0),
        )

        self.assertEqual(FrameAction.RELIABLE_SINGLE, action)

    def test_medium_importance_tight_frame_uses_unreliable_path(self) -> None:
        action = select_deadline_feasible_action(
            importance_score=0.5,
            payload_bytes=1_000,
            current_time_ms=0.0,
            display_deadline_ms=40.0,
            network=NetworkState(rtt_ms=50.0, bandwidth_mbps=1.0),
        )

        self.assertEqual(FrameAction.UNRELIABLE, action)

    def test_protected_frame_stays_reliable_when_infeasible_and_medium_importance(self) -> None:
        action = select_deadline_feasible_action(
            importance_score=0.5,
            payload_bytes=100_000,
            current_time_ms=0.0,
            display_deadline_ms=100.0,
            network=NetworkState(rtt_ms=50.0, bandwidth_mbps=1.0),
            protected_frame=True,
        )

        self.assertEqual(FrameAction.RELIABLE_SINGLE, action)

    def test_protected_frame_is_not_dropped_when_low_importance(self) -> None:
        action = select_deadline_feasible_action(
            importance_score=0.2,
            payload_bytes=100_000,
            current_time_ms=0.0,
            display_deadline_ms=100.0,
            network=NetworkState(rtt_ms=50.0, bandwidth_mbps=1.0),
            protected_frame=True,
        )

        self.assertEqual(FrameAction.RELIABLE_SINGLE, action)


if __name__ == "__main__":
    unittest.main()
