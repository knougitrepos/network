"""Stage A: 프레임 중요도 스코어링.

v1 heuristic은 frame type(I/P/B), deadline slack, GOP 내 위치를 반영한다.
향후 ML 기반 scorer로 교체 가능하도록 인터페이스를 분리한다.
"""

from __future__ import annotations

import abc
import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


logger = logging.getLogger(__name__)


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


def build_importance_features(
    frame: Dict[str, object],
    network: NetworkState,
    playback_buffer_ms: float = 50.0,
) -> List[float]:
    """ML scorer용 입력 feature 벡터를 생성한다.

    feature order:
    [I_onehot, P_onehot, B_onehot, key_frame, payload_bytes,
     slack_ms, slack_ratio, rtt_ms, bandwidth_mbps, loss_rate, buffer_level_ms]
    """
    frame_type = str(frame.get("frame_type", "B")).upper()
    deadline_ms = float(frame.get("display_deadline_ms", float("inf")))
    now_ms = float(frame.get("event_time_ms", 0.0))
    normalized_buffer_ms = max(playback_buffer_ms, 1.0)
    slack_ms = deadline_ms - now_ms
    slack_ratio = max(0.0, min(2.0, slack_ms / normalized_buffer_ms))

    return [
        1.0 if frame_type == "I" else 0.0,
        1.0 if frame_type == "P" else 0.0,
        1.0 if frame_type == "B" else 0.0,
        float(frame.get("key_frame", 0)),
        float(frame.get("payload_bytes", 0.0)),
        float(slack_ms),
        float(slack_ratio),
        float(network.rtt_ms),
        float(network.bandwidth_mbps),
        float(network.loss_rate),
        float(network.buffer_level_ms),
    ]


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


class MLImportanceScorer(ImportanceScorer):
    """Stage A v2용 ML 기반 scorer 스캐폴딩.

    - model_path가 주어지면 pickle 모델을 로드한다.
    - 모델이 없거나 추론 실패 시 heuristic scorer로 안전하게 폴백한다.
    """

    def __init__(self, model_path: Optional[str] = None, playback_buffer_ms: float = 50.0) -> None:
        self.model_path = model_path
        self.playback_buffer_ms = max(playback_buffer_ms, 1.0)
        self.model = None
        self._fallback = HeuristicImportanceScorer(playback_buffer_ms=self.playback_buffer_ms)

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str) -> None:
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"ML model file not found: {path}")
        with path.open("rb") as f:
            self.model = pickle.load(f)

    def _build_features(self, frame: Dict[str, object], network: NetworkState) -> List[float]:
        return build_importance_features(
            frame=frame,
            network=network,
            playback_buffer_ms=self.playback_buffer_ms,
        )

    def _predict(self, features: np.ndarray) -> float:
        if self.model is None:
            raise RuntimeError("ML model is not loaded")

        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(features)
            return float(probs[0][-1])

        if hasattr(self.model, "predict"):
            pred = self.model.predict(features)
            return float(pred[0])

        raise TypeError("Loaded model does not expose predict_proba or predict")

    def score(self, frame: Dict[str, object], network: NetworkState) -> float:
        features = np.asarray(self._build_features(frame, network), dtype=float).reshape(1, -1)

        if self.model is None:
            return self._fallback.score(frame, network)

        try:
            raw = self._predict(features)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ML scorer inference failed; fallback to heuristic scorer: %s", exc)
            return self._fallback.score(frame, network)

        return min(1.0, max(0.0, float(raw)))
