# RL 프레임 스케줄링 환경 (`rl/env.py`)

> **연구 맥락**: 본 연구는 H.264 비디오 프레임 중요도를 동적으로 판단하여 전송 행동을 결정하는 적응 전송 연구다.
> RL 환경은 중요도 판단 방법론 v3(RL 기반 scorer)의 실험 기반이다.

## 목적

`rl/env.py`의 `FrameSchedulingEnv`는 프레임 중요도 기반 전송 행동을 RL로 탐색하기 위한 환경이다.
현재 단계에서는 다음을 목표로 한다.

1. 프레임 단위 state/action/reward 인터페이스 고정
2. `core.simulator` 기반 시뮬레이션 통합
3. heuristic/ML scorer 대비 RL scorer의 QoE 기여 비교 가능성 확보

## 환경 인터페이스

- 클래스: `FrameSchedulingEnv`
- 핵심 메서드:
  - `reset(seed=None) -> (state, info)`
  - `step(action) -> (state, reward, terminated, truncated, info)`

Gymnasium 스타일에 맞춰 DQN/PPO 래핑이 쉽게 구성되도록 했다.

## State 정의 (12차원)

state는 아래 순서의 실수 벡터다.

1. `frame_type_encoded` (I=0, P=1, B=2, FILE=3)
2. `importance_score` (Stage A scorer 출력)
3. `deadline_slack_ms`
4. `payload_bytes`
5. `gop_progress` (현재 GOP 내 진행률)
6. `queue_bytes` (누적 대기 바이트)
7. `rtt_ms`
8. `bandwidth_mbps`
9. `buffer_level_ms`
10. `late_frame_ratio_so_far`
11. `step_index` (정규화)
12. `key_frame`

## Action 정의

`FrameAction` enum (5개):

- `0`: `RELIABLE_SINGLE` — QUIC Stream, 단일 경로
- `1`: `RELIABLE_MULTI` — QUIC Stream, 멀티패스
- `2`: `UNRELIABLE` — QUIC DATAGRAM
- `3`: `DUPLICATE` — 고중요 프레임 중복 전송
- `4`: `DROP` — deadline 초과 예상 프레임 드롭

## Reward 정의

QoE 중심 보상식:

```text
reward = w1 * block_completion_ratio
       + w2 * (1 - late_frame_ratio)
       + w3 * (1 - rebuffer_ratio)
       - w4 * transmission_cost
```

가중치는 환경 설정으로 제어한다.

## 시뮬레이터 통합

`FrameSchedulingEnv`는 `core.simulator`, `policy.importance`, `eval.metrics` 모듈을 직접 사용한다.

- 입력: H.264 frame trace → `core.workload` 로 이벤트 생성
- 중요도: `policy.importance.HeuristicImportanceScorer` (v1, 향후 ML/RL scorer 교체)
- 전송: `core.transport.TransportModel` 기반 완료 시각 추정
- 평가: `eval.metrics` 기반 QoE 지표 계산

## 평가 프로토콜

### holdout 분할

- 시나리오 축: `content_type`, `frame_distribution`, `bandwidth band`, `rtt band`, `loss_rate`
- 원칙: 학습/검증/테스트 시나리오를 축 조합 단위로 분리

### 공통 비교 지표 (QoE 중심)

- `rebuffer_ratio`
- `ssim_proxy`
- `block_completion_ratio`
- `late_frame_ratio`
- `keyframe_late_ratio`
- `decodable_gop_ratio`

### 비교 대상 (중요도 판단 방법론 비교)

1. `HeuristicImportanceScorer` (v1)
2. `MLImportanceScorer` (v2, 예정)
3. `RLImportanceScorer` (v3, 본 환경 기반)

## 재현성 규칙

- seed 고정: 환경, 학습기, 시나리오 샘플러 분리 관리
- CSV 파일명 규칙:
  - `eval_<scorer_version>_<split>_seed<seed>.csv`
- 시나리오 매트릭스 버전 태깅:
  - 예: `scenario_matrix_v1.yaml`

## TODO

- [ ] DQN/PPO 학습 루프 예시 스크립트 추가
- [ ] heuristic/ML/RL scorer 결과 비교 테이블 자동 생성 스크립트 추가
- [ ] 동적 bandwidth trace 시나리오 대응
