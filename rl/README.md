# RL 실험 초안 설계 (`rl/env.py`)

## 목적

`rl/env.py`는 TCP content-aware batching 정책을 RL로 탐색하기 위한 **초기 환경 스펙**이다.
현재 단계에서는 다음을 목표로 한다.

1. state/action/reward 인터페이스 고정
2. 기존 노트북 시뮬레이터(`run_simulation`)와의 연결 지점 명확화
3. baseline(heuristic, ml_regression_adaptive) 대비 동일 지표 비교 가능성 확보

## 환경 인터페이스

- 클래스: `TCPBatchingEnv`
- 핵심 메서드:
  - `reset(seed=None) -> (state, info)`
  - `step(action) -> (state, reward, terminated, truncated, info)`

Gymnasium 스타일에 맞춰 추후 DQN/PPO 래핑이 쉽게 구성되도록 했다.

## State 정의

state는 아래 순서의 실수 벡터다.

1. `queue_size_bytes`
2. `queue_len`
3. `mean_message_size`
4. `estimated_message_rate`
5. `elapsed_time_since_last_flush_ms`
6. `estimated_rtt_ms`
7. `current_batch_size`
8. `content_type` (`0=file`, `1=stream`)

## Action 정의

정수형 이산 행동 집합:

- `0`: `WAIT`
- `1`: `FLUSH`
- `2`: `INCREASE_BATCH`
- `3`: `DECREASE_BATCH`

## Reward 정의

기본 보상식:

```text
reward = throughput_mbps
         - alpha_latency * latency_ms
         - beta_staleness * staleness_penalty
         - gamma_syscall * syscall_count
```

튜닝 가중치는 `EnvConfig`로 제어한다.

## 기존 시뮬레이터 연계 지점

현재 `_simulate_flush_step()`는 경량 근사식을 사용한다.
다음 단계에서 이 부분을 `run_simulation` 호출 기반으로 대체한다.

- 입력 매핑:
  - queue snapshot -> 시뮬레이터 입력 트래픽
  - `current_batch_size` -> 정책 파라미터
- 출력 매핑:
  - 시뮬레이터 결과 `latency/throughput/staleness/syscall_count` -> `StepMetrics`

## 평가 프로토콜(초안)

### holdout 분할

- 시나리오 축: `content_type`, `arrival profile`, `message size band`, `rtt band`
- 원칙: 학습/검증/테스트 시나리오를 축 조합 단위로 분리

### 공통 비교 지표

- `latency_mean_ms`
- `latency_p95_ms`
- `throughput_mbps`
- `staleness_penalty`
- `syscall_count`

### 비교 대상

1. `heuristic_adaptive`
2. `ml_regression_adaptive`
3. `rl_adaptive` (신규)

## 재현성 규칙(초안)

- seed 고정: 환경, 학습기, 시나리오 샘플러 분리 관리
- CSV 파일명 규칙:
  - `eval_<policy>_<split>_seed<seed>.csv`
- 시나리오 매트릭스 버전 태깅:
  - 예: `scenario_matrix_v1.yaml`

## TODO

- [ ] `_simulate_flush_step()`를 `run_simulation` 연동으로 교체
- [ ] 학습 루프(DQN/PPO) 예시 스크립트 추가
- [ ] baseline/rl 결과 비교 테이블 자동 생성 스크립트 추가
