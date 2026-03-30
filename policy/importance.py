"""Stage A: 프레임 중요도 스코어링.

v1 heuristic은 frame type(I/P/B), deadline slack, GOP 내 위치를 반영한다.
향후 ML 기반 scorer로 교체 가능하도록 인터페이스를 분리한다.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class NetworkState:
    """정책 결정 시점의 네트워크 상태 스냅샷."""
    rtt_ms: float
    bandwidth_mbps: float
    loss_rate: float = 0.0
    buffer_level_ms: float = 0.0


class ImportanceScorer(abc.ABC):
    """프레임 중요도 scorer 공통 인터페이스."""

    @abc.abstractmethod
    def score(self, frame: Dict[str, object], network: NetworkState) -> float:
        ...


_TYPE_BASE_SCORES = {"I": 1.0, "P": 0.6, "B": 0.2, "FILE": 0.5}


class HeuristicImportanceScorer(ImportanceScorer):
    """IPB type + deadline slack + GOP 위치 기반 heuristic scorer.

    score 범위: 0.0 (가장 낮음) ~ 1.0 (가장 높음)
    """

    def __init__(self, playback_buffer_ms: float = 50.0) -> None:
        self.playback_buffer_ms = max(playback_buffer_ms, 1.0)

    def score(self, frame: Dict[str, object], network: NetworkState) -> float:
        frame_type = str(frame.get("frame_type", "B")).upper()
        type_score = _TYPE_BASE_SCORES.get(frame_type, 0.3)

        deadline_ms = float(frame.get("display_deadline_ms", float("inf")))
        now_ms = float(frame.get("event_time_ms", 0.0))
        slack_ms = deadline_ms - now_ms
        if slack_ms <= 0:
            urgency = 1.0
        else:
            urgency = max(0.0, 1.0 - slack_ms / self.playback_buffer_ms)

        is_keyframe = int(frame.get("key_frame", 0))
        keyframe_bonus = 0.15 if is_keyframe else 0.0

        raw = 0.45 * type_score + 0.40 * urgency + keyframe_bonus
        return min(1.0, max(0.0, raw))
