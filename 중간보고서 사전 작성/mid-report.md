# 콘텐츠 중요도 기반 Cross-layer 적응 전송에서 MPR-QUIC 행동공간 분석

## Effectiveness of MPR-QUIC Action Space in Content-Aware Cross-Layer Adaptive Transport

박동찬  
한국방송통신대학교 대학원 정보과학과

## 요약

본 보고서는 H.264 프레임 중요도(I/P/B) 기반 판단을 전송 계층 행동과 결합한 cross-layer 적응 전송 연구의 중간 성과를 정리한다. 연구의 목표는 단순 TCP batching 최적화가 아니라, 프레임 단위 중요도에 따라 신뢰/비신뢰, 단일경로/다중경로, 중복/드롭을 선택하여 지연 민감 비디오 전송 품질을 개선하는 것이다. 현재 구현은 `heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath` 3개 정책을 동일 데이터셋에서 비교하며, 공개 데이터셋 다운로드 안정화와 중복 콘텐츠 제거(MD5)까지 반영하였다. 실험 결과 전체 평균 `late_frame_ratio`는 `heuristic_baseline=0.3267`, `frame_action_multipath=0.2431`, `frame_action_single_path=0.2071`로 확인되었다. 즉, 행동 기반 정책은 기준 정책 대비 지연 위반 비율을 낮추었고, 현재 근사 모델에서는 single-path가 multipath보다 안정적인 경향을 보였다. 이는 multipath 행동공간의 필요성을 부정하는 결과가 아니라, 경로 이질성과 부분 신뢰 전송의 프로토콜 수준 효과를 더 정교하게 반영해야 함을 시사한다.

주제어: 콘텐츠 중요도, Cross-layer 적응 전송, MPR-QUIC, H.264 IPB, Late Frame Ratio

## ABSTRACT

This report presents mid-term progress on a content-aware cross-layer adaptive transport framework that combines H.264 frame importance (I/P/B) with transport actions. The objective is not plain TCP batching optimization, but frame-level decision making over reliable/unreliable delivery, single-path/multipath routing, and duplicate/drop actions for latency-sensitive video traffic. The current implementation compares three policies (`heuristic_baseline`, `frame_action_single_path`, and `frame_action_multipath`) under the same dataset and simulation pipeline. We also improved dataset reproducibility by adding resilient fallback downloads and MD5-based duplicate filtering. Experimental results show mean `late_frame_ratio` values of 0.3267, 0.2431, and 0.2071 for the three policies, respectively. This indicates that action-aware policies improve deadline performance over the baseline, while multipath gains remain limited under the current approximation. The result highlights the next step: refining protocol-level modeling of path heterogeneity and partial reliability.

Keywords: Content-Aware Transport, Cross-Layer Adaptation, MPR-QUIC, H.264, QoE

---

## 1. 서론

실시간 비디오 전송의 핵심 성능 문제는 평균 지연이 아니라, 재생 마감시간(deadline)을 넘긴 프레임의 누적이다. 사용자 체감 품질(QoE)은 몇 개 프레임의 과도한 지연만으로도 급격히 악화될 수 있으며, 특히 I 프레임과 같은 고중요 프레임의 지연은 GOP 단위 복호 가능성에 연쇄적으로 영향을 준다. 따라서 본 연구는 “모든 프레임을 동일하게 신뢰 전송”하는 접근을 벗어나, 프레임 중요도 기반으로 전송 행동을 다르게 선택하는 전략을 채택한다.

기존 전송 최적화는 크게 두 축으로 발전해 왔다. 첫째는 전송 계층의 큐/배치 제어이며, 둘째는 콘텐츠 특성 기반 선택 전송이다. 그러나 두 축이 분리되어 적용될 경우, 콘텐츠 중요도와 네트워크 상태가 상호작용하는 실제 서비스 상황을 충분히 반영하지 못한다. 예를 들어 네트워크가 혼잡한 상황에서 저중요 B 프레임에 동일한 신뢰 전송 비용을 부여하면, 고중요 프레임의 deadline miss 가능성이 오히려 증가할 수 있다.

본 연구는 이러한 문제를 해결하기 위해 cross-layer 관점을 취한다. 즉, 응용 계층의 프레임 의미(importance)와 전송 계층의 행동(action)을 한 정책 내에서 결합한다. 정책은 heuristic 기반으로 시작하되, 이후 ML/RL로 확장 가능한 구조를 유지한다. 중간보고의 목적은 이 구조가 실제 지표 개선으로 이어지는지를 확인하고, 현재 단계의 한계와 다음 연구 단계를 명확히 제시하는 데 있다.

## 2. 관련 연구

### 2.1 콘텐츠 중요도 기반 전송 연구

Tüker et al.[1]은 edge 환경에서 콘텐츠 중요도 기반 packet trimming 가능성을 보였고, 중요도가 낮은 데이터의 선택적 축소/포기가 네트워크 효율에 기여할 수 있음을 제시했다. 본 연구는 이 관점을 프레임 단위로 가져와, drop/unreliable와 같은 행동에 직접 연결한다.

### 2.2 전송 계층 지연 메커니즘 연구

Grazia et al.[2]은 TCP pacing/TSQ가 지연 및 jitter에 미치는 영향을 분석했다. 이는 전송 큐 관리와 flush 시점의 중요성을 뒷받침한다. Borisov et al.[3]은 E2E 상태를 고려한 adaptive batching의 필요성을 강조했으며, 본 연구의 queue-aware 규칙 설계에 근거를 제공한다.

### 2.3 MPR-QUIC 및 학습기반 정책 연구

Han et al.[4]은 multipath와 부분 신뢰 전송을 결합한 MPR-QUIC 방향을 제시했다. 본 연구는 이를 완전 구현하기보다, 중간보고 목적에 맞는 “정책 비교 + 지표 검증” 형태의 근사 실험으로 우선 반영했다. 또한 Mao et al.[5]의 Pensieve는 학습 기반 적응 정책의 실효성을 보여주며, 본 연구의 장기 로드맵(heuristic→ML→RL)을 정당화한다.

## 3. 연구 방법

### 3.1 시스템 구성

실험 파이프라인은 세 모듈로 구성된다.

1. 중요도 산정: `policy/importance.py`  
2. 행동 선택: `policy/action.py`  
3. 시뮬레이션/지표 집계: `core/simulator.py`

노트북 `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`은 공개 데이터셋 준비, 정책 실행, 지표 집계, 시각화, CSV 저장을 담당한다. 데이터셋 재현성을 높이기 위해 다중 URL fallback과 MD5 중복 제거를 포함한다.

### 3.2 개념 요약: 신뢰/비신뢰와 행동공간

본 연구에서 “신뢰/비신뢰”는 다음처럼 정의한다.

- 신뢰 전송 계열: `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `DUPLICATE`
- 비신뢰 전송 계열: `UNRELIABLE`
- 포기 계열: `DROP`

핵심은 정책 이름이 신뢰/비신뢰를 고정하지 않는다는 점이다. `frame_action_*` 정책은 프레임마다 `importance_score`, `deadline_slack_ms`, `network state`를 입력으로 받아 행동을 동적으로 선택한다.

### 3.3 정책별 분기 규칙(상세)

#### 3.3.1 `heuristic_baseline`

`heuristic_baseline`은 노트북에서 `PolicyConfig('heuristic_frame_aware')`로 설정된다. 이 정책은 frame action 분기(`select_action`)를 사용하지 않고, legacy batch/flush 규칙 중심으로 동작한다. 따라서 `UNRELIABLE`, `RELIABLE_MULTI`, `DUPLICATE`, `DROP`를 프레임 단위로 명시 선택하지 않는다.

#### 3.3.2 `frame_action_single_path (available_paths=1)`

`PolicyConfig('frame_action_adaptive', available_paths=1)`로 설정되며 프레임마다 행동을 선택한다. 가능한 대표 행동은 `RELIABLE_SINGLE`, `UNRELIABLE`, `DROP`이다. 경로가 1개이므로 `RELIABLE_MULTI`/`DUPLICATE`는 사실상 발생하지 않는다.

#### 3.3.3 `frame_action_multipath (available_paths=2)`

`PolicyConfig('frame_action_adaptive', available_paths=2)`로 설정되며, `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `DUPLICATE`, `UNRELIABLE`, `DROP` 전체 행동공간을 사용한다. 고중요 프레임은 다중경로 신뢰 전송 또는 중복 전송 후보가 되고, 저중요 프레임은 비신뢰 전송 또는 드롭 후보가 된다.

#### 3.3.4 `select_action` 우선순위(핵심 로직)

현재 구현의 규칙 우선순위는 다음과 같다.

1. deadline 초과 + 낮은 중요도: `DROP`
2. 매우 높은 중요도 + slack 여유 + 다중경로 가능: `DUPLICATE`
3. 높은 중요도: `RELIABLE_MULTI`(가능 시) 또는 `RELIABLE_SINGLE`
4. 배칭 이득 높고 중간 중요도: `RELIABLE_SINGLE`(flush 유보)
5. slack 충분 + 낮은 중요도: `UNRELIABLE`
6. 기본값: `RELIABLE_SINGLE`

즉, 본 정책은 “중요한 프레임은 더 안전하게, 덜 중요한 프레임은 더 가볍게”라는 직관을 deadline과 queue 상태를 결합해 실행한다.

### 3.4 데이터셋 및 실험 세팅

공개 데이터셋은 안정 URL 위주로 재구성했으며, 다운로드 실패 시 fallback URL을 순차 시도한다. 또한 MD5 해시로 동일 파일 중복을 차단해 분석 표본 다양성을 확보했다. 메타데이터에 `file_size_mb`와 `size_bin`을 추가해 small/medium 구간별 정책 효과를 분리 비교했다.

### 3.5 평가 지표

본 연구의 주요 지표는 다음과 같다.

- `late_frame_ratio`: deadline 초과 프레임 비율
- `dropped_frame_ratio`: 정책적 전송 포기 비율
- `partial_reliability_ratio = (unreliable + drop) / total_actions`
- `multipath_usage_ratio = reliable_multi / total_actions`
- `redundancy_ratio = duplicate / total_actions`

Fig. 1은 실험 흐름(데이터 준비→IPB 분석→정책 실행→지표 집계)을, Table 1은 정책별 주요 지표 요약을 나타낸다(최종 제출본에서 도표 삽입 예정).

## 4. 연구 결과

### 4.1 전체 평균 결과

실험 산출(`midreport_transport_efficiency.csv`) 기준 평균 `late_frame_ratio`는 다음과 같다.

- `heuristic_baseline`: 0.3267
- `frame_action_multipath`: 0.2431
- `frame_action_single_path`: 0.2071

`frame_action_*` 정책군이 baseline 대비 유의미하게 개선되었고, 현재 조건에서는 single-path가 가장 낮은 지연 위반 비율을 보였다. 이는 frame action 기반 정책 도입 자체가 효과적임을 의미한다.

### 4.2 size_bin 구간별 결과

`midreport_sizebin_policy_summary.csv` 집계 결과:

- medium 구간 late_frame_ratio 평균  
  - heuristic: 0.4276  
  - multipath: 0.3485  
  - single-path: 0.3233
- small 구간 late_frame_ratio 평균  
  - heuristic: 0.2090  
  - multipath: 0.1202  
  - single-path: 0.0714

구간별로 보더라도 baseline이 가장 불리하며, frame action 기반 정책의 개선 경향은 일관적이다.

### 4.3 신뢰/비신뢰 사용 패턴 해석

집계표에서 `frame_action_*` 정책은 높은 `partial_reliability_ratio`를 보인다(예: medium 약 0.8846, small 약 0.9712). 이는 저중요/긴급성 낮은 프레임을 비신뢰 또는 포기 처리해 고중요 프레임의 deadline 충족 기회를 확보한 결과로 해석된다.

`multipath_usage_ratio`는 `frame_action_single_path`에서 0, `frame_action_multipath`에서 양수(예: medium 0.0135, small 0.0037)로 관찰되어, multipath 행동이 실제로 사용되었음을 확인했다. 다만 값 자체가 크지 않아 multipath의 체감 이득이 제한적으로 나타난다.

`redundancy_ratio`는 현재 집계에서 0에 가깝다. 이는 `DUPLICATE`가 거의 선택되지 않았거나, 현 시나리오에서 강한 중복 전송이 필요할 정도의 고위험 상태가 충분히 발생하지 않았음을 시사한다.

### 4.4 왜 multipath가 single-path보다 항상 좋지 않은가

현재 구현은 중간보고 단계의 근사 모델이다. `core/simulator.py`에는 경로별 RTT/BW/loss를 반영하는 경량 모델이 도입되어 있으나, 실제 QUIC 스택의 세밀한 동작(경로별 혼잡제어, ACK 상호작용, reorder buffer 영향, datagram 재전송 정책)을 완전 재현하지는 않는다. 따라서 multipath의 잠재적 이득이 일부 시나리오에서 희석될 수 있다.

또한 경로 분할 전송의 경우 가장 느린 경로 완료시각이 병목이 되는 상황이 생길 수 있다. 반면 single-path는 경로 선택 불확실성이 없어 현재 파라미터에서 상대적으로 안정적인 결과를 만들 수 있다. 즉, 본 결과는 “multipath 무용론”이 아니라 “모델 정교화 필요성”에 대한 실험적 근거로 해석하는 것이 타당하다.

### 4.5 결과의 연구적 의미

이번 결과의 핵심 기여는 세 가지다.

1. 프레임 중요도와 전송 행동 결합이 baseline 대비 성능 개선으로 연결됨
2. 신뢰/비신뢰 혼합 정책이 deadline 중심 지표에서 실효성이 있음을 확인
3. multipath 확장의 필요성과 함께, 정밀 모델링 과제를 명확히 식별

이는 이후 ML/RL 확장 단계에서 어떤 부분을 먼저 고도화해야 하는지 우선순위를 제공한다.

## 5. 결론 및 향후 과제

본 연구는 콘텐츠 중요도 기반 cross-layer 적응 전송의 중간 성과를 제시하였다. 실험 결과 `frame_action_single_path`와 `frame_action_multipath`는 `heuristic_baseline` 대비 `late_frame_ratio`를 유의미하게 개선했으며, 특히 현재 설정에서는 `frame_action_single_path`가 가장 안정적인 성능을 보였다. 이 결과는 프레임 단위 행동공간 설계가 유효함을 보여준다.

동시에 multipath 이득이 제한적으로 나타난 점은 향후 과제를 분명히 한다. 첫째, 경로 상태 추정과 행동 선택의 결합을 정교화해야 한다. 둘째, 부분 신뢰 전송의 프로토콜 수준 모델을 개선해 실제 MPR-QUIC 동작 특성을 더 잘 반영해야 한다. 셋째, 중요도 판단 모델을 heuristic 중심에서 ML, RL로 단계적으로 확장해야 한다.

단기적으로는 구술평가2 목적에 맞추어 지표 설명의 명료성, 재현성 높은 데이터셋 운용, 정책별 분기 해석을 강화한다. 중기적으로는 경로별 E2E 상태추정과 행동 정책 결합을 고도화하고, 장기적으로는 RL 정책 학습을 도입해 “중요도 판단 + 전송 행동” 통합 최적화의 연구 기여를 확정할 계획이다.

---

## 참고문헌

[1] Tüker et al., “Using packet trimming at the edge for in-network video quality adaption,” *Peer-to-Peer Networking and Applications*, 2024.  
[2] Grazia et al., “On the Effect of TCP Pacing and TSQ on Latency and Jitter,” 2021.  
[3] Borisov et al., “Adaptive Batching for End-to-End Performance Estimation,” 2025.  
[4] Han et al., “MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport,” 2024.  
[5] Mao et al., “Neural Adaptive Video Streaming with Pensieve,” *SIGCOMM*, 2017.
