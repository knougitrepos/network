"""Stage B: 프레임 중요도/deadline 기반 전송 행동 매핑.

FrameAction은 QUIC Stream/DATAGRAM + multipath 환경에서의
프레임 단위 전송 결정을 표현한다.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional, Sequence

from policy.importance import NetworkState


class FrameAction(Enum):
    RELIABLE_SINGLE = auto()   # QUIC Stream, 단일 경로
    RELIABLE_MULTI = auto()    # QUIC Stream, 멀티패스
    UNRELIABLE = auto()        # QUIC DATAGRAM
    DUPLICATE = auto()         # 고중요 프레임 중복 전송
    DROP = auto()              # deadline 초과 예상 → 전송 포기


# 임계값 기본값 (향후 RL/ML로 대체 가능)
_HIGH_IMPORTANCE = 0.75
_LOW_IMPORTANCE = 0.30
_CRITICAL_SLACK_MS = 10.0


def select_action(
    importance_score: float,
    deadline_slack_ms: float,
    network: NetworkState,
    available_paths: int = 1,
) -> FrameAction:
    """importance score와 deadline slack으로 전송 행동을 결정한다.

    규칙 우선순위:
    1. deadline 이미 초과 & 낮은 중요도 → DROP
    2. 매우 높은 중요도 & 여유 있음 & 멀티패스 가능 → DUPLICATE
    3. 높은 중요도 → RELIABLE (MULTI if available)
    4. slack 여유 충분 & 낮은 중요도 → UNRELIABLE
    5. 기본 → RELIABLE_SINGLE
    """
    if deadline_slack_ms <= 0 and importance_score < _LOW_IMPORTANCE:
        return FrameAction.DROP

    if importance_score >= _HIGH_IMPORTANCE:
        if deadline_slack_ms > _CRITICAL_SLACK_MS and available_paths > 1:
            return FrameAction.DUPLICATE
        if available_paths > 1:
            return FrameAction.RELIABLE_MULTI
        return FrameAction.RELIABLE_SINGLE

    if deadline_slack_ms > network.rtt_ms * 2 and importance_score < _LOW_IMPORTANCE:
        return FrameAction.UNRELIABLE

    if available_paths > 1 and importance_score >= _LOW_IMPORTANCE:
        return FrameAction.RELIABLE_MULTI

    return FrameAction.RELIABLE_SINGLE
