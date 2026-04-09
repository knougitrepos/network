# 콘텐츠 중요도 기반 Cross-layer 적응 전송을 위한 프레임 단위 전송 행동 설계 및 중간 구현 평가

## Design and Mid-Term Evaluation of Frame-Level Transport Actions for Content-Aware Cross-Layer Adaptive Transport

박동찬  
Dongchan Park  
한국방송통신대학교 대학원 정보과학과  
Graduate School of Information Science, Korea National Open University

## 요 약

실시간 비디오 전송에서는 모든 프레임을 동일한 방식으로 전송할 경우, 중요도가 높은 I/P 프레임의 재생 마감시간 위반이 증가하고 GOP 전체 복호 품질이 함께 저하될 수 있다. 본 연구는 이 문제를 해결하기 위해 H.264 프레임 중요도와 전송 계층 행동을 함께 결정하는 cross-layer 적응 전송 구조를 설계하고, 현재 구현된 시뮬레이터 기반 성능을 평가하였다. 구현은 Stage A의 중요도 산정과 Stage B의 전송 행동 선택으로 구성되며, 13개 공개 비디오 트레이스에서 `heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath`를 비교하였다. 실험 결과 전체 평균 `late_frame_ratio`는 각각 0.3267, 0.2071, 0.2431로 나타나 프레임 행동 선택 기반 정책이 기준 정책보다 deadline 준수에 유리함을 확인하였다. 이는 콘텐츠 중요도 기반 전송 행동 설계가 실시간 비디오 QoE 개선에 유효함을 시사한다.

주제어: 콘텐츠 중요도, cross-layer 적응 전송, H.264 IPB, QUIC, deadline-aware 전송, 비디오 QoE

## ABSTRACT

In real-time video delivery, treating all frames identically can increase deadline misses for important frames and degrade GOP-level decodability. This study addresses that problem by designing a cross-layer adaptive transport structure that jointly considers H.264 frame importance and transport actions. The current implementation consists of Stage A for importance scoring and Stage B for action selection, and compares `heuristic_baseline`, `frame_action_single_path`, and `frame_action_multipath` on 13 public video traces. The mean `late_frame_ratio` values were 0.3267, 0.2071, and 0.2431, respectively, showing that action-aware policies improve playback deadline compliance over the baseline. The result suggests that content-aware transport action design is effective for improving real-time video QoE.

Keywords: content-aware transport, cross-layer adaptation, H.264 IPB, QUIC, deadline-aware transmission, video QoE

## 1. 서론

실시간 비디오 전송에서 중요한 것은 단순 평균 지연이 아니라, 재생 시점까지 제시간에 도착한 프레임의 비율이다. H.264/AVC는 I, P, B 프레임이 서로 다른 복호 의존성을 가지므로, 같은 양의 지연이라도 어떤 프레임에서 발생했는지에 따라 사용자 체감 품질의 영향이 달라진다[1]. 특히 I 프레임이나 이를 기준으로 복호되는 중요한 프레임이 늦게 도착하면 해당 프레임 하나의 손실에 그치지 않고 GOP 전체 재생 품질 저하로 이어질 수 있다. 반대로 중요도가 낮은 프레임까지 동일한 수준의 신뢰성과 전송 비용을 부여하면, 제한된 전송 자원이 정말 중요한 프레임에 충분히 배분되지 못하는 문제가 생긴다.

이 점이 본 연구가 해결하려는 문제이다. 기존 네트워크 최적화 연구는 주로 전송 계층의 배칭, 큐잉, flush 시점, pacing과 같은 메커니즘에 집중해 왔고[3][4], 콘텐츠 기반 연구는 영상 자체의 중요도를 반영한 선택적 처리에 집중해 왔다[2]. 그러나 실제 실시간 비디오 서비스에서는 콘텐츠 중요도와 네트워크 상태가 동시에 작용한다. 따라서 "무엇이 중요한 프레임인가"와 "그 프레임을 어떤 전송 방식으로 보낼 것인가"를 분리해서 다루면, 중요한 프레임이 왜 늦어지는지와 그것을 어떻게 줄일지를 한 정책 안에서 설명하기 어렵다.

본 연구는 단순 TCP batching 최적화가 아니라, 콘텐츠 중요도와 전송 계층 결정을 함께 다루는 cross-layer 적응 전송 연구이다. 현재 단계의 목표는 H.264 프레임 중요도를 기반으로 프레임 단위 전송 행동을 선택하는 구조를 설계하고, 그 구조가 기준 정책보다 deadline miss를 줄일 수 있는지를 시뮬레이터 수준에서 검증하는 것이다. 이를 위해 저장소의 현재 구현인 `policy/importance.py`, `policy/action.py`, `core/simulator.py`, 그리고 중간보고 노트북 `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`를 기준으로 연구 진행 상황을 정리하였다.

본 중간보고의 기여는 다음과 같다. 첫째, 프레임 중요도 산정(Stage A)과 전송 행동 선택(Stage B)을 분리한 2단 구조를 제시하였다. 둘째, 공개 비디오 트레이스 13개에 대해 기준 정책과 행동 선택 기반 정책을 동일한 조건에서 비교하였다. 셋째, 현재 구현이 어디까지 검증되었고, 어떤 부분이 아직 시뮬레이터 수준에 머물러 있는지를 함께 기술하여 후속 연구 방향을 명확히 하였다.

## 2. 관련 연구

Tüker 등[2]은 영상 콘텐츠 중요도를 이용한 선택적 전송 처리 가능성을 제시하였다. 이 연구는 모든 영상 데이터를 동일하게 다루지 않고, 중요도가 낮은 데이터는 줄이거나 제거하여 QoE를 유지할 수 있음을 보여준다. 본 연구는 이러한 콘텐츠 중요도 관점을 받아들이되, 판단 위치를 송신 측으로 옮기고 프레임 단위 행동 결정과 직접 연결한다는 점에서 차이가 있다.

Grazia 등[3]과 Borisov 등[4]은 전송 계층에서 지연과 처리량이 배칭, pacing, 큐 길이와 긴밀히 연결되어 있음을 보여주었다. 즉, 언제 모아서 보내고 언제 즉시 flush할지의 결정은 지연 성능에 직접적인 영향을 준다. 다만 이들 연구는 전송할 데이터의 내용적 중요도까지는 반영하지 않는다. 본 연구는 이 한계를 보완하기 위해 콘텐츠 중요도와 배칭 관련 상태를 함께 고려하는 구조를 설계하였다.

QUIC 기반 부분 신뢰 전송과 다중경로 전송에 대해서는 RFC 9221[5]과 Han 등[6]의 MPR-QUIC 연구가 중요한 배경을 제공한다. 이들은 모든 데이터를 동일한 신뢰 방식으로 전송하지 않아도 된다는 점과, 경로를 여러 개 사용할 수 있다는 가능성을 제시한다. 또한 Mao 등[7]과 Bentaleb 등[8]은 적응형 비디오 전송에서 학습 기반 정책의 유효성을 보여주며, 향후 중요도 판단을 heuristic에서 ML, RL로 확장할 연구 방향을 뒷받침한다.

정리하면, 기존 연구는 콘텐츠 중요도 활용[2], 전송 계층 지연 최적화[3][4], 부분 신뢰성과 multipath[5][6], 학습 기반 적응[7][8]을 각각 발전시켜 왔다. 그러나 프레임 중요도 판단과 전송 행동 결정을 하나의 정책 안에서 통합하고, 그 효과를 동일한 실험 파이프라인에서 비교하는 구조는 아직 충분히 다뤄지지 않았다. 본 연구는 이 공백을 메우기 위한 현재 단계의 구현과 검증 결과를 제시한다.

## 3. 연구 방법

### 3.1 시스템 구조

본 연구의 처리 흐름은 세 단계로 구성된다. 먼저 `scripts/extract_video_trace.py`가 `ffprobe` 기반으로 H.264 비디오에서 프레임 유형, payload 크기, key frame 여부, GOP 번호, 시각 정보를 추출하여 trace CSV를 생성한다. 다음으로 `core/workload.py`는 각 프레임의 재생 마감시간을 `display_deadline_ms = pts_ms + duration_ms + playback_buffer_ms`로 계산하고, 본 중간보고에서는 `playback_buffer_ms = 50.0` ms를 사용하였다. 마지막으로 `core/simulator.py`가 프레임별 중요도와 전송 행동을 반영하여 완료 시각과 지표를 계산한다.

Stage A는 프레임 중요도 산정 단계이며, 현재 구현은 `HeuristicImportanceScorer`이다. 이 스코어러는 프레임 유형(I/P/B), deadline slack, key frame 여부를 반영하여 0.0에서 1.0 사이의 중요도 점수를 계산한다. 구체적으로 I 프레임은 가장 높은 기본 점수, P 프레임은 중간 점수, B 프레임은 낮은 점수를 받으며, 재생 마감시간이 가까울수록 긴급도가 증가한다. 현재 점수는 `0.45 x type_score + 0.40 x urgency + keyframe_bonus`의 형태로 계산된다. 코드에는 `MLImportanceScorer` 인터페이스도 포함되어 있으나, 본 중간보고의 비교 실험은 heuristic 기반 `frame_action_adaptive` 정책을 중심으로 수행하였다.

Stage B는 전송 행동 선택 단계이며, `policy/action.py`의 `select_action()`이 담당한다. 행동 공간은 `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `UNRELIABLE`, `DUPLICATE`, `DROP`의 다섯 가지이다. 선택 규칙은 중요도와 deadline slack을 우선 기준으로 삼고, queue 상태와 배칭 이득 추정값을 함께 고려한다. 즉, 늦었고 중요도가 낮은 프레임은 `DROP`, 매우 중요한 프레임은 `RELIABLE_SINGLE` 또는 `RELIABLE_MULTI`, 여유가 충분한 낮은 중요도 프레임은 `UNRELIABLE`로 처리한다. 또한 queue에 프레임이 쌓여 있어 배칭 이득이 예상되면 즉시 flush하지 않고 `RELIABLE_SINGLE` 상태로 잠시 유보하는 규칙도 포함되어 있다.

### 3.2 비교 정책과 실험 설정

중간보고 실험은 노트북 `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`에 정의된 동일한 전송 조건에서 수행되었다. 전송 파라미터는 `TransportConfig(rtt_ms=10, bandwidth_mbps=5, delayed_ack_ms=40)`이며, 비교 대상 정책은 세 가지이다. 첫째, `heuristic_baseline`은 `heuristic_frame_aware` 정책으로서 legacy batch/flush 규칙만 사용하며 프레임별 행동을 명시적으로 선택하지 않는다. 둘째, `frame_action_single_path`는 `frame_action_adaptive` 정책에 `available_paths=1`을 적용한 단일 경로 버전이다. 셋째, `frame_action_multipath`는 같은 정책에 `available_paths=2`, `path_profile='heterogeneous'`를 적용한 다중 경로 버전이다.

실험 데이터는 13개 공개 H.264 비디오로 구성되며, animation 5개, movie 3개, nature 5개로 구분된다. 파일 크기 기준은 노트북에서 `small(<10MB)`, `medium(10MB 이상 50MB 이하)`, `large(50MB 초과)`로 정의하였으나, 최종 집계에 포함된 샘플은 small 6개와 medium 7개였다. 각 비디오는 `dataset/videos/`에 저장되고, 프레임 트레이스는 `dataset/traces/`에서 관리된다. 중복 샘플 제거를 위해 MD5 기반 중복 제거가 적용되었다.

**Table 1. Summary of video groups used in the mid-term evaluation.**

| Group | Videos | Total frames | Mean I ratio | Mean P ratio | Mean B ratio | Mean payload bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| animation | 5 | 33509 | 0.0466 | 0.7435 | 0.2099 | 4544.1 |
| movie | 3 | 19636 | 0.0326 | 0.9674 | 0.0000 | 1901.8 |
| nature | 5 | 2454 | 0.0052 | 0.2514 | 0.7434 | 20181.0 |

Table 1에서 볼 수 있듯이 nature 그룹은 B 프레임 비율과 평균 payload가 모두 높아, 같은 네트워크 조건에서도 deadline miss가 발생하기 쉬운 구간이다. 반면 movie 그룹은 평균 payload가 작고 P 프레임 중심으로 구성되어 비교적 안정적인 전송이 가능하다.

### 3.3 평가 지표

본 중간보고의 핵심 평가지표는 `late_frame_ratio`이다. 이는 전체 프레임 중 재생 마감시간을 넘겨 도착한 프레임의 비율을 의미하며, 값이 낮을수록 deadline 준수 성능이 좋다. 보조 지표로는 정책이 의도적으로 포기한 프레임의 비율인 `dropped_frame_ratio`, 제시간에 도착한 프레임 payload 총합인 `useful_goodput_bytes`, GOP 복호 가능성을 나타내는 `decodable_gop_ratio`를 사용하였다. 또한 행동 비율 해석을 위해 `partial_reliability_ratio`, `multipath_usage_ratio`, `redundancy_ratio`를 함께 관찰하였다.

## 4. 연구 결과 및 논의

### 4.1 전체 평균 성능

정책별 전체 평균 결과는 Table 2와 같다. `heuristic_baseline`의 평균 `late_frame_ratio`는 0.3267이었고, `frame_action_single_path`는 0.2071, `frame_action_multipath`는 0.2431이었다. 즉, 프레임별 전송 행동을 선택하는 정책이 기준 정책보다 더 적은 deadline miss를 보였다. 특히 `frame_action_single_path`는 기준 정책 대비 약 36.6% 감소한 값을 기록하였다.

**Table 2. Overall mean performance by policy.**

| Policy | late_frame_ratio | dropped_frame_ratio | useful_goodput_bytes mean | decodable_gop_ratio |
| --- | ---: | ---: | ---: | ---: |
| heuristic_baseline | 0.3267 | 0.0000 | 9.63M | 0.5750 |
| frame_action_single_path | 0.2071 | 0.1087 | 10.09M | 0.5820 |
| frame_action_multipath | 0.2431 | 0.1087 | 9.66M | 0.5542 |

Table 2는 두 가지 사실을 보여준다. 첫째, `late_frame_ratio` 관점에서는 행동 선택 기반 정책이 분명한 개선을 보였다. 둘째, 이 개선은 일부 낮은 중요도 프레임을 포기하는 전략과 함께 나타났다. 두 행동 선택 정책의 `dropped_frame_ratio`가 0.1087이라는 점은, 현재 정책이 모든 프레임을 무조건 살리기보다 중요한 프레임의 deadline 준수를 우선하는 방향으로 작동했음을 의미한다. 이는 본 연구의 목적과 일치한다.

### 4.2 파일 크기 구간별 결과

파일 크기 구간별 결과는 Table 3과 같다. small 구간에서는 기준 정책 0.2090에 비해 `frame_action_single_path`가 0.0714, `frame_action_multipath`가 0.1202로 개선되었다. medium 구간에서도 기준 정책 0.4276에 비해 각각 0.3233, 0.3485로 개선되었다. 즉, 작은 파일과 중간 크기 파일 모두에서 행동 선택 기반 정책의 개선 경향이 일관되게 나타났다.

**Table 3. Mean late_frame_ratio by size bin.**

| Size bin | heuristic_baseline | frame_action_single_path | frame_action_multipath |
| --- | ---: | ---: | ---: |
| small | 0.2090 | 0.0714 | 0.1202 |
| medium | 0.4276 | 0.3233 | 0.3485 |

small 구간에서 개선 폭이 더 크게 나타난 이유는 payload가 상대적으로 작아 행동 선택 효과가 더 직접적으로 반영되기 때문으로 해석할 수 있다. 반면 medium 구간은 프레임 크기와 지연 부담이 커서 개선되더라도 여전히 높은 deadline miss가 남아 있다. 이는 이후 더 정교한 중요도 판단과 경로 제어가 필요함을 시사한다.

### 4.3 콘텐츠 그룹별 해석

콘텐츠 그룹별 평균 `late_frame_ratio`를 보면, animation 그룹은 기준 정책 0.0433에서 `frame_action_single_path` 0.0246으로 감소하였고, movie 그룹은 세 정책 모두 거의 0에 가까운 안정적 결과를 보였다. 반면 nature 그룹은 기준 정책 0.8060, `frame_action_single_path` 0.5138, `frame_action_multipath` 0.6004로 가장 어려운 전송 조건을 보였다. 이는 Table 1에서 확인한 것처럼 nature 그룹이 높은 B 프레임 비율과 큰 평균 payload를 가지기 때문이다. 다시 말해, 콘텐츠 구조 자체가 전송 난이도에 영향을 주며, 본 연구가 콘텐츠 중요도를 독립 변수로 삼는 이유도 여기에 있다.

### 4.4 행동 비율과 현재 한계

행동 비율을 보면 `partial_reliability_ratio`는 medium 구간에서 0.8846, small 구간에서 0.9712로 높게 나타났다. 이는 현재 정책이 많은 프레임을 비신뢰 전송 또는 드롭 후보로 판단하고 있음을 의미한다. 반대로 `multipath_usage_ratio`는 medium 0.0135, small 0.0037로 매우 낮았고, `redundancy_ratio`는 사실상 0이었다. 즉, 현재 결과는 multipath와 duplicate가 활발히 사용되어 얻은 개선이라기보다, 단일 경로 중심 정책에 partial reliability가 일부 결합된 결과에 가깝다.

또한 `frame_action_multipath`가 `frame_action_single_path`보다 항상 좋지 않았다는 점도 중요하다. 이를 곧바로 "multipath가 불필요하다"라고 해석해서는 안 된다. 현재 저장소의 multipath는 `core/simulator.py`에서 경로별 RTT, 대역폭, 손실률을 이용해 완료 시간을 근사하는 수준이며, 실제 QUIC 스택의 혼잡 제어, ACK 상호작용, 재정렬 버퍼, DATAGRAM 동작을 완전하게 재현하지 않는다. 특히 느린 경로가 전체 완료 시간을 끌어내리는 병목으로 작용할 수 있어, 현재의 단순화된 모델에서는 단일 경로가 더 안정적으로 보일 수 있다. 따라서 본 결과는 실제 프로토콜 수준 결론이 아니라, "현 모델에서 multipath 이득이 충분히 드러나지 않았다"는 중간 단계의 관찰로 해석하는 것이 타당하다.

## 5. 결론

본 연구는 실시간 비디오 전송에서 모든 프레임을 동일하게 다루는 방식이 중요한 프레임의 deadline miss를 늘릴 수 있다는 문제의식에서 출발하였다. 이를 해결하기 위해 H.264 프레임 중요도와 전송 행동을 함께 결정하는 cross-layer 적응 전송 구조를 설계하고, 현재 구현된 시뮬레이터 기반 정책을 공개 비디오 트레이스 13개에서 평가하였다. 그 결과 `frame_action_single_path`와 `frame_action_multipath`는 모두 기준 정책보다 낮은 `late_frame_ratio`를 보여, 프레임 단위 행동 선택이 실제로 유의미한 개선 방향임을 확인하였다.

동시에 본 중간보고는 현재 단계의 한계도 분명히 드러냈다. 첫째, multipath 및 부분 신뢰 전송은 아직 실제 QUIC 프로토콜 수준 구현이 아니라 시뮬레이터 기반 근사 모델이다. 둘째, 중요도 판단은 현재 heuristic 중심이며, ML과 RL은 확장 경로로 설계되어 있으나 본 중간보고의 핵심 결과는 아직 그 단계에 이르지 않았다. 셋째, QoE 평가는 deadline 중심 지표에 초점을 맞추었고, 실제 VMAF/SSIM과 같은 지각 품질 지표는 후속 과제로 남아 있다.

향후 연구에서는 첫째, 경로 상태와 부분 신뢰 전송 모델을 더 정교하게 만들어 multipath의 효과를 프로토콜 수준에 가깝게 검증할 계획이다. 둘째, `MLImportanceScorer`를 실제 학습 및 평가 파이프라인과 연결하여 heuristic 대비 개선 효과를 비교할 것이다. 셋째, RL 기반 중요도 판단과 전송 행동 결정을 통합하여, 콘텐츠 중요도 기반 cross-layer 적응 전송의 학습형 확장 가능성을 검증할 예정이다.

## 참고문헌

[1] Wiegand, T., Sullivan, G. J., Bjontegaard, G., & Luthra, A. (2003). Overview of the H.264/AVC video coding standard. *IEEE Transactions on Circuits and Systems for Video Technology, 13*(7), 560-576.

[2] Tüker, D., Rizk, A., & Zink, M. (2024). Using packet trimming at the edge for in-network video quality adaption. *Peer-to-Peer Networking and Applications*.

[3] Grazia, C. A., Patriciello, N., Klapez, M., & Casoni, M. (2021). The new TCP modules on the block: TCP pacing and TCP small queues. *IEEE Access, 9*.

[4] Borisov, N., Amit, N., & Tsafrir, D. (2025). Batching with end-to-end performance estimation. *Proceedings of HotOS '25*.

[5] Pauly, T., Kinnear, E., & Schinazi, D. (2022). *An unreliable datagram extension to QUIC* (RFC 9221).

[6] Han, B., Feng, L., & Shen, G. (2024). MPR-QUIC: Multi-path partially reliable transmission for priority and deadline-aware video streaming.

[7] Mao, H., Netravali, R., & Alizadeh, M. (2017). Neural adaptive video streaming with Pensieve. *Proceedings of ACM SIGCOMM*.

[8] Bentaleb, A., Taani, B., Begen, A. C., Timmerer, C., & Zimmermann, R. (2018). A survey on bitrate adaptation schemes for streaming media over HTTP. *IEEE Communications Surveys & Tutorials, 21*(1), 562-585.
