# 콘텐츠 중요도 기반 Cross-layer 적응 전송을 위한 프레임 단위 전송 행동 설계와 중간 구현 평가

## Frame-Level Transport Action Design and Mid-Term Implementation Evaluation for Content-Aware Cross-Layer Adaptive Transport

박동찬  
한국방송통신대학교 대학원 정보과학과

## 요약

본 연구는 H.264 비디오 프레임의 콘텐츠 중요도와 전송 계층의 행동 결정을 결합하는 cross-layer 적응 전송을 다룬다. 연구의 목적은 단순한 TCP batching 최적화가 아니라, 프레임 중요도와 deadline 여유를 함께 고려하여 신뢰 전송, 비신뢰 전송, 단일 경로, 다중 경로, 중복 전송, 드롭을 선택하는 정책을 설계하는 데 있다. 현재 구현은 frame trace 추출기, heuristic 기반 중요도 산정기, action-aware 시뮬레이터, 공개 데이터셋 기반 재현 가능한 노트북 분석으로 구성된다. 13개 공개 비디오에 대해 `heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath`를 비교한 결과, 전체 평균 `late_frame_ratio`는 각각 0.3267, 0.2071, 0.2431로 나타났다. 이는 프레임 단위 행동공간이 deadline 위반을 줄이는 데 효과적임을 보여준다. 반면 현재 단계의 multipath 이득은 제한적으로 나타났으며, 이는 multipath 개념의 부정이라기보다 경로 이질성 모델과 부분 신뢰 전송 효과를 더 정교하게 반영해야 함을 시사한다.

주제어: 콘텐츠 중요도, Cross-layer 적응 전송, 프레임 단위 스케줄링, MPR-QUIC, H.264, QoE

## ABSTRACT

This study investigates a content-aware cross-layer adaptive transport framework that combines H.264 frame importance with transport-layer action selection. The goal is not simple TCP batching optimization, but frame-level decision making over reliable or unreliable delivery, single-path or multipath routing, duplication, and dropping according to frame importance and deadline slack. The current implementation consists of a frame-trace extractor, a heuristic importance scorer, an action-aware simulator, and a reproducible notebook-based evaluation pipeline using public video datasets. We compared three policies, `heuristic_baseline`, `frame_action_single_path`, and `frame_action_multipath`, on 13 public videos. The mean `late_frame_ratio` values were 0.3267, 0.2071, and 0.2431, respectively. The results show that frame-level action selection is effective for reducing deadline violations. At the same time, the limited gain of the current multipath setting suggests the need for a more faithful model of path heterogeneity and partially reliable transport behavior.

Keywords: Content-Aware Transport, Cross-Layer Adaptation, Frame Scheduling, MPR-QUIC, H.264, QoE

## 1. 서론

실시간 비디오 전송에서 중요한 것은 평균 지연 자체보다 재생 마감시간을 넘긴 프레임이 얼마나 발생하는가이다. 특히 I 프레임이나 GOP 해석에 큰 영향을 주는 프레임이 늦게 도착하면, 일부 프레임의 손실이 연쇄적인 품질 저하로 이어질 수 있다. 따라서 모든 프레임을 동일한 방식으로 전송하는 접근은 지연 민감 비디오 환경에서 비효율적일 수 있다.

기존 연구는 크게 두 방향으로 발전해 왔다. 첫째는 TCP/QUIC 전송 계층에서 batching, pacing, queue 관리 등을 조정하여 지연을 줄이는 방향이다. 둘째는 콘텐츠 중요도에 따라 덜 중요한 데이터를 줄이거나 버리는 방향이다. 그러나 두 접근이 분리되어 있으면, 네트워크 상태가 나쁜 순간에 어떤 프레임을 보호하고 어떤 프레임을 가볍게 처리해야 하는지를 함께 결정하기 어렵다.

본 연구는 이러한 한계를 해결하기 위해 콘텐츠 중요도와 전송 행동을 한 정책 안에서 동시에 다루는 cross-layer 적응 전송을 목표로 한다. 핵심 질문은 다음과 같다. “프레임 단위 중요도 판단을 바탕으로 전송 행동공간을 설계하면, 동일한 네트워크 조건에서 late frame 비율을 낮출 수 있는가?” 현재 저장소 기준 구현은 이 질문을 검증하기 위한 중간 단계 프로토타입이며, 실제 QUIC 스택을 완전 구현한 단계는 아니다. 그 대신 프레임 trace 기반 시뮬레이터와 재현 가능한 공개 데이터셋 실험을 통해 연구 방향의 타당성을 점검한다.

## 2. 관련 연구와 연구 문제

### 2.1 콘텐츠 중요도 기반 전송 연구

Tüker et al.는 비디오 콘텐츠 중요도를 이용한 선택적 packet trimming 가능성을 제시하였다 [1]. 이 연구는 중요도가 낮은 데이터의 축소나 제거가 전체 품질과 네트워크 효율 개선에 기여할 수 있음을 보여주었다. 다만 전송 계층의 구체적 행동 선택과 직접 결합되지는 않았다.

### 2.2 전송 계층 지연 최적화 연구

Grazia et al.는 TCP pacing과 TCP Small Queues가 지연과 jitter에 미치는 영향을 분석하였다 [2]. 이는 batching과 queue 관리가 지연 성능에 실질적인 영향을 준다는 근거를 제공한다. Borisov et al.는 end-to-end 성능 추정을 바탕으로 adaptive batching 필요성을 제시하였다 [3]. 즉, 정적인 batch/flush 규칙보다 상태에 따라 batching을 바꾸는 접근이 더 적절하다는 점이 강조되었다.

### 2.3 본 연구의 위치

본 연구는 위 두 흐름을 분리하지 않고 연결한다. 콘텐츠 중요도는 Tüker의 문제의식에서, batching과 queue 관리는 Grazia 및 Borisov의 문제의식에서 출발한다. 그러나 본 연구의 관심은 단순 batching 자체가 아니라, “어떤 프레임을 어떤 전송 방식으로 보낼 것인가”를 프레임 단위로 결정하는 데 있다. 다시 말해, 본 연구는 콘텐츠 중요도 기반 적응 전송과 전송 계층 의사결정을 ML/RL로 통합할 수 있는 cross-layer 구조를 지향한다.

또한 학습 기반 적응 정책이 네트워크 의사결정에 실질적인 성능 개선을 줄 수 있다는 점은 Pensieve 계열 연구에서도 확인된 바 있다 [5]. 본 연구는 이러한 흐름을 비디오 bitrate 선택이 아니라 프레임 중요도 기반 전송 행동 선택으로 확장하려는 시도에 해당한다.

현재 구현 단계에서의 연구 문제는 다음 두 가지로 정리할 수 있다.

1. heuristic 기반 중요도 판단만으로도 프레임 단위 전송 행동이 성능 개선을 만들 수 있는가?
2. multipath 행동공간을 추가했을 때, 단일 경로보다 항상 유리한가, 아니면 조건에 따라 한계가 드러나는가?

## 3. 연구 설계 및 현재 구현

### 3.1 전체 파이프라인

현재 구현된 실험 파이프라인은 다음 순서로 구성된다.

1. `scripts/extract_video_trace.py`가 `ffprobe`를 사용해 프레임 단위 trace를 생성한다.
2. 각 프레임에 대해 `frame_type`, `payload_bytes`, `key_frame`, `gop_id`, `display_deadline_ms`를 구성한다.
3. `policy/importance.py`가 프레임 중요도를 산정한다.
4. `policy/action.py`가 중요도와 deadline slack, 네트워크 상태를 이용해 전송 행동을 선택한다.
5. `core/simulator.py`가 각 행동에 대한 완료 시각을 근사하고 QoE 지표를 계산한다.
6. `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`가 결과를 집계하고 CSV 및 그림을 생성한다.

이 구조는 응용 계층 정보와 전송 계층 상태를 하나의 정책 경로로 연결한다는 점에서 cross-layer 구조를 가진다.

### 3.2 프레임 trace 구성

프레임 trace는 H.264 비디오에서 `ffprobe`로 프레임 메타데이터를 추출해 생성한다. 각 프레임의 display deadline은 다음과 같이 구성된다.

`display_deadline_ms = pts_ms + duration_ms + playback_buffer_ms`

현재 노트북 실험에서는 `playback_buffer_ms=50.0` ms를 사용한다. 이 값은 프레임 단위 deadline 판단의 기준이 되며, 중요도와 별개로 시간적 긴급성을 측정하는 역할을 한다.

### 3.3 Stage A: 중요도 산정

현재 실험에서 사용한 중요도 산정은 heuristic 방식이다. `HeuristicImportanceScorer`는 프레임 타입, deadline urgency, keyframe 여부를 이용해 0과 1 사이의 score를 만든다. 구현식은 다음과 같다.

`ImportanceScore = clamp(0.45 × type_score + 0.40 × urgency + keyframe_bonus, 0, 1)`

여기서 `type_score`는 I=1.0, P=0.6, B=0.2이고, `keyframe_bonus`는 key frame일 때 0.15를 더한다. 즉, 현재 구현은 “I 프레임 우선 보호, B 프레임 상대적 완화”라는 직관을 deadline 정보와 함께 반영한다.

중요도 산정 코드에는 ML 모델 로딩을 수용하는 확장 경로가 일부 준비되어 있으나, 본 보고서의 실험은 heuristic 기반 정책 비교에 한정된다. 따라서 이번 결과는 “heuristic 중요도 + action-aware 전송”의 효과를 검증한 결과로 해석하는 것이 맞다.

### 3.4 Stage B: 전송 행동공간

현재 구현의 전송 행동공간은 다음 다섯 가지다.

| 행동 | 의미 |
| --- | --- |
| `RELIABLE_SINGLE` | 단일 경로 신뢰 전송 |
| `RELIABLE_MULTI` | 다중 경로 신뢰 전송 |
| `UNRELIABLE` | 비신뢰 전송 |
| `DUPLICATE` | 고중요 프레임 중복 전송 |
| `DROP` | deadline 초과가 예상되는 저중요 프레임 포기 |

행동 선택은 `policy/action.py`의 `select_action()`에서 수행되며, 핵심 규칙은 다음과 같다.

1. deadline을 이미 넘겼고 중요도가 낮으면 `DROP`
2. 중요도가 매우 높고 slack이 충분하며 경로가 2개 이상이면 `DUPLICATE`
3. 중요도가 높으면 `RELIABLE_MULTI` 또는 `RELIABLE_SINGLE`
4. 배칭 이득이 충분하고 중요도가 중간 수준이면 `RELIABLE_SINGLE`
5. slack이 충분하고 중요도가 낮으면 `UNRELIABLE`
6. 그 외에는 `RELIABLE_SINGLE`

이 규칙은 “중요한 프레임은 더 안전하게, 덜 중요한 프레임은 더 가볍게”라는 원칙을 구현한 것이다.

### 3.5 시뮬레이터와 전송 근사 모델

실험에 사용한 전송 설정은 `TransportConfig(rtt_ms=10, bandwidth_mbps=5, delayed_ack_ms=40)`이다. MSS는 1460 bytes, propagation factor는 0.5, Nagle penalty factor는 0.25로 설정된다.

행동별 완료 시각 근사는 다음과 같이 다르게 계산된다.

1. `RELIABLE_SINGLE`: 단일 경로의 전송 시간, propagation, ACK penalty를 반영
2. `UNRELIABLE`: ACK penalty를 제거하고 propagation 항을 축소
3. `RELIABLE_MULTI`: 여러 경로로 payload를 분할한 뒤 가장 늦게 끝나는 경로 완료 시각을 사용
4. `DUPLICATE`: 상위 2개 경로에 중복 전송하고 더 빨리 끝나는 완료 시각을 사용

즉, 현재 구현은 MPR-QUIC에서 기대하는 행동공간을 시뮬레이터 수준에서 근사한 것이다 [4]. 다만 실제 QUIC stack의 congestion control, ACK 상호작용, reordering buffer, retransmission 정책을 모두 반영한 것은 아니다. 이 점은 결과 해석에서 중요한 제한 조건이다.

### 3.6 비교 정책

실험에서는 다음 세 정책을 비교했다.

| 정책 | 설정 | 의미 |
| --- | --- | --- |
| `heuristic_baseline` | `PolicyConfig('heuristic_frame_aware')` | 프레임별 action selection 없이 queue/batch heuristics 중심으로 동작하는 기준 정책 |
| `frame_action_single_path` | `PolicyConfig('frame_action_adaptive', available_paths=1, path_profile='balanced')` | heuristic 중요도를 사용하되 단일 경로 action 공간만 허용 |
| `frame_action_multipath` | `PolicyConfig('frame_action_adaptive', available_paths=2, path_profile='heterogeneous')` | 동일한 중요도 기반 정책에 multipath action 공간을 추가 |

이 비교는 Stage A를 동일하게 두고 Stage B 행동공간 차이가 성능에 미치는 영향을 보는 데 목적이 있다.

### 3.7 데이터셋과 실험 프로토콜

노트북은 접속 안정성이 높은 공개 비디오 샘플만 선별하여 사용하며, 다운로드 실패를 대비해 fallback URL을 두고 MD5 기반 중복 제거를 수행한다. 실제 분석에 사용된 비디오는 총 13개이며, 그룹 구성은 animation 5개, movie 3개, nature 5개이다. 각 비디오는 file size 기준으로 `small(<10MB)`과 `medium(10~50MB)`로 구분되며, 이번 실험에서는 small 6개, medium 7개가 사용되었다.

총 실험 건수는 39건이다. 이는 13개 비디오에 3개 정책을 적용한 결과다.

## 4. 실험 결과 및 해석

### 4.1 콘텐츠 특성 요약

IPB 분포를 그룹별로 평균하면 표 1과 같다.

**표 1. 그룹별 프레임 구성 특성 요약**

| 그룹 | 비디오 수 | I 비율 | P 비율 | B 비율 | 평균 GOP 길이(frame) | 평균 payload(bytes) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| animation | 5 | 0.0466 | 0.7435 | 0.2099 | 45.0 | 4544.1 |
| movie | 3 | 0.0326 | 0.9674 | 0.0000 | 127.3 | 1901.8 |
| nature | 5 | 0.0052 | 0.2514 | 0.7434 | 234.2 | 20181.0 |

표 1에서 볼 수 있듯이 nature 그룹은 B 프레임 비중이 매우 높고 평균 payload도 크다. 반대로 movie 그룹은 거의 P 프레임 중심이며 payload가 작다. 따라서 본 실험에서는 nature 계열이 가장 어려운 시나리오, movie 계열이 가장 쉬운 시나리오로 작동한다.

### 4.2 정책별 전체 평균 성능

정책별 전체 평균 결과는 표 2와 같다.

**표 2. 정책별 전체 평균 성능**

| 정책 | late_frame_ratio | dropped_frame_ratio | useful_goodput_bytes | decodable_gop_ratio |
| --- | ---: | ---: | ---: | ---: |
| heuristic_baseline | 0.326676 | 0.000000 | 9,626,585 | 0.575028 |
| frame_action_single_path | 0.207061 | 0.108728 | 10,090,070 | 0.582021 |
| frame_action_multipath | 0.243119 | 0.108728 | 9,657,496 | 0.554226 |

가장 중요한 결과는 `late_frame_ratio`다. `frame_action_single_path`는 기준 정책 대비 약 36.62% 개선되었고, `frame_action_multipath`는 약 25.58% 개선되었다. 이는 현재 구현 수준에서도 프레임 단위 행동공간이 deadline 위반을 줄이는 데 실질적인 효과가 있음을 의미한다.

또한 `frame_action_single_path`는 useful goodput에서도 기준 정책보다 높은 값을 보였다. 즉, 저중요 프레임을 선택적으로 완화하거나 포기하더라도 전체적으로 “제때 도착해 실제로 의미 있는 데이터”는 오히려 더 늘어날 수 있음을 보여준다.

### 4.3 size_bin별 결과

비디오 크기 구간별 평균 결과는 표 3과 같다.

**표 3. size_bin별 late frame 비율**

| size_bin | 정책 | sample_count | late_frame_ratio_mean |
| --- | --- | ---: | ---: |
| medium | heuristic_baseline | 7 | 0.427557 |
| medium | frame_action_single_path | 7 | 0.323333 |
| medium | frame_action_multipath | 7 | 0.348504 |
| small | heuristic_baseline | 6 | 0.208982 |
| small | frame_action_single_path | 6 | 0.071411 |
| small | frame_action_multipath | 6 | 0.120170 |

medium 구간에서는 `frame_action_single_path`가 기준 정책 대비 약 24.38%, `frame_action_multipath`가 약 18.49% 개선되었다. small 구간에서는 `frame_action_single_path`가 약 65.83%, `frame_action_multipath`가 약 42.50% 개선되었다. 즉, 현재 구현에서는 작은 파일 구간에서 frame-aware action의 효과가 더 뚜렷하게 나타났다.

이는 small 구간의 경우 정책이 low-importance frame에 대해 더 공격적으로 비신뢰 전송 혹은 드롭을 적용하더라도 전체 deadline 관리가 상대적으로 쉬워, 보호가 필요한 frame에 자원을 집중하는 효과가 잘 드러났기 때문으로 해석할 수 있다.

### 4.4 그룹별 결과 해석

그룹 평균 `late_frame_ratio`를 보면 animation은 `0.043346 → 0.024604 → 0.031693`, movie는 세 정책 모두 0 근처, nature는 `0.806012 → 0.513755 → 0.600416`의 흐름을 보였다. 즉, 전체 평균의 차이는 사실상 nature 그룹의 난도가 좌우하고 있다.

nature 그룹에서 개선 폭이 크게 나타난 이유는 다음과 같다.

1. B 프레임 비중이 매우 높아 중요도 차등 적용 효과가 크다.
2. 평균 payload가 크기 때문에 동일한 전송 방식으로 모두 처리하면 queue 지연이 쉽게 누적된다.
3. GOP 길이가 길어 일부 프레임 지연이 연쇄적인 품질 악화로 이어질 가능성이 크다.

반대로 movie 그룹은 애초에 프레임 수가 적고 payload가 작아 세 정책 모두 충분히 deadline을 맞춘 것으로 해석할 수 있다. 이 결과는 “모든 콘텐츠에서 adaptive action이 동일하게 큰 이득을 주는 것은 아니며, 콘텐츠 구조가 복잡할수록 효과가 커진다”는 점을 보여준다.

### 4.5 부분 신뢰와 multipath 사용 패턴

size_bin 집계 결과에서 `partial_reliability_ratio_mean`은 medium 0.8846, small 0.9712로 나타났다. 이는 현재 action 정책이 상당수 프레임을 비신뢰 혹은 드롭 계열로 처리하고 있음을 의미한다. 그러나 이 선택은 무작위 손실이 아니라, 낮은 중요도 프레임을 덜 보호하고 높은 중요도 프레임의 deadline 충족 가능성을 높이기 위한 의도적인 자원 재배분이다.

한편 `multipath_usage_ratio_mean`은 medium 0.0135, small 0.0037로 매우 낮았다. `redundancy_ratio_mean`은 사실상 0이었다. 다시 말해, multipath 행동공간은 존재하지만 실제로 선택된 비율이 높지 않았고, 중복 전송은 거의 사용되지 않았다. 따라서 현재 단계에서 multipath의 기대 이득이 크게 나타나지 않은 것은 자연스러운 결과다.

### 4.6 왜 single-path가 multipath보다 더 좋게 나왔는가

현재 결과만 보면 `frame_action_single_path`가 `frame_action_multipath`보다 더 좋은 평균 성능을 보였다. 이 현상은 다음과 같은 구현적 이유로 설명할 수 있다.

첫째, 현재 multipath 모델은 `heterogeneous` path profile을 사용한다. 즉, RTT, bandwidth, loss가 다른 경로들을 근사적으로 섞어 사용한다. 이때 `RELIABLE_MULTI`의 완료 시각은 가장 늦게 끝나는 경로를 기준으로 계산되므로, 경로 이질성이 크면 기대만큼 이득이 나오지 않을 수 있다.

둘째, 실제 multipath QUIC에서는 경로별 혼잡제어와 재정렬 버퍼, ACK 상호작용, retransmission 정책이 성능에 큰 영향을 준다. 그러나 현재 시뮬레이터는 그 복잡한 동작을 모두 반영하지 않고, completion time 중심으로 경량 근사를 수행한다.

셋째, 현재 규칙 기반 정책에서 `DUPLICATE`가 거의 선택되지 않았기 때문에, multipath의 강점이 될 수 있는 고중요 프레임 보호 효과가 충분히 드러나지 않았다.

따라서 본 결과는 “multipath가 불필요하다”는 뜻이 아니다. 오히려 “현재 단계의 multipath 모델과 임계값 설계가 아직 거칠다”는 점을 보여주는 중간 결과로 해석하는 것이 타당하다.

## 5. 결론 및 향후 과제

본 연구는 콘텐츠 중요도 기반 cross-layer 적응 전송의 중간 구현을 정리하고, 프레임 단위 행동공간이 실제로 의미 있는 성능 개선을 만드는지 평가하였다. 현재 저장소 기준 구현은 frame trace 생성기, heuristic 중요도 산정기, action-aware 시뮬레이터, 공개 데이터셋 기반 재현 가능한 노트북으로 구성되어 있다.

실험 결과, `frame_action_single_path`와 `frame_action_multipath`는 모두 `heuristic_baseline`보다 낮은 `late_frame_ratio`를 보였다. 특히 `frame_action_single_path`는 전체 평균 기준 약 36.62%의 개선을 보이며 가장 안정적인 결과를 나타냈다. 이는 프레임 단위 중요도 판단과 전송 행동 선택을 결합하는 접근이 연구 방향으로서 충분한 타당성을 가진다는 점을 뒷받침한다.

동시에 현재 multipath 이득이 제한적이라는 점도 확인되었다. 이는 본 연구의 다음 과제를 명확히 한다.

1. 경로 이질성, loss, ACK 상호작용을 더 현실적으로 반영하는 multipath 모델 정교화
2. 현재 heuristic 기반 Stage A를 넘어 ML 기반 중요도 판단 실험 연결
3. 실제 QUIC 또는 에뮬레이션 환경과의 연동을 통한 시뮬레이터 검증
4. 장기적으로 heuristic → ML → RL 단계로 확장되는 중요도 판단 체계 완성

정리하면, 현재 구현은 아직 최종 시스템이 아니라 중간 단계의 연구 프로토타입이지만, 콘텐츠 중요도와 전송 행동을 결합한 cross-layer 적응 전송이라는 연구 방향이 실험적으로 유효하다는 점을 보여주었다. 향후에는 multipath와 부분 신뢰 전송의 모델 충실도를 높이고, 중요도 판단 방법론을 고도화함으로써 보다 설득력 있는 end-to-end 연구 결과로 발전시킬 수 있다.

## 참고문헌

[1] Tüker et al., “Using Packet Trimming at the Edge for In-Network Video Quality Adaption,” *Peer-to-Peer Networking and Applications*, 2024.

[2] Grazia et al., “On the Effect of TCP Pacing and TSQ on Latency and Jitter,” 2021.

[3] Borisov et al., “Batching with End-to-End Performance Estimation,” *HotOS*, 2025.

[4] Han et al., “MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport,” 2024.

[5] Mao et al., “Neural Adaptive Video Streaming with Pensieve,” *SIGCOMM*, 2017.
