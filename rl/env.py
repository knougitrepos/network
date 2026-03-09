"""RL 실험용 TCP Content-Aware Batching 환경 초안.

이 파일은 외부 RL 프레임워크에 종속되지 않는 최소 환경 인터페이스를 제공한다.
Gymnasium 스타일의 `reset()/step()` 사용 패턴을 따르며,
기존 시뮬레이터 함수(`run_simulation`)와의 연결을 쉽게 하기 위해
정책 입력/출력 명세와 reward 계산 규칙을 명시적으로 분리했다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional, Tuple
import math
import random


class ContentType(IntEnum):
    """콘텐츠 타입 인코딩."""

    FILE = 0
    STREAM = 1


class Action(IntEnum):
    """RL 정책이 선택할 수 있는 행동 집합."""

    WAIT = 0
    FLUSH = 1
    INCREASE_BATCH = 2
    DECREASE_BATCH = 3


@dataclass(frozen=True)
class EnvConfig:
    """환경 설정값.

    alpha_latency: latency 패널티 가중치
    beta_staleness: staleness 패널티 가중치
    gamma_syscall: flush 호출 패널티 가중치
    """

    max_steps: int = 200
    initial_batch_size: int = 16 * 1024
    min_batch_size: int = 2 * 1024
    max_batch_size: int = 64 * 1024
    batch_size_step: int = 2 * 1024

    alpha_latency: float = 0.8
    beta_staleness: float = 0.5
    gamma_syscall: float = 0.2

    seed: Optional[int] = 42


@dataclass
class Message:
    """단일 메시지 이벤트."""

    size_bytes: int
    inter_arrival_ms: float
    content_type: ContentType


@dataclass
class StepMetrics:
    """스텝 단위 측정치."""

    latency_ms: float = 0.0
    throughput_mbps: float = 0.0
    staleness_penalty: float = 0.0
    syscall_count: int = 0


class TCPBatchingEnv:
    """TCP content-aware batching RL 환경 초안.

    상태 벡터(state):
      - queue_size_bytes
      - queue_len
      - mean_message_size
      - estimated_message_rate
      - elapsed_time_since_last_flush_ms
      - estimated_rtt_ms
      - current_batch_size
      - content_type(0=file, 1=stream)

    행동(action):
      - WAIT(0)
      - FLUSH(1)
      - INCREASE_BATCH(2)
      - DECREASE_BATCH(3)

    보상(reward):
      throughput_mbps
      - alpha_latency * latency_ms
      - beta_staleness * staleness_penalty
      - gamma_syscall * syscall_count
    """

    def __init__(self, config: Optional[EnvConfig] = None):
        self.config = config or EnvConfig()
        self._rng = random.Random(self.config.seed)

        self.step_count = 0
        self.current_batch_size = self.config.initial_batch_size
        self.elapsed_since_last_flush_ms = 0.0

        self.queue: List[Message] = []
        self.last_metrics = StepMetrics()
        self.estimated_rtt_ms = 20.0

    def reset(self, seed: Optional[int] = None) -> Tuple[List[float], Dict[str, float]]:
        if seed is not None:
            self._rng.seed(seed)
        elif self.config.seed is not None:
            self._rng.seed(self.config.seed)

        self.step_count = 0
        self.current_batch_size = self.config.initial_batch_size
        self.elapsed_since_last_flush_ms = 0.0
        self.queue.clear()
        self.last_metrics = StepMetrics()
        self.estimated_rtt_ms = self._sample_rtt()

        self._enqueue_random_message()
        return self._get_state(), self._get_info()

    def step(self, action: int) -> Tuple[List[float], float, bool, bool, Dict[str, float]]:
        self.step_count += 1

        if action == Action.INCREASE_BATCH:
            self.current_batch_size = min(
                self.current_batch_size + self.config.batch_size_step,
                self.config.max_batch_size,
            )
            metrics = self._simulate_wait_step()
        elif action == Action.DECREASE_BATCH:
            self.current_batch_size = max(
                self.current_batch_size - self.config.batch_size_step,
                self.config.min_batch_size,
            )
            metrics = self._simulate_wait_step()
        elif action == Action.FLUSH:
            metrics = self._simulate_flush_step()
        else:
            metrics = self._simulate_wait_step()

        reward = self._compute_reward(metrics)
        self.last_metrics = metrics

        terminated = self.step_count >= self.config.max_steps
        truncated = False

        self._enqueue_random_message()

        return self._get_state(), reward, terminated, truncated, self._get_info()

    def _get_state(self) -> List[float]:
        queue_size_bytes = sum(m.size_bytes for m in self.queue)
        queue_len = len(self.queue)
        mean_message_size = (queue_size_bytes / queue_len) if queue_len else 0.0

        total_inter_arrival = sum(m.inter_arrival_ms for m in self.queue)
        estimated_message_rate = (1000.0 / total_inter_arrival) if total_inter_arrival > 0 else 0.0

        content_type_value = float(self.queue[-1].content_type if self.queue else ContentType.FILE)

        return [
            float(queue_size_bytes),
            float(queue_len),
            float(mean_message_size),
            float(estimated_message_rate),
            float(self.elapsed_since_last_flush_ms),
            float(self.estimated_rtt_ms),
            float(self.current_batch_size),
            content_type_value,
        ]

    def _get_info(self) -> Dict[str, float]:
        return {
            "latency_ms": self.last_metrics.latency_ms,
            "throughput_mbps": self.last_metrics.throughput_mbps,
            "staleness_penalty": self.last_metrics.staleness_penalty,
            "syscall_count": float(self.last_metrics.syscall_count),
            "queue_len": float(len(self.queue)),
            "batch_size": float(self.current_batch_size),
        }

    def _compute_reward(self, metrics: StepMetrics) -> float:
        return (
            metrics.throughput_mbps
            - self.config.alpha_latency * metrics.latency_ms
            - self.config.beta_staleness * metrics.staleness_penalty
            - self.config.gamma_syscall * metrics.syscall_count
        )

    def _simulate_wait_step(self) -> StepMetrics:
        # wait 시 queue 증가/지연 누적
        wait_ms = self._rng.uniform(1.0, 8.0)
        self.elapsed_since_last_flush_ms += wait_ms

        queue_size = sum(m.size_bytes for m in self.queue)
        staleness = self.elapsed_since_last_flush_ms * (1.0 + 0.5 * (queue_size > self.current_batch_size))

        return StepMetrics(
            latency_ms=wait_ms,
            throughput_mbps=max(0.05, queue_size / 1_000_000),
            staleness_penalty=staleness,
            syscall_count=0,
        )

    def _simulate_flush_step(self) -> StepMetrics:
        queue_size = sum(m.size_bytes for m in self.queue)
        if queue_size == 0:
            return StepMetrics(latency_ms=0.2, throughput_mbps=0.0, staleness_penalty=0.0, syscall_count=1)

        # 기존 run_simulation 결과와 연결할 때는 아래 계산을 대체하도록 설계
        effective_bandwidth_mbps = max(1.0, 120.0 - 0.2 * self.estimated_rtt_ms)
        transmit_time_ms = (queue_size * 8.0) / (effective_bandwidth_mbps * 1_000.0)
        latency_ms = self.elapsed_since_last_flush_ms + transmit_time_ms + self.estimated_rtt_ms * 0.25

        throughput_mbps = (queue_size * 8.0) / max(transmit_time_ms, 1e-6) / 1_000.0
        staleness = max(0.0, self.elapsed_since_last_flush_ms - 3.0)

        self.queue.clear()
        self.elapsed_since_last_flush_ms = 0.0
        self.estimated_rtt_ms = self._sample_rtt()

        return StepMetrics(
            latency_ms=latency_ms,
            throughput_mbps=throughput_mbps,
            staleness_penalty=staleness,
            syscall_count=1,
        )

    def _enqueue_random_message(self) -> None:
        content_type = ContentType.STREAM if self._rng.random() < 0.45 else ContentType.FILE
        if content_type == ContentType.STREAM:
            size = int(self._rng.uniform(200, 4_000))
            inter_arrival = self._rng.uniform(0.4, 3.0)
        else:
            size = int(self._rng.uniform(4_000, 32_000))
            inter_arrival = self._rng.uniform(1.0, 6.0)

        self.queue.append(
            Message(size_bytes=size, inter_arrival_ms=inter_arrival, content_type=content_type)
        )

    def _sample_rtt(self) -> float:
        # log-normal 분포로 tail latency를 가볍게 반영
        return min(180.0, max(5.0, math.exp(self._rng.normalvariate(3.0, 0.35))))


def run_episode(env: TCPBatchingEnv, max_steps: Optional[int] = None) -> Dict[str, float]:
    """랜덤 정책 기반 간단 smoke 실행 유틸리티."""

    state, _ = env.reset()
    del state

    steps = max_steps or env.config.max_steps
    reward_sum = 0.0
    latency_sum = 0.0
    throughput_sum = 0.0

    for _ in range(steps):
        action = env._rng.choice(list(Action))
        _, reward, done, _, info = env.step(int(action))

        reward_sum += reward
        latency_sum += info["latency_ms"]
        throughput_sum += info["throughput_mbps"]

        if done:
            break

    executed_steps = float(env.step_count)
    return {
        "episode_reward": reward_sum,
        "latency_mean_ms": latency_sum / max(executed_steps, 1.0),
        "throughput_mean_mbps": throughput_sum / max(executed_steps, 1.0),
        "steps": executed_steps,
    }


if __name__ == "__main__":
    environment = TCPBatchingEnv(EnvConfig(seed=7, max_steps=50))
    summary = run_episode(environment)
    print(summary)
