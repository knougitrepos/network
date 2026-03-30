# 연구 목표

> **최종 갱신**: 2026-03-30

## 한 줄 요약

H.264 비디오 프레임의 중요도(I/P/B)를 동적으로 판단하여 프레임별 전송 행동(신뢰/비신뢰, 경로, 중복)을 결정하는 QoE 중심 적응 전송 연구다.
중요도 판단 방법론(휴리스틱 → ML → RL)의 단계적 고도화가 핵심 기여점이다.

## 연구 정체성

> **본 연구는 TCP batching 연구가 아니다.**
> H.264 코덱의 프레임 중요도(I/P/B)를 동적으로 판단하여 프레임 단위로 효율적인 전송 행동을 결정하는 것이 주요 목표다.
> 참조 논문(Simsek et al., 2023)의 "콘텐츠 중요도 기반 적응 전송" 방향과 매우 유사하며,
> 여기에 머신러닝/휴리스틱/강화학습 기반의 중요도 판단을 추가 실험 목표로 삼는다.

## 참조 논문과의 관계

- **참조**: Simsek et al., "Using packet trimming at the edge for in-network video quality adaption", 2023
- **공통점**: 콘텐츠 중요도에 따라 전송 리소스를 차등 배분
- **차이점**:

| 항목 | 참조 논문 | 본 연구 |
|------|-----------|---------|
| 단위 | BPP chunk | H.264 frame |
| 중요도 | 고정 significance value | 동적 스코어링 (heuristic → ML → RL) |
| 위치 | 네트워크 엣지 VNF에서 드롭 | 송신측에서 전송 행동 결정 |
| 전송 | BPP 프로토콜 | QUIC Stream/DATAGRAM + multipath |

## 2단 아키텍처

### Stage A — 프레임 중요도 스코어링 (핵심 기여 지점)

- 입력: H.264 frame type(I/P/B), payload size, deadline slack, GOP 위치, buffer 상태
- 출력: importance score (0.0~1.0)
- **v1** (현재): HeuristicImportanceScorer — IPB type + deadline slack + keyframe bonus
- **v2** (예정): ML 기반 scorer — RandomForest/Gradient Boosting
- **v3** (예정): RL 기반 scorer — FrameSchedulingEnv에서 QoE 보상 극대화 학습

### Stage B — 전송 행동 매핑

- 입력: importance score, deadline slack, network state, 사용 가능 경로 수
- 출력: FrameAction (RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP)

## 논문 기여 포인트

1. **중요도 판단 방법론 고도화**: 단순 I/P/B 우선순위를 넘어, heuristic → ML → RL 단계별 중요도 스코어링과 각 방법론의 QoE 기여 비교
2. **부분 신뢰성+멀티패스 결합 스케줄링**: 프레임 단위 행동 정책 제안
3. **재현 가능한 검증 프로토콜**: 시뮬레이터 → 에뮬레이터 → 실환경의 계층형 검증

## 3계층 실험 체계

1. **시뮬레이터 (현재 리포)**: 대규모 정책 탐색/어블레이션
2. **에뮬레이션 (Mininet)**: 제어 가능한 손실·RTT·대역폭 조건 검증
3. **실환경 (Wi-Fi + LTE/5G)**: 외부 요인 포함 강건성 검증

## 비교군

- HeuristicImportanceScorer (v1)
- MLImportanceScorer (v2, 예정)
- RLImportanceScorer (v3, 예정)
- MPTCP 계열 신뢰 전송 기준선
- MPQUIC/관련 구현 (가능 범위 내)

## 후속 작업 로드맵

### 중요도 판단 방법론 확장 (핵심 기여 경로)

- ML 기반 importance scorer (v2): 프레임 특성 + 네트워크 상태 → 중요도 예측
- RL 기반 importance scorer (v3): FrameSchedulingEnv에서 QoE 보상 극대화 학습
- 각 방법론(heuristic/ML/RL)의 QoE 기여 비교 분석

### 시뮬레이션 환경 확장

- QUIC 전송 모델에 실제 loss/jitter 시나리오 추가
- Mininet 에뮬레이션 연동
- video trace 다양성 확대 (1개 이상 추가)
- 실환경(Wi-Fi + LTE/5G) 검증
- 실제 SSIM/VMAF 계산 (ffmpeg 연동)

## 발표용 권장 문구

> 본 연구는 비디오 프레임의 H.264 코덱 중요도(I/P/B)를 동적으로 판단하여 프레임 단위 전송 행동을 결정하는 적응 전송 시스템을 제안한다.
> Simsek et al.(2023)의 콘텐츠 중요도 기반 적응 전송과 유사한 방향이나, 본 연구는 중요도 판단 방법론(휴리스틱, 머신러닝, 강화학습)의 단계적 고도화를 통한 QoE 개선을 핵심 기여로 삼는다.
