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
    """Importance score based on frame type, slack, and key-frame protection."""

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

        key_frame_bonus = 0.15 if int(frame.get("key_frame", 0)) == 1 else 0.0
        raw_score = 0.45 * type_score + 0.40 * urgency_score + key_frame_bonus
        return min(1.0, max(0.0, raw_score))
