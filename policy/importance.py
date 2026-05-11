"""Stage A importance scoring for actual-video experiments."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class NetworkState:
    rtt_ms: float
    bandwidth_mbps: float
    loss_rate: float = 0.0
    buffer_level_ms: float = 0.0
    queue_bytes: int = 0
    estimated_batch_gain: float = 0.0


class ImportanceScorer(abc.ABC):
    @abc.abstractmethod
    def score(self, frame: Dict[str, object], network: NetworkState) -> float:
        raise NotImplementedError


_TYPE_BASE_SCORE = {
    "I": 1.0,
    "P": 0.6,
    "B": 0.2,
    "FILE": 0.5,
}


class HeuristicImportanceScorer(ImportanceScorer):
    """Importance score based on frame value, urgency, GOP role, and payload cost."""

    def __init__(self, playback_buffer_ms: float = 50.0) -> None:
        self.playback_buffer_ms = max(float(playback_buffer_ms), 1.0)

    def score(self, frame: Dict[str, object], network: NetworkState) -> float:
        del network
        frame_type = str(frame.get("frame_type", "B")).upper()
        type_score = _TYPE_BASE_SCORE.get(frame_type, 0.3)

        display_deadline_ms = float(frame.get("display_deadline_ms", float("inf")))
        event_time_ms = float(frame.get("event_time_ms", 0.0))
        deadline_slack_ms = display_deadline_ms - event_time_ms
        if deadline_slack_ms <= 0:
            urgency_score = 1.0
        else:
            urgency_score = max(0.0, 1.0 - deadline_slack_ms / self.playback_buffer_ms)

        key_frame_bonus = 0.14 if int(frame.get("key_frame", 0)) == 1 else 0.0
        gop_dependency_bonus = float(frame.get("gop_dependency_bonus", 0.0))

        payload_bytes = max(float(frame.get("payload_bytes", 0.0)), 0.0)
        max_payload_bytes = max(float(frame.get("max_payload_bytes", payload_bytes or 1.0)), 1.0)
        payload_cost = min(1.0, payload_bytes / max_payload_bytes)

        raw_score = (
            0.48 * type_score
            + 0.38 * urgency_score
            + key_frame_bonus
            + min(max(gop_dependency_bonus, 0.0), 0.10)
            - 0.10 * payload_cost
        )
        return min(1.0, max(0.0, raw_score))
