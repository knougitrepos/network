# H.264 프레임 중요도 기반 Cross-layer 적응 전송 시스템의 설계 및 실험

## Design and Experiment of a Cross-layer Adaptive Transport System Based on H.264 Frame Importance

박 동 찬⁺ · 손 진 곤⁺⁺

Dongchan Park⁺ · Jin-Gon Son⁺⁺

## 요 약

본 연구는 실시간 비디오 전송에서 H.264 프레임의 콘텐츠 중요도를 전송 계층의 행동 결정에 직접 반영하는 cross-layer 적응 전송 시스템을 설계하고 실험하였다. H.264 코덱의 I, P, B 프레임은 복호 의존성과 페이로드 크기가 상이하므로, 동일한 전송 방식을 일괄 적용하면 고중요 프레임의 마감시간(deadline) 초과 위험이 증가한다. 이를 해결하기 위해 본 연구는 선행연구에서 제시된 콘텐츠 중요도 평가[1], 적응적 배칭[3], 부분 신뢰 전송 및 다중경로 행동 공간[5] 등의 개념을 차용·혼합하여 프레임별 중요도 점수를 산정하고, 이 점수와 재생 마감시간 여유, 네트워크 상태를 종합하여 신뢰 전송, 비신뢰 전송, 다중경로 전송, 중복 전송, 전송 포기 중 하나를 선택하는 정책을 구현하였다. 공개 비디오 데이터셋 13건에 대해 기준 정책(heuristic\_baseline)과 문헌 기반 혼합 정책(frame\_action\_single\_path, frame\_action\_multipath)을 비교한 결과, 혼합 정책은 마감시간 초과 프레임 비율(late\_frame\_ratio)을 기준 정책 대비 최대 36.6% 낮추었다. 이 결과는 선행연구의 전송 행동공간을 차용하고 콘텐츠 중요도와 결합하는 접근이 비디오 전송 품질 개선에 유효함을 보여준다.

주제어: 콘텐츠 중요도, H.264 IPB, Cross-layer 적응 전송, QUIC, 비디오 QoE

## ABSTRACT

This study designs and evaluates an adaptive transport system that determines per-frame transmission actions based on video frame importance. In H.264, I, P, and B frames differ in decoding dependency and size, making uniform transport inefficient. We adopt and combine concepts from prior work—content importance scoring[1], adaptive batching[3], and the partially reliable multipath action space of MPR-QUIC[5]—to compute an importance score for each frame and select among five transport actions: reliable single-path, reliable multi-path, unreliable (QUIC DATAGRAM), duplicate, and drop. Experiments on 13 public video clips show that the literature-based hybrid policies reduce the late frame ratio by up to 36.6% compared to the heuristic baseline. These results confirm the effectiveness of combining transport action spaces from prior work with content importance scoring for video delivery.

Keywords: Content-Aware Transport, H.264 IPB, Cross-Layer Adaptation, QUIC, Video QoE

---

## 1. 서 론

실시간 비디오 서비스에서 사용자 체감 품질(QoE)은 평균 전송 속도보다 '제때 도착한 프레임의 비율'에 더 크게 좌우된다[1]. H.264 코덱에서 I 프레임은 독립적으로 복호 가능한 기준 프레임이며, 하나의 I 프레임이 재생 마감시간(playback deadline)을 넘기면 해당 GOP(Group of Pictures) 전체의 복호가 불가능해져 화면 정지나 품질 저하로 직결된다. 반면 B 프레임은 양방향 예측에 기반하므로 지연 시 시각적 영향이 상대적으로 제한적이다. 이러한 프레임 유형별 중요도 차이는 "모든 프레임을 동일하게 신뢰 전송하는 것이 최선인가"라는 근본적 물음을 제기한다.

기존 전송 최적화 연구는 크게 두 갈래로 발전해 왔다. 하나는 전송 계층에서 큐 관리와 배치 크기를 조절하는 접근이다. Grazia et al.[2]은 TCP Pacing과 TSQ(TCP Small Queues)가 지연과 jitter에 미치는 영향을 분석하였고, Borisov et al.[3]은 Little의 법칙 기반 E2E 성능 추정으로 Nagle 알고리즘을 동적 토글하여 처리량을 2배 높인 사례를 보고하였다. 다른 하나는 콘텐츠 특성을 이용하는 접근이다. Tüker et al.[1]은 네트워크 엣지에서 패킷 중요도에 따라 선택적으로 trimming하는 방식을 제안하였다. 그러나 이 두 갈래는 대체로 독립적으로 적용되어 왔으며, 프레임 중요도와 전송 행동을 하나의 정책 안에서 통합한 연구는 아직 충분하지 않다.

본 연구는 이러한 배경에서 선행연구의 아이디어를 결합한 cross-layer 접근을 시도한다. H.264 프레임의 타입(I/P/B), 크기, 재생 마감시간 여유, 네트워크 RTT와 대역폭을 종합하여 중요도 점수를 산정하고, 이 점수에 따라 5가지 전송 행동 중 하나를 선택하는 정책을 설계하였다. 정책은 현재 규칙 기반(heuristic)으로 동작하며, 이후 머신러닝(ML) 및 강화학습(RL)으로 확장할 수 있는 구조를 갖추고 있다. Mao et al.[4]의 Pensieve가 적응형 비트레이트(ABR) 문제에서 RL의 실효성을 입증한 것처럼, 프레임 수준 전송 행동 결정에도 학습 기반 정책의 적용이 기대된다.

## 2. 관련 연구

### 2.1 콘텐츠 중요도 기반 전송

Tüker et al.[1]은 H.264 SVC(Scalable Video Coding) 환경에서 패킷에 부여된 중요도 값을 기준으로 네트워크 엣지의 VNF에서 불필요한 부분을 잘라내는 packet trimming 기법을 제안하였다. 이 연구는 '중요하지 않은 데이터를 줄이면 전체 품질이 향상될 수 있다'는 통찰을 제공하지만, 중요도가 인코딩 시점에 고정되며 전송 계층 상태를 반영하지 않는다는 한계가 있다. 본 연구는 이 아이디어를 차용하여 중요도를 동적 점수로 산정하고 전송 행동에 직접 연결하는 방식으로 확장하였다.

### 2.2 전송 계층 지연 제어

Grazia et al.[2]은 TCP Pacing이 버스트를 평탄화하고 TSQ가 소켓 큐 길이를 제한함으로써 지연이 줄어드는 메커니즘을 정량 분석하였다. Borisov et al.[3]은 애플리케이션 수준에서 E2E 성능을 추정하여 배칭 여부를 동적 결정하는 방식을 제안하였다. 이 연구들은 '전송할 데이터가 무엇인지'를 고려하지 않고 큐와 타이밍만 제어한다는 공통 한계를 갖는다. 본 연구는 이러한 전송 계층 제어 기법을 차용하면서 콘텐츠 중요도 축을 추가로 결합하여 혼합 정책을 실험한다.

### 2.3 MPR-QUIC와 학습 기반 정책

Han et al.[5]은 QUIC 위에서 부분 신뢰 전송(Partially Reliable)과 다중경로(Multipath)를 결합한 MPR-QUIC 구조를 제안하였다. 본 연구는 MPR-QUIC에서 제시한 행동 공간(신뢰/비신뢰, 단일/다중경로)을 차용하여 정책 시뮬레이션에 반영하고, 이 행동 공간이 콘텐츠 중요도와 결합될 때 실제 지표 개선으로 이어지는지를 실험적으로 확인한다. Mao et al.[4]의 Pensieve는 RL 정책이 ABR에서 전문가 규칙을 능가할 수 있음을 증명하였으며, 본 연구는 프레임 수준 전송 행동에 유사한 학습 접근을 적용할 계획이다.

## 3. 연구 방법

### 3.1 시스템 구조

시스템은 두 단계(Stage A, Stage B)로 구성된다. Stage A(중요도 산정)는 각 프레임의 타입(I/P/B), 페이로드 크기, 재생 마감시간까지의 여유(deadline slack), GOP 내 위치, 네트워크 RTT와 대역폭을 입력으로 받아 0.0~1.0 사이의 중요도 점수를 출력한다. I 프레임과 키프레임에는 높은 가중치가 부여되고, 마감시간이 임박할수록 점수가 상승한다. 현재는 규칙 기반(HeuristicImportanceScorer)으로 동작하며 향후 ML/RL 기반 스코어러로 교체할 수 있는 인터페이스를 갖추고 있다.

Stage B(행동 선택)는 Stage A의 중요도 점수와 deadline slack, 네트워크 상태, 사용 가능 경로 수를 입력으로 받아 Table 1의 다섯 가지 전송 행동 중 하나를 선택한다.

#### Table 1. Transmission actions and their meanings

| Action | Description |
| --- | --- |
| RELIABLE\_SINGLE | QUIC Stream으로 단일 경로 신뢰 전송 |
| RELIABLE\_MULTI | QUIC Stream으로 다중경로 신뢰 전송 |
| UNRELIABLE | QUIC DATAGRAM으로 비신뢰 전송(ACK 불필요) |
| DUPLICATE | 고중요 프레임을 복수 경로로 중복 전송 |
| DROP | 마감시간 초과가 확실한 저중요 프레임의 전송 포기 |

### 3.2 행동 선택 규칙

행동 선택 함수는 다음 우선순위로 동작한다. (1) 마감시간이 이미 초과되었고 중요도가 낮으면(score < 0.30) DROP한다. (2) 중요도가 매우 높고(score >= 0.75) deadline 여유가 충분하며 다중경로가 가능하면 DUPLICATE한다. (3) 중요도가 높으면 RELIABLE\_MULTI(가능 시) 또는 RELIABLE\_SINGLE을 선택한다. (4) 배칭 이득이 15% 이상이고 중간 중요도이면 flush를 유보한다. (5) deadline 여유가 RTT의 2배 이상이고 중요도가 낮으면 UNRELIABLE을 선택한다. (6) 위 조건에 해당하지 않으면 RELIABLE\_SINGLE을 선택한다. 이 규칙은 Tüker[1]의 콘텐츠 중요도 개념과 Borisov[3]의 배칭 이득 개념을 차용하여 하나의 의사결정 함수로 혼합 구성한 것이다.

### 3.3 비교 정책

실험에서 사용한 세 가지 정책은 Table 2와 같다.

#### Table 2. Compared policies

| Policy Label | Actions Used | Paths |
| --- | --- | --- |
| heuristic\_baseline | Legacy batch/flush만 사용 | 1 |
| frame\_action\_single\_path | RELIABLE\_SINGLE, UNRELIABLE, DROP | 1 |
| frame\_action\_multipath | 전체 5개 행동 | 2 |

heuristic\_baseline은 프레임 타입에 따라 배치 크기와 flush 간격만 조절하는 정책으로, 프레임별 전송 행동을 명시적으로 선택하지 않는다. 이에 반해 frame\_action\_\* 정책은 선행연구[1][3][5]의 아이디어를 혼합하여 매 프레임마다 Stage A → Stage B를 거쳐 행동을 동적으로 결정한다.

### 3.4 데이터셋 및 평가 지표

공개 비디오 소스에서 다양한 해상도(360p~1080p)와 비트레이트의 H.264 인코딩 파일을 수집하였다. 파일당 복수의 fallback URL을 구성하였고, MD5 해시를 이용해 중복을 제거하여 최종 13개의 고유 비디오를 사용하였다. 파일 크기 기준으로 small(5MB 미만)과 medium(5MB 이상) 구간으로 분류하여 구간별 정책 효과를 분리 관찰하였다.

핵심 지표는 late\_frame\_ratio로, 전체 프레임 중 재생 마감시간을 넘긴 프레임의 비율이다. 보조 지표로 dropped\_frame\_ratio(전송 포기 비율), partial\_reliability\_ratio(비신뢰 또는 포기 행동의 비율), multipath\_usage\_ratio(다중경로 행동의 비율)를 함께 관찰하였다.

## 4. 연구 결과

### 4.1 전체 평균 결과

13개 비디오에 대한 정책별 평균 late\_frame\_ratio는 Table 3과 같다.

#### Table 3. Mean late\_frame\_ratio by policy

| Policy | late\_frame\_ratio | dropped\_frame\_ratio |
| --- | --- | --- |
| heuristic\_baseline | 0.3267 | 0.0000 |
| frame\_action\_multipath | 0.2431 | 0.1087 |
| frame\_action\_single\_path | 0.2071 | 0.1087 |

frame\_action\_single\_path는 baseline 대비 late\_frame\_ratio를 약 36.6% 낮추었고, frame\_action\_multipath는 약 25.6% 낮추었다. 두 정책 모두 약 10.9%의 프레임을 DROP 처리하였는데, 이는 마감시간 초과가 확실한 저중요 프레임을 포기함으로써 나머지 프레임의 전송 기회를 확보한 결과로 해석된다.

### 4.2 파일 크기 구간별 결과

#### Table 4. Late\_frame\_ratio by size\_bin and policy

| size\_bin | heuristic\_baseline | frame\_action\_multipath | frame\_action\_single\_path |
| --- | --- | --- | --- |
| small | 0.2090 | 0.1202 | 0.0714 |
| medium | 0.4276 | 0.3485 | 0.3233 |

small 구간에서 frame\_action\_single\_path는 baseline 대비 약 65.8%의 개선을 보였으며, medium 구간에서도 약 24.4%의 개선을 보였다. 모든 구간에서 혼합 정책이 baseline보다 우수한 수치를 보였으며, 파일 크기가 작을수록 개선 폭이 더 컸다.

### 4.3 행동 사용 패턴 분석

frame\_action\_\* 정책의 partial\_reliability\_ratio는 medium 구간 약 0.885, small 구간 약 0.971로 나타났다. 이는 대부분의 프레임이 비신뢰 전송 또는 포기로 처리되었음을 의미하며, 소수의 고중요 프레임만 신뢰 전송으로 보호하는 전략이 작동하고 있음을 확인할 수 있다. multipath\_usage\_ratio는 frame\_action\_multipath에서 medium 0.0135, small 0.0037로, 다중경로 행동이 선택되기는 했으나 빈도가 높지 않았다. redundancy\_ratio(DUPLICATE 비율)는 0에 가까웠으며, 이는 현재 시뮬레이션 환경에서 DUPLICATE가 필요한 극단적 고위험 상태가 충분히 발생하지 않았음을 시사한다.

### 4.4 Multipath 이득의 한계와 해석

Table 3에서 frame\_action\_multipath의 late\_frame\_ratio(0.2431)가 frame\_action\_single\_path(0.2071)보다 오히려 높게 나타났다. 이는 두 가지 원인으로 설명된다. 첫째, 현재 시뮬레이터의 다중경로 모델은 경량 근사로, 실제 QUIC 스택의 세밀한 동작(경로별 혼잡 윈도우, ACK 상호작용, reorder buffer 영향)을 포함하지 않는다. 둘째, 다중경로 분할 전송(RELIABLE\_MULTI)은 모든 경로가 완료되어야 프레임이 사용 가능하므로 가장 느린 경로가 병목이 되며, 이질적 경로 환경에서 이 병목 효과가 단일경로 대비 불리하게 작용한다.

따라서 본 결과는 "다중경로가 무용하다"는 결론이 아니라, "현 근사 모델에서 다중경로의 이점을 충분히 재현하지 못한다"는 의미이며, 프로토콜 수준 모델의 정교화가 필요하다는 과제를 식별한 것으로 해석하는 것이 타당하다.

## 5. 결론 및 향후 과제

본 연구에서는 선행연구에서 제시된 콘텐츠 중요도, 전송 행동 공간, 배칭 이득 등의 개념을 차용·혼합하여 cross-layer 적응 전송 시스템을 구성하고, 세 가지 정책의 성능을 비교 실험하였다. 실험 결과, 문헌 기반 혼합 정책(frame\_action\_single\_path)은 기준 정책 대비 마감시간 초과 비율을 최대 약 36.6% 낮추었다. 이는 기존 연구의 아이디어들을 결합하는 접근이 비디오 전송 품질 개선에 유효할 수 있음을 시사한다.

그러나 현 단계에는 다음과 같은 한계가 존재한다. 첫째, 다중경로 모델이 경량 근사 수준에 머물러 있어 multipath의 이점이 충분히 나타나지 않았다. 둘째, 중요도 산정이 규칙 기반으로만 이루어져 다양한 비디오 특성에 대한 적응력이 제한적이다. 셋째, 실험 데이터셋의 해상도 범위가 360p~1080p로 한정되어 2K/4K 환경에서의 일반화 검증이 필요하다.

향후 연구에서는 세 방향으로 확장할 계획이다. 첫째, 경로별 상태 추정(E2E delay, loss, jitter)을 정교화하여 다중경로 전송의 실효적 이점을 재현한다. 둘째, ML 기반 중요도 스코어러를 도입하여 규칙 기반 대비 QoE 개선 폭을 비교한다. 셋째, RL 기반 정책 학습을 도입하여 전송 행동 결정의 최적화를 시도하며, Pensieve[4]가 ABR에서 보인 것과 유사한 학습 효과가 프레임 수준 전송에서도 나타나는지를 검증한다. 이를 통해 "콘텐츠 중요도 → 전송 행동" 결합 방식의 실효성을 보다 엄밀하게 검증할 계획이다.

---

## 참고문헌

[ 1 ] Tüker, D., Rizk, A., & Zink, M. (2024). Using Packet Trimming at the Edge for In-Network Video Quality Adaption. *Peer-to-Peer Networking and Applications*, 17, 1097–1114.

[ 2 ] Grazia, C. A., Patriciello, N., Klapez, M., & Casoni, M. (2021). The New TCP Modules on the Block: TCP Pacing & TCP Small Queues. *IEEE Access*, 9, 100429–100440.

[ 3 ] Borisov, N., Amit, N., & Tsafrir, D. (2025). Batching with End-to-End Performance Estimation. *Proceedings of the Workshop on Hot Topics in Operating Systems (HotOS '25)*.

[ 4 ] Mao, H., Netravali, R., & Alizadeh, M. (2017). Neural Adaptive Video Streaming with Pensieve. *Proceedings of ACM SIGCOMM*, 197–210.

[ 5 ] Han, B., Feng, L., & Shen, G. (2024). MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport.

---

⁺ 한국방송통신대학교 대학원 정보과학과
⁺⁺ 한국방송통신대학교 대학원 정보과학과 교수
