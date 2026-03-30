"""RL 실험용 프레임 단위 전송 스케줄링 환경.

core.simulator / policy.importance / policy.action / eval.metrics를 활용하여
Gymnasium 스타일 reset()/step() 인터페이스를 제공한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.transport import TransportConfig, PathState, TCPTransportModel
from core.workload import (
    VideoTraceConfig,
    WorkloadConfig,
    generate_workload,
    frame_interval_ms,
)
from eval.metrics import compute_all_video_metrics
from policy.action import FrameAction, select_action
from policy.importance import HeuristicImportanceScorer, NetworkState


@dataclass
class EnvConfig:
    """환경 설정값."""
    workload_cfg: Optional[WorkloadConfig] = None
    transport_cfg: Optional[TransportConfig] = None

    max_steps: int = 500
    seed: int = 42

    alpha_qoe: float = 1.0
    beta_latency: float = 0.3
    gamma_drop_penalty: float = 0.5


@dataclass
class StepResult:
    state: List[float] = field(default_factory=list)
    reward: float = 0.0
    terminated: bool = False
    truncated: bool = False
    info: Dict[str, float] = field(default_factory=dict)


class FrameSchedulingEnv:
    """프레임 단위 전송 스케줄링 RL 환경.

    state vector (14차원):
      0: frame_type_encoded (I=0, P=1, B=2, FILE=3)
      1: importance_score
      2: deadline_slack_ms
      3: payload_bytes
      4: gop_progress (현재 GOP 내 진행률)
      5: queue_bytes (누적 대기 바이트)
      6: rtt_ms
      7: bandwidth_mbps
      8: buffer_level_ms
      9: late_frame_ratio_so_far
     10: step_index (정규화)
     11: key_frame
     12: estimated_batch_gain (cross-layer: Borisov 2025 관점)
     13: loss_rate

    action space: FrameAction enum (0~4)
    """

    FRAME_TYPE_MAP = {"I": 0.0, "P": 1.0, "B": 2.0, "FILE": 3.0}

    def __init__(self, config: Optional[EnvConfig] = None) -> None:
        self.config = config or EnvConfig()
        self._rng = np.random.RandomState(self.config.seed)

        if self.config.workload_cfg is None:
            from core.workload import StaticFileConfig
            self.config.workload_cfg = StaticFileConfig(file_size_bytes=1_000_000, chunk_size_bytes=4096)
        if self.config.transport_cfg is None:
            self.config.transport_cfg = TransportConfig(rtt_ms=20.0, bandwidth_mbps=10.0, delayed_ack_ms=20.0)

        self.transport_model = TCPTransportModel(self.config.transport_cfg)
        self.scorer = HeuristicImportanceScorer(
            playback_buffer_ms=getattr(self.config.workload_cfg, "playback_buffer_ms", 50.0),
        )

        self.events: pd.DataFrame = pd.DataFrame()
        self.step_count = 0
        self.current_frame_idx = 0
        self.frame_records: List[Dict[str, object]] = []
        self.total_latency_ms = 0.0
        self.last_completion_ms = 0.0
        self.queue_bytes = 0
        self.late_count = 0
        self.drop_count = 0

    def reset(self, seed: Optional[int] = None) -> Tuple[List[float], Dict[str, float]]:
        if seed is not None:
            self._rng = np.random.RandomState(seed)
        self.events = generate_workload(self.config.workload_cfg)
        self.step_count = 0
        self.current_frame_idx = 0
        self.frame_records = []
        self.total_latency_ms = 0.0
        self.last_completion_ms = 0.0
        self.queue_bytes = 0
        self.late_count = 0
        self.drop_count = 0
        return self._get_state(), self._get_info()

    def step(self, action_idx: int) -> Tuple[List[float], float, bool, bool, Dict[str, float]]:
        self.step_count += 1
        action = list(FrameAction)[min(action_idx, len(FrameAction) - 1)]

        if self.current_frame_idx >= len(self.events):
            return self._get_state(), 0.0, True, False, self._get_info()

        row = self.events.iloc[self.current_frame_idx]
        frame_dict = row.to_dict()
        cfg = self.config.transport_cfg

        network = NetworkState(
            rtt_ms=cfg.rtt_ms,
            bandwidth_mbps=cfg.bandwidth_mbps,
            buffer_level_ms=max(0.0, float(row.get("display_deadline_ms", 0)) - self.last_completion_ms),
            queue_bytes=self.queue_bytes,
        )

        importance = self.scorer.score(frame_dict, network)
        payload_bytes = int(row["payload_bytes"])
        event_time_ms = float(row["event_time_ms"])

        if action == FrameAction.DROP:
            self.drop_count += 1
            on_time = False
            completion_ms = self.last_completion_ms
        else:
            send_start_ms = max(event_time_ms, self.last_completion_ms)
            completion_ms = self.transport_model.estimate_completion(payload_bytes, send_start_ms)
            self.last_completion_ms = completion_ms

            deadline_ms = float(row.get("display_deadline_ms", float("inf")))
            on_time = completion_ms <= deadline_ms
            latency_ms = completion_ms - event_time_ms
            self.total_latency_ms += latency_ms

        if not on_time:
            self.late_count += 1

        self.frame_records.append({
            "gop_id": int(row.get("gop_id", -1)),
            "key_frame": int(row.get("key_frame", 0)),
            "payload_bytes": payload_bytes,
            "on_time": on_time,
        })

        self.current_frame_idx += 1
        terminated = self.current_frame_idx >= len(self.events) or self.step_count >= self.config.max_steps
        reward = self._compute_reward(on_time, importance, action)

        return self._get_state(), reward, terminated, False, self._get_info()

    def _compute_reward(self, on_time: bool, importance: float, action: FrameAction) -> float:
        qoe_reward = importance if on_time else -importance * 0.5
        drop_penalty = -self.config.gamma_drop_penalty if action == FrameAction.DROP else 0.0
        return self.config.alpha_qoe * qoe_reward + drop_penalty

    def _get_state(self) -> List[float]:
        if self.current_frame_idx >= len(self.events):
            return [0.0] * 14

        row = self.events.iloc[self.current_frame_idx]
        frame_type_str = str(row.get("frame_type", "FILE")).upper()
        deadline_ms = float(row.get("display_deadline_ms", 0.0))
        now_ms = float(row.get("event_time_ms", 0.0))
        slack_ms = deadline_ms - max(now_ms, self.last_completion_ms)

        gop_id = int(row.get("gop_id", -1))
        if gop_id >= 0:
            gop_mask = self.events["gop_id"] == gop_id
            gop_size = int(gop_mask.sum())
            gop_pos = int((self.events.index[gop_mask] <= self.current_frame_idx).sum())
            gop_progress = gop_pos / max(gop_size, 1)
        else:
            gop_progress = 0.0

        total_frames = max(self.current_frame_idx, 1)
        late_ratio_so_far = self.late_count / total_frames

        # cross-layer 배칭 이득 추정 (Borisov 2025 관점)
        cfg = self.config.transport_cfg
        _est_batch_gain = min(
            1.0,
            self.queue_bytes / max(cfg.mss_bytes, 1),
        ) * cfg.nagle_penalty_factor

        return [
            self.FRAME_TYPE_MAP.get(frame_type_str, 3.0),
            self.scorer.score(row.to_dict(), NetworkState(
                rtt_ms=cfg.rtt_ms,
                bandwidth_mbps=cfg.bandwidth_mbps,
                queue_bytes=self.queue_bytes,
            )),
            slack_ms,
            float(row["payload_bytes"]),
            gop_progress,
            float(self.queue_bytes),
            float(cfg.rtt_ms),
            float(cfg.bandwidth_mbps),
            max(0.0, slack_ms),
            late_ratio_so_far,
            self.step_count / max(self.config.max_steps, 1),
            float(row.get("key_frame", 0)),
            _est_batch_gain,
            0.0,  # loss_rate (향후 동적 업데이트)
        ]

    def _get_info(self) -> Dict[str, float]:
        metrics = compute_all_video_metrics(self.frame_records)
        return {
            **{k: float(v) for k, v in metrics.items()},
            "step_count": float(self.step_count),
            "total_latency_ms": self.total_latency_ms,
            "drop_count": float(self.drop_count),
        }


def run_episode(env: FrameSchedulingEnv, max_steps: Optional[int] = None) -> Dict[str, float]:
    """heuristic 정책 기반 smoke 실행 유틸리티."""
    state, _ = env.reset()
    steps = max_steps or env.config.max_steps
    reward_sum = 0.0

    for _ in range(steps):
        if env.current_frame_idx >= len(env.events):
            break
        row = env.events.iloc[env.current_frame_idx]
        cfg = env.config.transport_cfg
        network = NetworkState(rtt_ms=cfg.rtt_ms, bandwidth_mbps=cfg.bandwidth_mbps, queue_bytes=env.queue_bytes)
        importance = env.scorer.score(row.to_dict(), network)
        deadline_ms = float(row.get("display_deadline_ms", float("inf")))
        slack_ms = deadline_ms - max(float(row["event_time_ms"]), env.last_completion_ms)
        action = select_action(importance, slack_ms, network)
        action_idx = list(FrameAction).index(action)

        _, reward, done, _, info = env.step(action_idx)
        reward_sum += reward
        if done:
            break

    return {
        "episode_reward": reward_sum,
        **env._get_info(),
    }


if __name__ == "__main__":
    from core.workload import StaticFileConfig
    env = FrameSchedulingEnv(EnvConfig(
        workload_cfg=StaticFileConfig(file_size_bytes=100_000, chunk_size_bytes=4096),
        max_steps=50,
        seed=7,
    ))
    summary = run_episode(env)
    print(summary)
