# 콘텐츠 중요도 기반 Cross-layer 적응 전송에서 MPR-QUIC 행동공간 분석

## Effectiveness of MPR-QUIC Action Space in Content-Aware Cross-Layer Adaptive Transport

박동찬  
한국방송통신대학교 대학원 정보과학과

## 요약

본 보고서는 H.264 프레임 중요도(I/P/B) 판단을 전송 계층 행동과 결합한 cross-layer 적응 전송 연구의 중간 성과를 정리한다. 연구 목표는 단순 TCP 배칭 최적화가 아니라, 프레임 단위 중요도에 따라 신뢰·비신뢰·다중경로·중복·드롭을 선택해 지연 민감 비디오 전송의 재생 마감시간(deadline) 준수를 개선하는 것이다. 행동 분기·시뮬레이션 가정은 문헌 개념의 합성이며, 동일 파이프라인에서 문헌 기반 혼합 정책을 비교한다. 대상은 `heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath`이고, URL fallback과 MD5 중복 제거로 재현성을 보강하였다. 전체 평균 `late_frame_ratio`는 `heuristic_baseline=0.3267`, `frame_action_multipath=0.2431`, `frame_action_single_path=0.2071`로, 행동 선택을 포함한 문헌 기반 혼합 정책이 기준 정책 대비 지연 위반 비율을 낮추는 경향이 확인되었다. 근사 설정에서는 단일경로 변형의 `late_frame_ratio`가 더 낮았고, multipath는 모델 보완 없이 제거할 대상으로 단정하기 어렵다.

주제어: 콘텐츠 중요도, Cross-layer 적응 전송, MPR-QUIC, H.264 IPB, Late Frame Ratio

## ABSTRACT

Mid-term results on content-aware cross-layer transport: H.264 I/P/B plus actions (reliable/unreliable, single/multipath, duplicate, drop). Literature concepts form hybrid policies—`heuristic_baseline`, `frame_action_single_path`, `frame_action_multipath`—with URL fallback and MD5 dedup. Mean `late_frame_ratio`: 0.3267, 0.2431, 0.2071; single-path lowest here; multipath needs richer modeling.

Keywords: Content-Aware Transport, Cross-Layer, MPR-QUIC, H.264, Deadline Miss

---

## 1. 서론

실시간 비디오에서 체감 품질은 평균 지연만이 아니라 재생 마감시간을 넘긴 프레임의 비중에 민감하다. I 프레임 등 고중요 프레임의 지연은 GOP 단위 복호에 연쇄 영향을 줄 수 있고, B 프레임은 상대적으로 지연 허용도가 다를 수 있다. 혼잡 상황에서 저중요 프레임에 과도한 신뢰 전송 비용을 쓰면 고중요 프레임의 마감시간 위반 가능성이 커질 수 있어, 모든 프레임을 동일하게 신뢰 전송하는 방식은 항상 타당하지 않다.

전송 최적화는 (i) 큐·배칭·flush 타이밍 등 전송 계층 제어와 (ii) 콘텐츠 특성을 반영한 선택 전송으로 나뉘어 발전해 왔다. 두 축이 분리되면 네트워크 상태와 프레임 의미의 상호작용을 한 정책 안에서 다루기 어렵다. 본 연구는 응용 계층의 프레임 중요도와 전송 계층 행동을 결합하는 cross-layer 관점을 취하며, 규칙 기반으로 시작하되 ML·RL로 확장 가능한 구조를 유지한다. Han et al.[4]의 MPR-QUIC 계열 행동공간은 차용·근사하여 중요도와 결합 시 지표 변화를 본다. 중간보고 목적은 동일 데이터·지표에서 기준 정책과 문헌 기반 혼합 정책의 차이를 수치로 확인하고 한계·후속 과제를 정리하는 것이다.

## 2. 관련 연구

### 2.1 콘텐츠 중요도 기반 전송

Tüker et al.[1]은 엣지 환경에서 콘텐츠 중요도에 따른 packet trimming 등 선택적 처리 가능성을 다루었다. 본 연구는 이 관점을 프레임 단위로 가져와 `UNRELIABLE`·`DROP` 같은 행동과 직접 연결한다.

### 2.2 전송 계층 지연·배칭

Grazia et al.[2]·Borisov et al.[3]은 pacing·TSQ·적응 배칭과 지연의 관계를 다루며, 본 파이프라인의 큐·flush 해석에 참고한다.

### 2.3 MPR-QUIC 및 학습 기반 적응

Han et al.[4]의 MPR-QUIC 방향을 행동공간 근사 시뮬레이션에 반영한다. Mao et al.[5] Pensieve는 향후 ML·RL 확장 참고로 둔다.

## 3. 연구 방법

### 3.1 시스템 구성

실험은 중요도 산정(`policy/importance.py`), 행동 선택(`policy/action.py`), 시뮬레이션 및 지표 집계(`core/simulator.py`)로 구성된다. 노트북 `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`에서 데이터 준비, 정책 실행, 집계·시각화·CSV 저장을 수행한다.

### 3.2 개념 요약: 신뢰/비신뢰와 행동공간

행동은 다음 세 계열로 구분한다.

- 신뢰 전송 계열: `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `DUPLICATE`
- 비신뢰 전송 계열: `UNRELIABLE`
- 포기 계열: `DROP`

정책 이름이 신뢰·비신뢰를 고정하지 않는다. `frame_action_*` 설정에서는 프레임마다 `importance_score`, `deadline_slack_ms`, 네트워크 상태 등을 입력으로 행동을 동적으로 선택한다.

### 3.3 정책별 분기 규칙

#### 3.3.1 `heuristic_baseline`

노트북에서 `PolicyConfig('heuristic_frame_aware')`에 해당한다. `select_action` 분기를 쓰지 않고 legacy batch/flush 규칙 중심으로 동작한다. 따라서 `UNRELIABLE`, `RELIABLE_MULTI`, `DUPLICATE`, `DROP`를 프레임 단위로 명시 선택하지 않는다.

#### 3.3.2 `frame_action_single_path` (`available_paths=1`)

`PolicyConfig('frame_action_adaptive', available_paths=1)`이다. 대표 행동은 `RELIABLE_SINGLE`, `UNRELIABLE`, `DROP`이다. 경로가 1개이므로 `RELIABLE_MULTI`·`DUPLICATE`는 사실상 발생하지 않는다.

#### 3.3.3 `frame_action_multipath` (`available_paths=2`)

`PolicyConfig('frame_action_adaptive', available_paths=2)`이다. `RELIABLE_SINGLE`, `RELIABLE_MULTI`, `DUPLICATE`, `UNRELIABLE`, `DROP` 전체 행동공간을 사용한다.

#### 3.3.4 `select_action` 6단계 우선순위

현재 구현의 규칙 우선순위는 다음과 같다.

1. deadline 초과·낮은 중요도: `DROP`
2. 매우 높은 중요도·slack 여유·다중경로 가능: `DUPLICATE`
3. 높은 중요도: `RELIABLE_MULTI`(가능 시) 또는 `RELIABLE_SINGLE`
4. 배칭 이득이 크고 중간 중요도: `RELIABLE_SINGLE`(flush 유보)
5. slack 충분·낮은 중요도: `UNRELIABLE`
6. 기본값: `RELIABLE_SINGLE`

### 3.4 데이터셋 및 실험 세팅

공개 데이터셋은 안정 URL을 우선하되 실패 시 fallback을 순차 시도한다. MD5로 동일 파일을 제거하여 표본 중복을 줄였다. 메타데이터에 `file_size_mb`와 `size_bin`(small/medium 등)을 두어 파일 크기 구간별로 `late_frame_ratio`와 행동 비율을 분리해 본다. 정책별로 동일 클립·동일 파이프라인을 적용해 차이를 정책 분기로 돌려보며, `size_bin`은 파일 크기 구간 후행 분석용 변수로 둔다.

### 3.5 평가 지표

- `late_frame_ratio`: deadline 초과 프레임 비율
- `dropped_frame_ratio`: 정책적 전송 포기 비율
- `partial_reliability_ratio = (unreliable + drop) / total_actions`
- `multipath_usage_ratio = reliable_multi / total_actions`
- `redundancy_ratio = duplicate / total_actions`

Fig. 1은 실험 흐름을, Table 1·2는 정책별·구간별 지표 요약을 나타낸다(최종 제출본에서 도표 삽입 예정).

**Fig. 1.** Experiment pipeline (data → IPB → policy → metrics). Placeholder for final submission.

**Table 1.** Mean `late_frame_ratio` by policy (overall).

| Policy | late_frame_ratio (overall) |
|--------|-----------------------------|
| heuristic_baseline | 0.3267 |
| frame_action_single_path | 0.2071 |
| frame_action_multipath | 0.2431 |

**Table 2.** Mean `late_frame_ratio` by `size_bin`.

| size_bin | heuristic_baseline | frame_action_single_path | frame_action_multipath |
|----------|-------------------|--------------------------|-------------------------|
| small | 0.2090 | 0.0714 | 0.1202 |
| medium | 0.4276 | 0.3233 | 0.3485 |

## 4. 연구 결과

### 4.1 전체 평균

- `late_frame_ratio` 평균(노트북·`midreport_*.csv` 집계): `heuristic_baseline` 0.3267, `frame_action_multipath` 0.2431, `frame_action_single_path` 0.2071.
- 문헌 기반 혼합 정책(`frame_action_*`)이 기준 정책보다 낮은 지연 위반 비율을 보였다.

### 4.2 `size_bin` 구간

- small: baseline 0.2090, single-path 0.0714, multipath 0.1202.
- medium: baseline 0.4276, single-path 0.3233, multipath 0.3485.
- 구간별로도 baseline이 가장 높은 비율을 보였다.

### 4.3 행동 비율 및 해석

- `partial_reliability_ratio`: medium 약 0.8846, small 약 0.9712 수준. 저중요·여유 있는 프레임을 비신뢰·포기 처리하는 비중이 커, 고중요 프레임 쪽으로 전송 자원을 기울이는 효과로 읽을 수 있다.
- `multipath_usage_ratio`: single-path 설정에서는 0, multipath 설정에서 medium 약 0.0135·small 약 0.0037. 다중경로 신뢰 행동은 사용되었으나 비중은 작다.
- `redundancy_ratio`는 현재 집계에서 0에 가깝다. `DUPLICATE`가 거의 선택되지 않았거나, 중복 전송이 필요할 정도의 고위험 구간이 제한적이었을 수 있다.

### 4.4 multipath와 single-path 비교에 대한 해석

시뮬레이터는 경로별 RTT·대역폭·손실의 경량 모델이며 QUIC 세부(혼잡제어·ACK·재정렬)를 완전 재현하지는 않는다. 분할 전송에서 느린 경로가 병목이 될 수 있어 현 설정에서는 single-path가 더 낮은 `late_frame_ratio`로 보일 수 있다. multipath 무용 단정보다 모델 보완 과제에 가깝다.

### 4.5 정리

다음 관찰로 묶어 말할 수 있다. (1) 문헌 기반 혼합 정책이 baseline 대비 `late_frame_ratio`를 낮추는 방향이 보였다. (2) `partial_reliability_ratio`가 높아 비신뢰·포기 혼합이 집계에 드러난다. (3) multipath 행동은 소수 선택되었고 평균 위반 비율은 single-path 변형이 더 낮았다. 후속 단계에서는 경로 상태 추정과 프로토콜 모델 보강을 검토한다.

## 5. 결론

문헌 기반 혼합 정책(`frame_action_single_path`, `frame_action_multipath`)은 `heuristic_baseline` 대비 `late_frame_ratio`를 낮추었다. 구현은 문헌 개념의 합성·근사이므로 수치는 동일 파이프라인의 중간 스냅샷으로 본다. multipath 행동 비중·이득은 제한적이어 경로·부분 신뢰 모델 보완이 필요하다.

**향후 과제**

- 단기: 구술·중간 제출 대비 지표 정의·정책 분기(3.3절) 설명의 명료화, 데이터셋 재현 절차 정리.
- 중기: 경로별 E2E 상태와 행동 선택의 결합 정교화, 시뮬레이터와 MPR-QUIC 문헌[4]의 행동 의미 정합성 점검.
- 장기: 중요도 산정을 ML·RL로 확장[5]하고, 규칙 기반 `select_action`과의 비교·대체 실험을 누적한다.

---

## 참고문헌

[1] Tüker et al., “Using packet trimming at the edge for in-network video quality adaption,” *Peer-to-Peer Networking and Applications*, 2024.  
[2] Grazia et al., “On the Effect of TCP Pacing and TSQ on Latency and Jitter,” *IEEE Access*, 2021.  
[3] Borisov et al., “Adaptive Batching for End-to-End Performance Estimation,” *HotOS*, 2025.  
[4] Han et al., “MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport,” 2024.  
[5] Mao et al., “Neural Adaptive Video Streaming with Pensieve,” *SIGCOMM*, 2017.
