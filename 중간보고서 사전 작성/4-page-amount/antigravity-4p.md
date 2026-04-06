# 콘텐츠 중요도 기반 Cross-Layer 적응 전송에서의 MPR-QUIC 행동공간 분석

## Effectiveness of MPR-QUIC Action Space in Content-Aware Cross-Layer Adaptive Transport

박동찬*

## 요 약

실시간 비디오 전송에서 재생 마감시간(deadline)을 초과한 프레임 비율은 사용자 체감 품질(QoE)과 밀접하다. H.264 IPB 구조에서는 I 프레임 등 구조적으로 중요한 프레임의 지연이 GOP 단위 복호 실패로 확산될 수 있다. 본고는 선행연구에서 제시된 콘텐츠 중요도 활용[1], 전송 계층 지연·배칭 메커니즘 분석[2][3], MPR-QUIC의 부분 신뢰·다중경로 행동공간[4], 학습 기반 적응 전송의 방법론적 시사[5]를 개념적으로 차용하고, 이를 하나의 시뮬레이션 프레임워크에서 합성하여 문헌 기반 혼합 정책을 구성·비교한다. 구현 코드는 대부분 논문에 기재된 아이디어의 근사이며, 본 실험의 목적은 이러한 개념들을 혼합한 규칙 기반 정책이 기준 휴리스틱 대비 지연 위반 지표를 어떻게 변화시키는지를 정량적으로 관찰하는 데 있다. 공개 비디오 데이터에 대한 시뮬레이션에서 `frame_action_single_path`는 `heuristic_baseline` 대비 `late_frame_ratio`를 0.3267에서 0.2071로 낮추었고(약 36.6% 감소), `frame_action_multipath`는 0.2431(약 25.6% 감소)을 기록하였다. 파일 크기 구간별로도 일관된 개선 경향이 나타났으며, 부분 신뢰 행동의 비중은 높고 다중경로·중복 행동의 비중은 제한적으로 관찰되었다.

**주제어**: 콘텐츠 중요도, Cross-layer 적응 전송, MPR-QUIC, H.264 IPB, Late Frame Ratio, QUIC

## ABSTRACT

This paper examines a literature-based hybrid policy that combines content-aware frame scoring with QUIC-layer actions inspired by prior work on edge trimming [1], TCP pacing and queuing [2], adaptive batching via end-to-end estimation [3], multipath partial reliability (MPR-QUIC) [4], and learning-based adaptive streaming [5]. The implementation approximates published concepts in a unified simulator; the empirical question is how such a synthesized rule-based policy changes deadline violation metrics relative to a frame-aware heuristic baseline. On public video traces, `frame_action_single_path` reduced `late_frame_ratio` from 0.3267 to 0.2071 (about 36.6% reduction vs. baseline), and `frame_action_multipath` achieved 0.2431 (about 25.6% reduction). Stratified results by file size bin and auxiliary metrics (partial reliability, multipath usage, redundancy) are reported to interpret action mixtures.

**Keywords**: Content-Aware Transport, Cross-Layer Adaptation, MPR-QUIC, H.264 IPB, Late Frame Ratio, QUIC

---

## 1. 서론

실시간 스트리밍에서 QoE는 평균 처리량만으로 설명되기 어렵고, 재생 시점까지 도착하지 못한 프레임의 누적이 체감 품질을 좌우한다[5]. H.264/AVC의 IPB 구조에서 I 프레임은 독립 복호의 기준이 되며, P·B 프레임은 예측 의존성을 갖는다. 따라서 동일한 신뢰 전송·동일한 배칭 규칙을 모든 프레임에 적용하면, 저중요 프레임이 큐와 ACK 오버헤드를 점유하여 고중요 프레임의 마감시간 위험이 증가할 수 있다. 특히 GOP 경계에서 키프레임이 지연되면 이후 P·B 프레임의 복호 가능성이 함께 흔들리므로, 프레임 유형에 따른 전송 비용 차등화는 지연 민감 응용에서 실무적으로 의미가 있다.

전송 계층 연구는 큐잉·패이싱·배칭 결정이 지연과 지터에 미치는 영향을 다루어 왔다[2][3]. 콘텐츠 측면에서는 엣지에서의 패킷 trimming 등 중요도 기반 축소 전송이 논의되었다[1]. 다중경로와 부분 신뢰를 결합한 QUIC 확장(MPR-QUIC)은 행동공간을 넓혀 지연·신뢰성 트레이드오프를 조정할 여지를 제시한다[4]. 그러나 위 요소를 송신단 정책 하나로 묶어 프레임 단위로 실행 가능한지, 그리고 근사 시뮬레이션에서 어떤 지표 변화가 관찰되는지는 별도의 실증이 필요하다. 본고에서 말하는 정책은 새로운 프로토콜을 제안하는 것이 아니라, 문헌에 나타난 개념과 행동 집합을 코드 수준에서 합성한 문헌 기반 혼합 정책으로 이해해야 하며, 실측 스택과의 동일성을 가정하지 않는다.

본고의 목적은 (i) Stage A(중요도 산정)와 Stage B(전송 행동 매핑)를 경유하는 파이프라인을 명시하고, (ii) 기준 정책과 문헌 기반 혼합 정책을 동일 데이터·동일 네트워크 스위트에서 비교하며, (iii) 이질적 다중경로 설정에서 행동 혼합과 지표 간 관계를 기술하는 것이다. 결론은 효과의 일반적 보장이나 단일한 성능 우위 선언이 아니라, 주어진 근사 모델과 정책 규칙 하에서 관찰된 정량 결과와 해석적 함의를 제시하는 수준으로 한정한다.

비교의 공정성을 위해 동일한 프레임 메타데이터 입력과 동일한 네트워크 파라미터 스위트를 유지한 채 정책 구성만 바꾸었다. 기준 정책은 레거시 배칭·flush 규칙에 의존하고, 문헌 기반 혼합 정책은 Stage A/B를 통과한 뒤 행동별 완료 시각 근사로 이어진다. 따라서 관찰된 차이는 ‘동일 입력·동일 채널 모형’ 조건에서의 정책 효과로 읽는 것이 타당하며, 실제 운영망에서의 절대 성능 수치로 일반화하는 것은 본고의 범위를 넘어선다.

## 2. 관련 연구

### 2.1 콘텐츠 중요도와 선택적 전송

Tüker et al.[1]은 H.264 SVC 패킷의 중요도에 따라 엣지 VNF에서 선택적 trimming을 수행하였다. 이 접근은 네트워크 중간 지점에서 콘텐츠 중요도를 반영해 전송 부하를 줄일 수 있음을 보여 주었다. 본 연구는 동일한 ‘중요도 기반 전송 자원 배분’ 관점을 차용하되, 판단 위치를 송신측으로 두고 단위를 프레임으로 설정하며, 전송 행동(RELIABLE, UNRELIABLE 등)과 직접 연결한다는 점에서 실험 설정이 다르다. 엣지 trimming은 네트워크 내부에서 트래픽을 줄이는 반면, 본 시뮬레이션은 송신단에서 행동을 바꾸어 큐와 완료 시각 분포를 바꾸는 문제에 초점을 맞춘다.

### 2.2 전송 계층 지연·배칭

Grazia et al.[2]는 TCP Pacing과 TSQ가 지연·지터에 미치는 효과를 분석하였고, Borisov et al.[3]은 E2E 추정에 기반한 적응적 배칭을 제시하였다. 이들 연구는 전송 큐와 타이밍 결정의 원리를 밝히지만, 프레임 중요도와의 교차 계층 결합은 다루지 않는다. 본 시뮬레이터에서는 `delayed_ack_ms`, `nagle_penalty_factor`, `queue_bytes`, `estimated_batch_gain` 등의 변수를 통해 위 논의를 완전히 재현하기보다 개념적으로 반영하였다. 즉, Linux 커널의 세부 타이머 동작이나 실제 Nagle 토글 구현과 1:1 대응을 목표로 하지 않고, 배칭 이득과 지연 패널티의 상대적 크기를 조절할 수 있는 실험 노브로 취급한다.

### 2.3 MPR-QUIC 행동공간

Han et al.[4]의 MPR-QUIC은 QUIC 상에서 다중경로와 부분 신뢰를 결합하였고, 신뢰·비신뢰·중복·포기 등을 포함하는 행동공간을 제시하였다. 본고의 Stage B는 해당 행동 집합을 참고하여 다섯 가지 행동을 정의하였다. 시뮬레이션은 프로토콜 상태머신 전체를 구현한 것이 아니라, 행동별 완료 시각을 근사하는 이벤트 모델에 기반한다. 따라서 본고의 결과는 ‘MPR-QUIC의 표준 구현 성능’이 아니라, ‘문헌에 기술된 행동공간을 차용한 근사 모델에서의 상대 비교’로 이해해야 한다.

### 2.4 학습 기반 적응과 확장 로드맵

Mao et al.[5]의 Pensieve는 강화학습이 ABR에서 휴리스틱을 개선할 수 있음을 보였다. 본 연구의 현 단계는 식 (1)에 해당하는 휴리스틱 스코어링(v1)이며, 향후 v2에서는 13차원 특성 벡터를 입력으로 하는 ML 모델로 Stage A를 대체하고, v3에서는 QoE 보상을 명시한 RL 정책을 동일 파이프라인에 통합하는 것을 예정한다. Pensieve[5]가 ABR에서 보여 준 것처럼, 학습 기반 정책은 상태 표현과 보상 설계에 민감하므로, 본 파이프라인에서는 우선 규칙 기반으로 행동 분포와 지표의 대응 관계를 확보한 뒤 단계적으로 확장하는 전략을 취한다.

## 3. 연구 방법

### 3.1 시스템 구조 및 처리 흐름

시스템은 Fig. 1과 같이 Stage A(중요도 산정) → Stage B(행동 선택) → 전송 시뮬레이터의 순서로 동작한다. 입력은 H.264 프레임 메타데이터(유형, 크기, 마감시간 여유, 키프레임 여부 등)와 네트워크 상태 추정치이며, 출력은 프레임별 전송 행동과 완료 시각 분포이다.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Input: H.264 stream metadata (frame type, size, deadline, GOP)      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Stage A: Frame importance scoring                                   │
│  in: frame_type, payload_bytes, deadline_slack, key_frame, net state │
│  out: importance_score ∈ [0,1]  (v1 heuristic; v2 ML planned)        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ importance_score
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Stage B: Transport action mapping                                   │
│  in: importance_score, deadline_slack_ms, NetworkState, paths        │
│  out: {RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP}  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ selected_action
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Simulator: per-path RTT/BW/loss → completion time → metrics         │
└─────────────────────────────────────────────────────────────────────┘
```

**Fig. 1.** End-to-end pipeline from content-side scoring to transport simulation.

#### 3.1.1 Stage A: 프레임 중요도 스코어링

Stage A는 각 프레임에 대해 0.0에서 1.0 사이의 중요도 점수를 할당한다. 현재 구현된 v1 휴리스틱 스코어러는 식 (1)과 같이 유형 기반 점수, 마감시간 긴급도, 키프레임 보너스를 가중 결합한다.

```
importance_score = 0.45 × type_score + 0.40 × urgency + keyframe_bonus    ... (1)
```

`type_score`는 I/P/B에 따른 기본 중요도(I=1.0, P=0.6, B=0.2)이고, `urgency`는 마감시간까지의 여유에 반비례하는 0~1 값이며, `keyframe_bonus`는 키프레임일 때 0.15를 가산한다. 향후 v2(ML)에서는 프레임·네트워크·큐 상태를 포함하는 13차원 특성 벡터를 입력으로 하는 모델로 Stage A를 대체할 계획이다. 특성 예시는 프레임 유형 one-hot, 페이로드 크기, slack, RTT, 대역폭, 손실률, 버퍼 수준, 큐 바이트, 배칭 이득 추정값 등이며, Tüker[1]의 콘텐츠 특성과 Borisov[3]의 E2E 추정 변수를 cross-layer 관점에서 함께 담는 구성을 목표로 한다.

#### 3.1.2 Stage B: 전송 행동 매핑과 우선순위 규칙

Stage B는 Table 2에 요약된 다섯 행동 중 하나를 선택한다. 행동 정의 자체는 MPR-QUIC[4]에서 차용한 개념에 대응하되, 시뮬레이터 내부에서는 행동별 완료 시각 근사 규칙으로 구현된다.

**Table 2.** Definitions of transport actions (MPR-QUIC–inspired).

| Action | Transport mode | Role in this study |
|--------|----------------|--------------------|
| RELIABLE_SINGLE | QUIC Stream, single path | Default reliable delivery with ACK-related penalty |
| RELIABLE_MULTI | QUIC Stream, multipath | Payload split by bandwidth share; completion = slowest path |
| UNRELIABLE | QUIC DATAGRAM (approx.) | Reduced ACK penalty and shortened propagation factor |
| DUPLICATE | Multipath redundant | Full copy on two paths; completion = earliest finish |
| DROP | No send | Skip late, low-importance frames to save queue capacity |

행동 선택은 다음 **여섯 단계 우선순위**를 순서대로 적용한다. **1단계.** 마감시간이 이미 초과되었고 중요도가 낮은 경우 → `DROP`: 재생 기여가 기대되지 않는 저중요 프레임의 전송을 중단하여 큐 점유와 불필요한 재전송 부담을 줄인다. **2단계.** 중요도가 매우 높고 deadline slack이 충분하며 다중경로가 가용한 경우 → `DUPLICATE`: 최고 중요 프레임을 복수 경로에 중복 실어 도착 시점을 앞당길 여지를 둔다. **3단계.** 중요도가 높은 경우 → `RELIABLE_MULTI`(가능 시) 또는 `RELIABLE_SINGLE`: 신뢰 전송으로 보호하되 경로가 둘 이상이면 분할 전송을 허용한다. **4단계.** 배칭 이득이 크고 중요도가 중간인 경우 → `RELIABLE_SINGLE`을 유지하되 flush 유보: Borisov et al.[3]의 적응적 배칭 관점을 반영하여, 처리량 이득이 기대되고 slack이 허용할 때 즉시 flush를 미룬다. **5단계.** slack이 충분하고 중요도가 낮은 경우 → `UNRELIABLE`: DATAGRAM에 대응하는 경량 경로로 ACK 부담을 줄인다. **6단계.** 위 어느 조건에도 해당하지 않으면 → `RELIABLE_SINGLE`을 기본값으로 선택한다.

### 3.2 데이터 및 전처리

공개 H.264 클립을 수집하였다. URL 폴백은 미러 주소 순차 시도로 재현성을 보완하였고, MD5 해시 기반 중복 제거로 동일 파일의 중복 표본을 줄였다. FFprobe로 프레임 유형·크기·PTS·키프레임 정보를 추출하여 시뮬레이터 입력으로 변환하였다. `file_size_mb` 기준으로 small(≤1MB)과 medium(>1MB) 구간을 나누어 하위 집단별 `late_frame_ratio`와 보조 지표를 산출하였다.

### 3.3 비교 정책

`heuristic_baseline`은 프레임 인지형 배칭·flush 중심의 기준선으로, 프레임별 전송 행동을 명시적으로 선택하지 않는다. `frame_action_single_path`와 `frame_action_multipath`는 동일 Stage A/B 파이프라인을 사용하되 경로 수와 가용 행동 집합이 다르다. 단일 경로 설정에서는 구조적으로 `RELIABLE_MULTI`, `DUPLICATE`가 제한된다. 세 정책 모두 문헌에서 유래한 개념을 합성한 실험 조건으로 이해하며, 완성된 QUIC 구현체와의 동치를 주장하지 않는다.

### 3.4 시뮬레이션 환경과 경로 이질성

시뮬레이터는 이벤트 기반으로 큐잉·배칭·행동별 완료 시각을 추적한다. `RELIABLE_SINGLE`은 단일 경로 전송 시간에 전파 지연과 ACK 패널티를 더해 완료 시각을 산출한다. `RELIABLE_MULTI`는 경로별 대역폭 비율에 따라 페이로드를 분할하고 가장 늦게 끝난 경로의 완료 시각을 채택한다. `DUPLICATE`는 상위 두 경로에 전체 페이로드를 실어 더 빨리 완료된 경로 시각을 사용한다. `UNRELIABLE`은 ACK 패널티를 제거하고 전파 지연을 축소 계수로 곱하는 방식으로 근사한다.

다중경로 시나리오에서는 **경로 이질성(heterogeneous path)** 을 반영하기 위해 경로별로 RTT 배수 **0.7×, 1.0×, 1.6×**, 대역폭 배수 **0.65×, 1.0×, 1.5×**, 패킷 손실률 **1%, 2%, 5%** 를 조합하여 적용하였다. 이 설정은 한 경로가 상대적으로 느리거나 손실이 클 때 분할 전송이 병목을 키울 수 있는 조건을 포함한다.

### 3.5 평가 지표

Table 3은 본 실험에서 사용한 지표를 정의한다. 핵심 지표는 `late_frame_ratio`이며, 값이 낮을수록 마감시간 준수 비율이 높아 QoE 측면에서 유리한 방향으로 해석할 수 있다. `dropped_frame_ratio`는 정책이 의도적으로 포기한 프레임 비중을, `partial_reliability_ratio`는 UNRELIABLE과 DROP이 전체 행동에서 차지하는 비중을 각각 나타낸다. `multipath_usage_ratio`와 `redundancy_ratio`는 다중경로 신뢰 전송과 중복 전송이 실제로 얼마나 활성화되었는지를 요약하여, 지표 개선이 어떤 행동 혼합과 연관되는지 해석하는 데 도움이 된다.

### 3.6 실험의 한계

본 실험은 공개 클립과 합성 네트워크 조건에 의존하므로, 코덱·해상도·GOP 길이·실제 혼잡 제어 상호작용을 모두 포괄한다고 보기 어렵다. 또한 QUIC DATAGRAM과 다중경로 혼잡 제어의 세부 동작은 구현체마다 차이가 있어, 본 근사 모델이 특정 구현의 강점·약점을 반영하지 못할 수 있다. 이러한 한계는 결과를 ‘특정 시나리오에서의 경향’으로 읽어야 함을 뜻하며, 후속 연구에서 실측 트레이스와 프로토콜 수준 시뮬레이터를 병행하는 방향으로 완화할 수 있다.

### 3.5 평가 지표

Table 3은 본 실험에서 사용한 지표를 정의한다. 핵심 지표는 `late_frame_ratio`이며, 값이 낮을수록 마감시간 준수 비율이 높아 QoE 측면에서 유리한 방향으로 해석할 수 있다.

**Table 3.** Definitions of evaluation metrics.

| Metric | Definition | Interpretation |
|--------|------------|----------------|
| late_frame_ratio | (# frames past deadline) / (# all frames) | Lower is better for playback timeliness |
| dropped_frame_ratio | (# policy DROP) / (# all frames) | Intentional omission rate |
| partial_reliability_ratio | (# UNRELIABLE + # DROP) / (# actions) | Use of non-fully-reliable handling |
| multipath_usage_ratio | (# RELIABLE_MULTI) / (# actions) | Multi-path reliable usage |
| redundancy_ratio | (# DUPLICATE) / (# actions) | Duplicate transmission usage |

---

## 4. 연구 결과

전체 평균 `late_frame_ratio`는 Table 4와 같다. 문헌 기반 혼합 정책 `frame_action_single_path`가 0.2071로 가장 낮았고, `frame_action_multipath`는 0.2431이었다. 기준선 `heuristic_baseline`은 0.3267이다.

**Table 4.** Overall late_frame_ratio by policy.

| Policy | late_frame_ratio | Change vs. baseline |
|--------|-----------------:|--------------------:|
| heuristic_baseline | 0.3267 | — |
| frame_action_multipath | 0.2431 | ~25.6% reduction |
| frame_action_single_path | 0.2071 | ~36.6% reduction |

**Table 5.** late_frame_ratio by size_bin.

| size_bin | heuristic_baseline | frame_action_multipath | frame_action_single_path |
|----------|-------------------:|-------------------------:|-------------------------:|
| small | 0.2090 | 0.1202 | 0.0714 |
| medium | 0.4276 | 0.3485 | 0.3233 |

Table 5에서 small 구간은 기준선 0.2090 대비 `frame_action_single_path`가 0.0714로 하락하였고, medium 구간에서도 0.4276에서 0.3233으로 감소하였다. 파일 크기가 큰 medium 구간은 프레임 수와 큐잉 상호작용이 커져 개선 폭이 small보다 작게 나타나는 경향으로 읽을 수 있다.

보조 지표로, `partial_reliability_ratio`는 medium 구간에서 약 **0.8846**, small 구간에서 약 **0.9712**로 관찰되었다. `multipath_usage_ratio`는 multipath 조건에서 medium 약 **0.0135**, small 약 **0.0037**이었다. `redundancy_ratio`는 **0에 근사**하여 `DUPLICATE` 선택 빈도가 매우 낮았음을 뜻한다. `frame_action_multipath`가 `frame_action_single_path`보다 높은 `late_frame_ratio`를 보인 결과는, `RELIABLE_MULTI`가 느린 경로(예: RTT 1.6×, 손실 5%)에 병목을 만들거나, 근사 모델이 경로별 혼잡 제어·재정렬·ACK 상호작용을 모두 반영하지 못한 데 기인할 수 있다. 따라서 본 실험만으로 다중경로 행동의 이점을 전면적으로 판단하기는 어렵고, 모델 정밀도와 행동 조건의 재조정이 후속 과제로 남는다.

### 4.1 연구적 의의

첫째, **cross-layer 정보 결합의 정량적 관찰**이다. 동일 데이터와 네트워크 스위트에서 프레임 중요도와 전송 행동을 연동한 문헌 기반 혼합 정책이 기준 휴리스틱 대비 `late_frame_ratio`를 낮추는 경향이 확인되었다. 둘째, **부분 신뢰·전송 포기의 역할**이다. 높은 `partial_reliability_ratio`와 개선된 마감시간 준수는 저중요 프레임에 대한 오버헤드 절감이 전체 큐 압력 완화로 연결되었을 가능성을 시사한다. 셋째, **다중경로 행동의 실험적 조건 정교화 필요성**이다. 낮은 `multipath_usage_ratio`와 `redundancy_ratio`, 그리고 multipath 대 single_path의 관계는 향후 경로 선택 규칙, 시뮬레이터의 프로토콜 세부, v2/v3 학습 단계에서 우선적으로 다룰 과제를 정리해 준다.

## 5. 결론

본고는 선행연구[1]–[5]에서 제시된 개념을 시뮬레이션 코드로 근사·합성하여 문헌 기반 혼합 정책을 구성하고, 기준 정책과의 비교 실험을 보고하였다. 구현은 논문 아이디어의 합성이며, 본고의 범위는 주어진 근사 하에서 관찰된 수치와 행동 분포 해석에 머문다. `frame_action_single_path`는 `late_frame_ratio`를 0.3267에서 0.2071로 낮추었고, `frame_action_multipath`는 0.2431을 기록하였다. size_bin별로도 baseline 대비 수치가 낮아지는 패턴이 확인되었다. 향후 과제로는 시뮬레이터의 프로토콜 세부 반응을 보강하고, 식 (1) 대신 13차원 특성 기반 ML 스코어러(v2) 및 보상 설계가 명확한 RL 정책(v3)을 동일 파이프라인에 통합하는 실험이 이어질 수 있다.

---

## 참고문헌

[1] Tüker, C., Szabo, G., & Metzger, F. (2024). Peer-to-Peer Networking and Applications, 17, 1484–1497.

[2] Grazia, C. A., et al. (2021). IEEE Access, 9, 152633–152646.

[3] Borisov, N., et al. (2025). HotOS '25.

[4] Han, B., et al. (2024). MPR-QUIC. IEEE ICC.

[5] Mao, H., et al. (2017). Pensieve. ACM SIGCOMM, 197–210.

---

\* 한국방송통신대학교 대학원 정보과학과 (e-mail: pdc1024@knou.ac.kr)
