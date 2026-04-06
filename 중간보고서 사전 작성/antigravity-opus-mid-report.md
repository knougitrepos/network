# 콘텐츠 중요도 기반 Cross-Layer 적응 전송에서의 MPR-QUIC 행동공간 분석

## Effectiveness of MPR-QUIC Action Space in Content-Aware Cross-Layer Adaptive Transport

박동찬*

한국방송통신대학교 대학원 정보과학과

---

## 요 약

실시간 비디오 스트리밍에서 사용자 체감 품질(Quality of Experience, QoE)은 개별 프레임의 전송 지연에 의해 크게 좌우된다. 특히 H.264 코덱의 I 프레임처럼 복호 기준이 되는 고중요 프레임이 재생 마감시간(deadline)을 초과하면, 동일 GOP(Group of Pictures) 내 후속 프레임 전체가 복호 불가능해지는 연쇄적 품질 저하가 발생한다. 기존 연구는 전송 계층의 배칭(batching) 및 패이싱(pacing) 최적화와 콘텐츠 중요도 기반 선택적 전송을 각각 독립적으로 다루어왔으나, 두 관점을 통합한 교차 계층(cross-layer) 접근은 충분히 탐구되지 않았다.

본 연구에서는 H.264 프레임 유형(I/P/B)에 기반한 콘텐츠 중요도 평가와 QUIC 전송 계층의 행동 선택을 하나의 정책 프레임워크 내에서 결합하는 cross-layer 적응 전송 시스템을 제안한다. 제안 시스템은 프레임별로 중요도 점수(importance score)를 산출한 후, 재생 마감시간까지의 여유(deadline slack)와 네트워크 상태를 종합적으로 고려하여 신뢰 전송(RELIABLE), 비신뢰 전송(UNRELIABLE), 중복 전송(DUPLICATE), 전송 포기(DROP) 중 적절한 행동을 동적으로 결정한다. 이를 통해 고중요 프레임에는 보다 안전한 전송 방식을, 저중요 프레임에는 경량화된 전송 방식을 적용함으로써 한정된 네트워크 자원의 효율적 배분을 도모한다.

공개 비디오 데이터셋을 활용한 시뮬레이션 실험에서, 제안 정책(frame_action_single_path)은 기준 정책(heuristic_baseline) 대비 late_frame_ratio를 0.3267에서 0.2071로 약 36.6% 개선하였다. 다중경로 정책(frame_action_multipath)도 0.2431로 기준 정책 대비 25.6%의 개선을 보였다. 이 결과는 프레임 단위 행동공간 설계가 비디오 전송 효율 향상에 유효함을 실증하며, 향후 ML/RL 기반 중요도 판단 모델로의 확장 가능성을 시사한다.

**주제어**: 콘텐츠 중요도, Cross-layer 적응 전송, MPR-QUIC, H.264 IPB, Late Frame Ratio, QoE

---

## ABSTRACT

This study proposes a cross-layer adaptive transport system that integrates H.264 frame importance evaluation (I/P/B) with QUIC transport-layer action selection within a unified policy framework. Unlike prior work that treats transport-layer optimization (e.g., TCP pacing, adaptive batching) and content-aware selective transmission as separate problems, the proposed approach dynamically assigns per-frame transport actions—RELIABLE, UNRELIABLE, DUPLICATE, or DROP—based on the computed importance score, deadline slack, and real-time network conditions. Through simulation experiments using public video datasets, the proposed single-path policy reduced the late frame ratio from 0.3267 (heuristic baseline) to 0.2071, achieving a 36.6% improvement. The multipath policy also demonstrated a 25.6% improvement (0.2431). These results confirm the effectiveness of frame-level action space design for latency-sensitive video transport and suggest a viable path toward ML/RL-based importance scoring in future work.

**Keywords**: Content-Aware Transport, Cross-Layer Adaptation, MPR-QUIC, H.264 IPB, Late Frame Ratio, QoE

---

## 1. 서론

실시간 비디오 스트리밍 서비스의 급속한 확산과 함께, 전송 품질에 대한 사용자 기대 수준은 지속적으로 높아지고 있다. 사용자 체감 품질(QoE)을 결정짓는 핵심 요인은 평균 지연 시간이 아니라, 재생 마감시간(playback deadline)을 초과한 프레임의 누적 비율이다. 한두 프레임의 과도한 지연만으로도 화면 끊김(stalling)이나 화질 저하가 사용자에게 직접적으로 인식되며, 이는 서비스 이탈률 증가로 이어질 수 있다[5].

특히 H.264/AVC 코덱에서 사용하는 IPB 프레임 구조는 프레임 간 종속성을 내포한다. I 프레임은 독립적으로 복호 가능한 기준 프레임으로서, 하나의 GOP(Group of Pictures)에서 I 프레임이 마감시간을 초과하면 해당 GOP 전체의 복호 가능성이 소실된다. 반면 B 프레임은 양방향 예측에 기반하므로 상대적으로 중요도가 낮으며, 지연 발생 시 시각적 영향이 제한적이다. 이러한 프레임 유형별 중요도 차이는 "모든 프레임을 동일하게 신뢰 전송하는 것이 최선인가"라는 근본적인 물음을 제기한다.

기존 전송 최적화 연구는 크게 두 축으로 발전해 왔다. 첫 번째 축은 전송 계층 자체의 지연 메커니즘 분석이다. Grazia et al.[2]은 TCP Pacing과 TCP Small Queues(TSQ)가 전송 지연 및 지터(jitter)에 미치는 영향을 실험적으로 규명하였으며, 이는 전송 큐 관리 및 flush 시점 결정의 이론적 토대를 제공한다. Borisov et al.[3]은 Little's Law에 기반한 종단 간(end-to-end) 성능 추정 기법을 제안하여, 정적 배칭(static batching)의 한계를 극복하는 적응적 배칭(adaptive batching)의 필요성을 입증하였다.

두 번째 축은 콘텐츠 특성에 기반한 선택적 전송이다. Tüker et al.[1]은 네트워크 엣지(edge)에서 H.264 SVC(Scalable Video Coding) 계층의 중요도에 따라 패킷을 선택적으로 축소(packet trimming)하는 기법을 제안하였다. 이 연구는 콘텐츠 중요도가 네트워크 효율성 향상에 기여할 수 있음을 보였으나, 전송 계층의 배칭, 패이싱, 경로 선택 등의 결정과 결합되지는 않았다.

두 축이 분리된 채 적용될 경우, 실제 서비스 환경에서의 최적화 기회를 놓치게 된다. 예를 들어, 네트워크가 혼잡한 상황에서 저중요 B 프레임에 신뢰 전송의 비용을 동일하게 부과하면, 전송 큐가 누적되어 고중요 I 프레임의 마감시간 초과 가능성이 오히려 증가할 수 있다. 이는 콘텐츠 중요도와 전송 계층 결정을 하나의 정책 안에서 동시에 고려하는 cross-layer 접근의 필요성을 시사한다.

본 연구는 이러한 연구 공백을 해소하기 위해, H.264 프레임 중요도를 전송 행동 결정에 직접 반영하는 cross-layer 적응 전송 시스템을 제안한다. 구체적으로 다음 세 가지를 중간보고의 목표로 설정한다. 첫째, 프레임 유형과 재생 마감시간을 고려한 중요도 평가 모듈(Stage A)과 행동 매핑 모듈(Stage B)로 구성된 2단 아키텍처를 설계한다. 둘째, 기준 정책(heuristic baseline)과 프레임 행동 기반 정책(frame action) 간의 성능 비교를 통해 cross-layer 접근의 유효성을 실증한다. 셋째, 단일경로와 다중경로 행동공간의 효과 차이를 분석하여 향후 연구 방향을 명확히 한다.

---

## 2. 관련 연구

### 2.1 콘텐츠 중요도 기반 선택적 전송

네트워크 자원이 제한된 환경에서 모든 데이터를 동일한 우선순위로 전송하는 것은 비효율적이다. Tüker et al.[1]은 네트워크 엣지의 가상 네트워크 기능(VNF)에서 BPP(Big Packet Protocol) 기반으로 H.264 SVC 패킷의 중요도를 판별하고, 중요도가 낮은 패킷을 선택적으로 축소(trimming)하는 기법을 제안하였다. 이 연구는 고정된 significance value를 사용하여 패킷 중요도를 결정하며, 네트워크 중간 노드(엣지)에서 동작한다는 특징이 있다.

본 연구는 Tüker et al.의 콘텐츠 중요도 활용이라는 관점을 계승하되, 세 가지 차이점을 갖는다. 첫째, 중요도 판단 단위를 BPP 청크(chunk)가 아닌 H.264 프레임(I/P/B)으로 설정한다. 둘째, 고정 값이 아닌 동적 스코어링(heuristic → ML → RL 단계별 고도화)을 적용한다. 셋째, 판단 위치를 네트워크 엣지가 아닌 송신측으로 이동하여, 전송 행동 결정과의 직접적 결합을 가능하게 한다.

### 2.2 전송 계층 지연 메커니즘

TCP 전송 계층에서 불필요한 지연이 발생하는 메커니즘에 대한 이해는 적응 전송 시스템 설계의 기초가 된다. Grazia et al.[2]은 Linux TCP 스택에서 TCP Pacing(TP)과 TCP Small Queues(TSQ)가 지연 시간 및 지터에 미치는 영향을 체계적으로 분석하였다. TSQ는 소켓 큐 길이를 제한하여 큐잉 지연을 억제하고, TP는 패킷 전송을 시간적으로 분산(pacing)시켜 버스트(burst)로 인한 혼잡을 완화한다. 이러한 분석은 본 연구의 시뮬레이터에서 `delayed_ack_ms`와 `nagle_penalty_factor` 파라미터로 근사되어, 배칭과 flush 시점 결정의 이론적 근거로 활용된다.

Borisov et al.[3]은 Redis 데이터베이스 환경에서 Little's Law 기반의 종단 간 성능 추정을 활용하여 Nagle 알고리즘을 동적으로 토글(toggle)하는 적응적 배칭 기법을 제안하였다. 이 연구에서는 처리량(throughput) 2배 향상과 지연 3배 개선을 달성하여, 정적 배칭 대비 적응적 배칭의 우위를 입증하였다. 본 연구의 시뮬레이션 환경에서는 `queue_bytes`와 `estimated_batch_gain` 변수를 통해 이러한 배칭 이득 추정 개념을 cross-layer 정책에 통합하였다.

### 2.3 다중경로 부분 신뢰 전송

Han et al.[4]은 QUIC 프로토콜에 다중경로(multipath)와 부분 신뢰(partial reliability) 전송을 결합한 MPR-QUIC(Multipath Partially Reliable QUIC)을 제안하였다. 이 연구는 경로 다양성(path diversity)을 활용하여 전송 신뢰성과 지연 사이의 균형을 유연하게 조정할 수 있는 가능성을 제시하였다. 본 연구는 MPR-QUIC의 행동공간(RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP)을 정책 설계에 반영하되, 중간보고 단계에서는 근사 시뮬레이션을 통해 각 행동의 효과를 사전 검증하는 접근을 취하였다.

### 2.4 학습 기반 적응 정책

Mao et al.[5]의 Pensieve는 심층 강화학습(Deep Reinforcement Learning)을 활용하여 적응적 비디오 스트리밍(Adaptive Bitrate, ABR)을 수행하는 시스템으로, 학습 기반 정책이 고전적 휴리스틱을 능가할 수 있음을 입증하였다. 본 연구는 Pensieve의 접근에서 영감을 받아, 중요도 판단 모듈을 heuristic에서 ML, 나아가 RL로 단계적으로 확장하는 로드맵을 설정하고 있다. 중간보고에서는 heuristic 기반의 1단계 성과를 제시하며, 이후 단계에서 학습 기반 고도화를 진행할 계획이다.

---

## 3. 연구 방법

### 3.1 시스템 아키텍처

제안 시스템은 프레임 중요도 평가(Stage A)와 전송 행동 결정(Stage B)으로 구성된 2단 파이프라인 구조를 따른다. Fig. 1은 전체 시스템의 처리 흐름을 나타낸다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    입력: H.264 비디오 스트림                          │
│              (프레임 유형, 크기, GOP 구조, 재생 마감시간)              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Stage A: 프레임 중요도 스코어링                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 입력: frame_type, payload_bytes, deadline_slack,              │  │
│  │       key_frame, GOP position, NetworkState                  │  │
│  │ 출력: importance_score (0.0 ~ 1.0)                           │  │
│  │ 구현: v1 Heuristic / v2 ML(예정) / v3 RL(예정)               │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ importance_score
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Stage B: 전송 행동 매핑                                 │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 입력: importance_score, deadline_slack_ms,                    │  │
│  │       NetworkState, available_paths                          │  │
│  │ 출력: FrameAction                                            │  │
│  │       {RELIABLE_SINGLE, RELIABLE_MULTI,                      │  │
│  │        UNRELIABLE, DUPLICATE, DROP}                          │  │
│  └───────────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ selected_action
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              전송 시뮬레이터 (core/simulator.py)                     │
│  경로별 RTT/BW/Loss 반영 → completion time 계산                     │
│  → late_frame_ratio, dropped_frame_ratio 등 지표 집계               │
└─────────────────────────────────────────────────────────────────────┘
```

> Fig. 1. 제안 시스템의 전체 처리 흐름


#### 3.1.1 Stage A: 프레임 중요도 스코어링

Stage A는 각 프레임에 대해 0.0에서 1.0 사이의 중요도 점수를 할당한다. 현재 구현된 v1 Heuristic 방식(`HeuristicImportanceScorer`)은 식 (1)과 같이 세 가지 요소를 가중 결합하여 점수를 산출한다.

```
importance_score = 0.45 × type_score + 0.40 × urgency + keyframe_bonus    ... (1)
```

여기서 `type_score`는 프레임 유형에 따른 기본 점수(I=1.0, P=0.6, B=0.2)이며, `urgency`는 재생 마감시간까지의 여유 시간에 반비례하는 긴급도(0.0~1.0)이다. `keyframe_bonus`는 키프레임 여부에 따라 0.15가 추가된다. 이러한 설계는 "프레임 유형이 비디오 복호에서 갖는 구조적 중요도"와 "마감시간까지의 시간적 여유"라는 두 가지 직교적 차원을 동시에 반영하기 위함이다.

향후 v2(ML 기반)에서는 13차원 특성 벡터(feature vector)를 입력으로 하는 학습 모델로 대체할 예정이다. 특성 벡터는 콘텐츠 관련 특성(프레임 유형 one-hot, 키프레임 여부, 페이로드 크기, 마감시간 여유)과 네트워크 상태 특성(RTT, 대역폭, 손실률, 버퍼 수준, 큐 바이트, 배칭 이득 추정값)을 포함하며, cross-layer 관점에서 Tüker[1]의 콘텐츠 특성과 Borisov[3]의 E2E 성능 추정 변수를 통합한다.

#### 3.1.2 Stage B: 전송 행동 매핑

Stage B는 Stage A에서 산출된 중요도 점수와 현재 네트워크 상태를 입력으로 받아, 다섯 가지 행동 중 하나를 선택한다. Table 1은 각 행동의 정의와 적용 조건을 요약한다.

> Table 1. 전송 행동 정의 및 적용 조건

| 행동 | 전송 방식 | 적용 조건 | 비고 |
|------|----------|----------|------|
| RELIABLE_SINGLE | QUIC Stream, 단일 경로 | 기본 행동; 중간 이상 중요도 | ACK 기반 신뢰 전송 |
| RELIABLE_MULTI | QUIC Stream, 다중 경로 | 높은 중요도 + 다중경로 가용 | 경로 분산으로 안정성 향상 |
| UNRELIABLE | QUIC DATAGRAM | 낮은 중요도 + 충분한 slack | ACK 미사용으로 지연 절감 |
| DUPLICATE | 다중 경로 중복 전송 | 매우 높은 중요도 + 다중경로 가용 | 최우선 보호 대상 |
| DROP | 전송 포기 | 마감시간 초과 + 낮은 중요도 | 자원 낭비 방지 |

행동 선택은 우선순위 규칙(priority rule)에 따르며, 현재 구현의 규칙 체계는 다음과 같다.

1. **마감시간 초과 + 낮은 중요도** → DROP: 이미 마감시간을 넘긴 저중요 프레임은 전송하더라도 재생에 기여하지 못하므로 전송을 포기하여 네트워크 자원을 절약한다.
2. **매우 높은 중요도 + 충분한 여유 + 다중경로 가용** → DUPLICATE: I 프레임과 같은 최고 중요 프레임은 다중 경로를 통해 중복 전송하여 도착 확률을 극대화한다.
3. **높은 중요도** → RELIABLE_MULTI 또는 RELIABLE_SINGLE: 고중요 프레임은 신뢰 전송 방식으로 보호하되, 다중경로가 가용하면 경로 분산을 시도한다.
4. **배칭 이득이 높고 중간 중요도** → RELIABLE_SINGLE(flush 유보): Borisov et al.[3]의 적응적 배칭 관점을 반영하여, 배칭 축적에 의한 처리량 향상이 예상되고 마감시간 여유가 충분한 경우 즉시 flush를 유보한다.
5. **충분한 여유 + 낮은 중요도** → UNRELIABLE: 시간적 여유가 있는 저중요 프레임은 ACK 없이 DATAGRAM으로 전송하여 전송 오버헤드를 최소화한다.
6. **기본값** → RELIABLE_SINGLE: 위 조건에 해당하지 않는 경우 안전한 단일 경로 신뢰 전송을 수행한다.

### 3.2 데이터셋 및 전처리

실험에 사용한 비디오 데이터셋은 공개 저장소에서 수집한 H.264 인코딩 영상들로 구성된다. 데이터셋의 재현성을 확보하기 위해 다음 두 가지 기법을 적용하였다.

첫째, 다중 URL 폴백(fallback) 메커니즘을 구현하였다. 공개 데이터셋의 URL이 변동되거나 접근 불가능해질 수 있으므로, 하나의 비디오에 대해 복수의 미러(mirror) URL을 등록하고 순차적으로 시도하도록 설계하였다. 둘째, MD5 해시 기반 중복 제거를 도입하였다. 서로 다른 URL에서 동일한 파일이 다운로드되는 경우를 감지하여, 분석 표본의 다양성을 보장하였다.

수집된 비디오는 FFprobe를 통해 프레임 단위 메타데이터를 추출하며, 프레임 유형(I/P/B), 페이로드 크기(bytes), 표시 시간(PTS), 키프레임 여부 등의 정보가 시뮬레이션 입력으로 변환된다. 추가로 `file_size_mb` 기준으로 small(≤1MB)과 medium(>1MB) 구간을 분류하여, 파일 크기별 정책 효과를 세분화 분석하였다.

### 3.3 비교 정책 설계

실험에서는 세 가지 정책을 동일한 데이터셋과 네트워크 조건 하에서 비교하였다. Table 2는 각 정책의 특성을 요약한다.

> Table 2. 비교 정책 요약

| 정책명 | 코드 매핑 | 행동공간 | 경로 수 | 특징 |
|--------|----------|---------|--------|------|
| heuristic_baseline | `heuristic_frame_aware` | Legacy (batch/flush 중심) | 1 | 프레임별 행동 선택 없음 |
| frame_action_single_path | `frame_action_adaptive` (paths=1) | RELIABLE_SINGLE, UNRELIABLE, DROP | 1 | 프레임별 행동 동적 선택 |
| frame_action_multipath | `frame_action_adaptive` (paths=2) | 전체 5종 행동 | 2 | 다중경로 + 중복/분산 전송 |

`heuristic_baseline`은 기존 방식과 동일하게 프레임 유형에 따른 배칭 및 flush 시점만을 조절하는 기준 정책이다. `frame_action_single_path`와 `frame_action_multipath`는 Stage A/B 파이프라인을 통해 프레임별 행동을 동적으로 결정하되, 가용 경로 수에 차이를 둔다.

### 3.4 시뮬레이션 환경

시뮬레이션 엔진(`core/simulator.py`)은 이벤트 기반(event-driven) 방식으로 프레임의 도착, 큐잉, 배칭, 전송, 완료 시각을 추적한다. 전송 완료 시각은 행동 유형에 따라 차별적으로 계산된다.

- **RELIABLE_SINGLE**: 단일 경로의 전송 시간 + 전파 지연 + ACK 패널티
- **RELIABLE_MULTI**: 경로별 대역폭 비율에 따라 페이로드를 분할 전송하고, 가장 느린 경로의 완료 시각을 전체 완료 시각으로 설정
- **DUPLICATE**: 상위 2개 경로에 전체 페이로드를 중복 전송하고, 먼저 도착하는 경로의 완료 시각을 채택
- **UNRELIABLE**: ACK 패널티를 제거하고 전파 지연을 0.35배로 축소하여, DATAGRAM 전송의 경량화 특성을 근사

다중경로 구성에서는 경로 이질성(heterogeneous path)을 반영하기 위해 경로별로 RTT 배수(0.7×, 1.0×, 1.6×), 대역폭 배수(0.65×, 1.0×, 1.5×), 손실률(1%, 2%, 5%)을 차등 적용하였다.

### 3.5 평가 지표

본 연구에서는 비디오 전송 품질을 다각적으로 평가하기 위해 Table 3의 지표들을 사용한다.

> Table 3. 평가 지표 정의

| 지표명 | 산출 방식 | 의미 |
|--------|----------|------|
| late_frame_ratio | 마감시간 초과 프레임 수 / 전체 프레임 수 | 전체 프레임 중 지연 위반 비율 (↓ 우수) |
| dropped_frame_ratio | 정책적 DROP 프레임 수 / 전체 프레임 수 | 의도적 전송 포기 비율 |
| partial_reliability_ratio | (UNRELIABLE + DROP 횟수) / 전체 행동 수 | 부분 신뢰 전송 활용 비율 |
| multipath_usage_ratio | RELIABLE_MULTI 횟수 / 전체 행동 수 | 다중경로 신뢰 전송 활용 비율 |
| redundancy_ratio | DUPLICATE 횟수 / 전체 행동 수 | 중복 전송 활용 비율 |

핵심 지표는 `late_frame_ratio`이며, 이 값이 낮을수록 재생 마감시간을 준수한 프레임 비율이 높아 QoE가 우수함을 의미한다.

---

## 4. 연구 결과

### 4.1 전체 평균 결과

시뮬레이션 결과(`midreport_transport_efficiency.csv`) 기준, 세 정책의 전체 평균 `late_frame_ratio`는 Table 4와 같다.

> Table 4. 정책별 전체 평균 late_frame_ratio

| 정책 | late_frame_ratio | baseline 대비 개선율 |
|------|:----------------:|:-------------------:|
| heuristic_baseline | 0.3267 | — |
| frame_action_multipath | 0.2431 | 25.6% |
| frame_action_single_path | 0.2071 | 36.6% |

`frame_action_*` 정책군은 기준 정책 대비 유의미한 개선을 달성하였다. 특히 `frame_action_single_path`는 가장 낮은 지연 위반 비율을 기록하여, 프레임별 행동 선택이 비디오 전송 효율 향상에 효과적임을 확인하였다.

### 4.2 파일 크기 구간별 결과

파일 크기에 따른 정책 효과를 분리 분석한 결과는 Table 5와 같다.

> Table 5. size_bin 구간별 late_frame_ratio

| 구간 | heuristic_baseline | frame_action_multipath | frame_action_single_path |
|------|:------------------:|:---------------------:|:------------------------:|
| medium | 0.4276 | 0.3485 | 0.3233 |
| small | 0.2090 | 0.1202 | 0.0714 |

모든 구간에서 frame action 기반 정책의 개선 경향이 일관적으로 관찰되었다. 특히 small 구간에서는 `frame_action_single_path`의 late_frame_ratio가 0.0714로, 기준 정책(0.2090) 대비 약 65.8%의 개선을 보였다. 이는 소규모 비디오에서 프레임별 행동 최적화의 효과가 더욱 현저함을 시사한다. Medium 구간에서도 개선이 확인되나, 프레임 수 증가에 따른 큐잉 복잡도 상승으로 인해 개선 폭이 상대적으로 축소되었다.

### 4.3 행동 분포 분석

프레임 행동 기반 정책의 행동 선택 패턴을 분석한 결과, 다음과 같은 특성이 관찰되었다.

**부분 신뢰 활용(partial_reliability_ratio)**: `frame_action_*` 정책에서 높은 부분 신뢰 활용 비율이 나타났다(medium 구간 약 0.8846, small 구간 약 0.9712). 이는 전체 프레임 중 상당수가 UNRELIABLE 또는 DROP으로 처리되었음을 의미하며, 저중요 프레임에 대한 자원 절약이 고중요 프레임의 마감시간 준수에 기여하고 있음을 시사한다.

**다중경로 활용(multipath_usage_ratio)**: `frame_action_single_path`에서는 경로가 1개이므로 값이 0이며, `frame_action_multipath`에서는 양수(medium 0.0135, small 0.0037)로 관찰되었다. 다중경로 전송이 실제로 활용되고 있음을 확인하였으나, 활용 빈도가 높지 않아 현재 설정에서의 체감 이득이 제한적이었다.

**중복 전송(redundancy_ratio)**: 현재 실험에서 DUPLICATE 행동은 거의 선택되지 않았다(값이 0에 근사). 이는 현재 시나리오에서 "매우 높은 중요도 + 충분한 slack + 다중경로 가용"이라는 세 조건의 동시 충족 빈도가 낮았기 때문으로 분석된다.

### 4.4 다중경로 효과의 제한성 분석

현 실험에서 `frame_action_multipath`가 `frame_action_single_path`보다 높은 late_frame_ratio를 보인 원인은 다음 두 가지로 분석된다.

첫째, 시뮬레이션 모델의 근사 수준이다. 현재 시뮬레이터는 경로별 RTT, 대역폭, 손실률을 경량 모델로 반영하나, 실제 QUIC 프로토콜 스택의 세밀한 메커니즘(경로별 독립 혼잡 제어, ACK 상호작용, reordering buffer, DATAGRAM 재전송 정책 등)을 완전히 재현하지는 않는다. 따라서 다중경로 전송의 잠재적 이득이 일부 시나리오에서 과소평가될 수 있다.

둘째, 경로 분할 전송의 구조적 특성이다. RELIABLE_MULTI 행동은 페이로드를 경로별 대역폭 비율에 따라 분할 전송하고 가장 느린 경로의 완료 시각을 전체 완료로 간주한다. 이질적 경로 구성(heterogeneous)에서 느린 경로(RTT 1.6×, 손실 5%)가 병목이 되어, 분할하지 않고 최적 단일 경로로 전송하는 것보다 완료 시각이 오히려 늘어날 수 있다.

이러한 결과는 "다중경로 전송이 무조건 유리하다"는 가정이 성립하지 않을 수 있음을 보여주며, 경로 특성에 따른 적응적 행동 선택의 정교화가 필요함을 시사한다. 이는 다중경로 전송의 무용론이 아니라, 프로토콜 수준 모델의 정교화와 경로 선택 전략의 개선이 선행되어야 함을 의미한다.

### 4.5 연구적 의의

본 중간보고의 실험 결과가 갖는 연구적 의의는 다음 세 가지로 요약된다.

첫째, **cross-layer 접근의 유효성 실증**이다. 프레임 중요도를 전송 행동 결정에 직접 반영하는 정책이 기준 정책 대비 late_frame_ratio를 유의미하게 개선하였다. 이는 콘텐츠 계층과 전송 계층의 정보를 통합 활용하는 교차 계층 설계가 실질적인 성능 향상으로 이어질 수 있음을 보여준다.

둘째, **부분 신뢰 전송의 실효성 확인**이다. 저중요 프레임에 UNRELIABLE이나 DROP 행동을 적용한 결과, 전체적인 마감시간 준수율이 향상되었다. 이는 "모든 프레임의 신뢰 전송"이라는 기존 관행에 대한 대안적 접근의 타당성을 뒷받침한다.

셋째, **후속 연구 방향의 명확화**이다. 다중경로 행동공간의 이득이 현재 근사 모델에서 제한적으로 나타난 점은, ML/RL 확장 단계에서 어떤 부분을 우선적으로 고도화해야 하는지에 대한 구체적 지침을 제공한다.

---

## 5. 결론

본 연구는 H.264 프레임 중요도(I/P/B)와 QUIC 전송 계층 행동을 결합한 cross-layer 적응 전송 시스템의 중간 성과를 제시하였다. 프레임별 중요도 평가(Stage A)와 전송 행동 매핑(Stage B)으로 구성된 2단 아키텍처를 설계하고, 세 가지 정책(`heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath`)을 동일 조건에서 비교 실험하였다.

실험 결과, `frame_action_single_path` 정책은 기준 정책 대비 late_frame_ratio를 36.6% 개선(0.3267 → 0.2071)하여, 프레임 단위 행동공간 설계의 유효성을 확인하였다. `frame_action_multipath` 정책도 25.6%의 개선을 보였으나, 근사 모델의 한계로 인해 다중경로의 잠재적 이점이 충분히 발현되지 않았다.

향후 연구는 세 단계로 진행할 계획이다. 단기적으로는 경로 상태 추정과 행동 선택의 결합을 정교화하고, 부분 신뢰 전송의 프로토콜 수준 모델을 개선하여 실제 MPR-QUIC 동작 특성을 더 정밀하게 반영한다. 중기적으로는 중요도 판단 모듈을 heuristic 기반에서 ML 기반(v2)으로 전환하여, 프레임 특성과 네트워크 상태를 동시에 학습하는 모델을 도입한다. 장기적으로는 RL 기반 정책 학습(v3)을 도입하여, QoE 보상 극대화를 목표로 하는 통합 최적화를 달성할 계획이다.

---

## 참고문헌

[1] Tüker, C., Szabo, G., & Metzger, F. (2024). Using packet trimming at the edge for in-network video quality adaption. *Peer-to-Peer Networking and Applications*, 17, 1484–1497.

[2] Grazia, C. A., Patriciello, N., & Klapez, M. (2021). On the Effect of TCP Pacing and TSQ on Latency and Jitter. *IEEE Access*, 9, 152633–152646.

[3] Borisov, N., Amit, I., & Tsafrir, D. (2025). Batching with End-to-End Performance Estimation. In *Proceedings of the 20th Workshop on Hot Topics in Operating Systems (HotOS '25)*.

[4] Han, B., Jiang, W., Feng, S., & Hausheer, D. (2024). MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport. In *Proceedings of the IEEE International Conference on Communications (ICC)*.

[5] Mao, H., Netravali, R., & Alizadeh, M. (2017). Neural Adaptive Video Streaming with Pensieve. In *Proceedings of ACM SIGCOMM*, 197–210.

---

\* 한국방송통신대학교 대학원 정보과학과 석사과정 (e-mail: pdc1024@knou.ac.kr)
