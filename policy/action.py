"""Stage B: 프레임 중요도/deadline 기반 전송 행동 매핑.

FrameAction은 QUIC Stream/DATAGRAM + multipath 환경에서의
프레임 단위 전송 결정을 표현한다.
"""

from __future__ import annotations

from enum import Enum, auto
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


def _resolve_thresholds(
    importance_thresholds: tuple[float, float] | None,
) -> tuple[float, float]:
    if importance_thresholds is not None:
        return importance_thresholds
    return _LOW_IMPORTANCE, _HIGH_IMPORTANCE


def estimate_completion_ms(
    *,
    payload_bytes: int,
    current_time_ms: float,
    network: NetworkState,
    queue_bytes: int = 0,
) -> float:
    """Estimate application-visible frame completion time for deadline checks."""
    effective_bandwidth_mbps = max(float(network.bandwidth_mbps), 0.001)
    queued_bytes = max(int(queue_bytes), int(network.queue_bytes), 0)
    total_bytes = max(int(payload_bytes), 0) + queued_bytes
    transmit_time_ms = (total_bytes * 8.0) / (effective_bandwidth_mbps * 1_000_000.0) * 1000.0
    return float(current_time_ms) + transmit_time_ms + float(network.rtt_ms) * 0.5


def select_deadline_feasible_action(
    *,
    importance_score: float,
    payload_bytes: int,
    current_time_ms: float,
    display_deadline_ms: float,
    network: NetworkState,
    available_paths: int = 1,
    queue_bytes: int = 0,
    importance_thresholds: tuple[float, float] | None = None,
) -> FrameAction:
    """Choose a frame action after first checking deadline feasibility."""
    low_threshold, high_threshold = _resolve_thresholds(importance_thresholds)
    estimated_completion_ms = estimate_completion_ms(
        payload_bytes=payload_bytes,
        current_time_ms=current_time_ms,
        network=network,
        queue_bytes=queue_bytes,
    )
    deadline_margin_ms = float(display_deadline_ms) - estimated_completion_ms
    is_feasible = deadline_margin_ms >= 0.0

    if not is_feasible and importance_score < low_threshold:
        return FrameAction.DROP

    if importance_score >= high_threshold:
        if available_paths > 1 and is_feasible and deadline_margin_ms > _CRITICAL_SLACK_MS:
            return FrameAction.DUPLICATE
        if available_paths > 1:
            return FrameAction.RELIABLE_MULTI
        return FrameAction.RELIABLE_SINGLE

    if not is_feasible:
        return FrameAction.UNRELIABLE

    if importance_score >= low_threshold and deadline_margin_ms <= float(network.rtt_ms) * 0.5:
        return FrameAction.UNRELIABLE

    if importance_score < low_threshold:
        return FrameAction.UNRELIABLE

    if available_paths > 1:
        return FrameAction.RELIABLE_MULTI

    return FrameAction.RELIABLE_SINGLE


def select_action(
    importance_score: float,
    deadline_slack_ms: float,
    network: NetworkState,
    available_paths: int = 1,
    queue_bytes: int = 0,
    estimated_batch_gain: float = 0.0,
    *,
    importance_thresholds: tuple[float, float] | None = None,
) -> FrameAction:
    """importance score와 deadline slack으로 전송 행동을 결정한다.

    cross-layer 적응 전송:
      - 콘텐츠 중요도(Tüker 2024)와 전송 계층 상태(Borisov 2025)를 동시에 고려
      - queue_bytes/estimated_batch_gain은 현재 배칭 큐 상태와
        배칭 유지 시 예상되는 throughput 향상률을 반영

    Args:
        importance_thresholds: (low, high) 임계값 튜플. None이면 기본값 사용.
            모델마다 점수 분포가 다를 수 있으므로 동적 임계값 지원.

    규칙 우선순위:
    1. deadline 이미 초과 & 낮은 중요도 → DROP
    2. 매우 높은 중요도 & 여유 있음 & 멀티패스 가능 → DUPLICATE
    3. 높은 중요도 → RELIABLE (MULTI if available)
    4. 배칭 이득 높고 여유 충분 & 중간 중요도 → RELIABLE_SINGLE (flush 유보)
    5. slack 여유 충분 & 낮은 중요도 → UNRELIABLE
    6. 기본 → RELIABLE_SINGLE
    """
    low_threshold, high_threshold = _resolve_thresholds(importance_thresholds)

    if deadline_slack_ms <= 0 and importance_score < low_threshold:
        return FrameAction.DROP

    if importance_score >= high_threshold:
        if deadline_slack_ms > _CRITICAL_SLACK_MS and available_paths > 1:
            return FrameAction.DUPLICATE
        if available_paths > 1:
            return FrameAction.RELIABLE_MULTI
        return FrameAction.RELIABLE_SINGLE

    # --- cross-layer 배칭 유보 (Borisov 2025 관점) ---
    # 배칭 이득이 충분하고 deadline 여유가 있으면 즉시 flush를 지연하여
    # throughput을 높인다. 단, 중요도가 높은 프레임은 이 규칙을 건너뜀.
    _BATCH_GAIN_THRESHOLD = 0.15  # 15% 이상 throughput 향상 예상 시
    if (
        estimated_batch_gain >= _BATCH_GAIN_THRESHOLD
        and deadline_slack_ms > network.rtt_ms * 3
        and importance_score < high_threshold
        and importance_score >= low_threshold
    ):
        return FrameAction.RELIABLE_SINGLE  # flush 유보 → 배칭 축적

    if deadline_slack_ms > network.rtt_ms * 2 and importance_score < low_threshold:
        return FrameAction.UNRELIABLE

    if available_paths > 1 and importance_score >= low_threshold:
        return FrameAction.RELIABLE_MULTI

    return FrameAction.RELIABLE_SINGLE

