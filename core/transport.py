"""전송 모델 설정 및 추상화."""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class TransportConfig:
    """TCP 기반 전송 파라미터."""
    rtt_ms: float
    bandwidth_mbps: float
    delayed_ack_ms: float
    mss_bytes: int = 1460
    nagle_penalty_factor: float = 0.25
    propagation_factor: float = 0.5


@dataclass(frozen=True)
class PathState:
    """단일 네트워크 경로의 실시간 상태."""
    rtt_ms: float
    bandwidth_mbps: float
    loss_rate: float = 0.0
    last_release_ms: float = 0.0


def serialize_transport_config(cfg: TransportConfig) -> Dict[str, float]:
    return {
        key: float(value) if isinstance(value, (int, float)) else value
        for key, value in asdict(cfg).items()
    }


class TransportModel(abc.ABC):
    """전송 완료 시각 추정 공통 인터페이스."""

    @abc.abstractmethod
    def estimate_completion(
        self,
        payload_bytes: int,
        send_start_ms: float,
        path: Optional[PathState] = None,
    ) -> float:
        ...


class TCPTransportModel(TransportModel):
    """기존 TCP 근사 수식 기반 모델."""

    def __init__(self, config: TransportConfig) -> None:
        self.config = config

    def estimate_completion(
        self,
        payload_bytes: int,
        send_start_ms: float,
        path: Optional[PathState] = None,
    ) -> float:
        cfg = self.config
        tx_time_ms = (payload_bytes * 8.0) / (cfg.bandwidth_mbps * 1_000_000.0) * 1000.0
        ack_penalty_ms = (
            min(cfg.delayed_ack_ms, cfg.nagle_penalty_factor * cfg.rtt_ms)
            if payload_bytes < cfg.mss_bytes
            else 0.0
        )
        return send_start_ms + tx_time_ms + cfg.propagation_factor * cfg.rtt_ms + ack_penalty_ms


@dataclass(frozen=True)
class QUICTransportConfig:
    """QUIC 기반 전송 파라미터 (멀티패스 확장 대비)."""
    paths: tuple  # Tuple[PathState, ...] — 1개 이상
    mss_bytes: int = 1400
    datagram_overhead_bytes: int = 50


class QUICTransportModel(TransportModel):
    """QUIC Stream/DATAGRAM 기반 모델 (프로토타입)."""

    def __init__(self, config: QUICTransportConfig) -> None:
        self.config = config

    def estimate_completion(
        self,
        payload_bytes: int,
        send_start_ms: float,
        path: Optional[PathState] = None,
    ) -> float:
        if path is None:
            path = self.config.paths[0]
        effective_bw = path.bandwidth_mbps * (1.0 - path.loss_rate)
        tx_time_ms = (payload_bytes * 8.0) / (max(effective_bw, 0.001) * 1_000_000.0) * 1000.0
        return send_start_ms + tx_time_ms + 0.5 * path.rtt_ms
