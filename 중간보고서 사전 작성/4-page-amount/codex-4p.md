# 콘텐츠 중요도 기반 Cross-layer 적응 전송을 위한 프레임 단위 전송 행동 설계와 중간 구현 평가

## Frame-Level Transport Action Design and Mid-Term Implementation Evaluation for Content-Aware Cross-Layer Adaptive Transport

박동찬⁺ · 손진곤⁺⁺

## 요약

본 연구는 H.264 프레임 메타데이터와 전송 계층 행동 선택을 결합하는 cross-layer 적응 전송의 중간 구현을 정리한다. 목적은 단순 TCP batching 튜닝이 아니라, 프레임 중요도와 마감시한 여유를 함께 보고 신뢰·비신뢰·단일·다중 경로·중복·드롭을 고르는 문헌 기반 혼합 정책을 시뮬레이터에서 점검하는 것이다. 개념은 Tüker·Grazia·Borisov·Mao·Han 등의 문헌 축을 `policy/action.py`, `core/simulator.py`에 합성한 것이며, 논문의 직접 이식이 아니라 문제축을 실험 가능한 형태로 옮긴 프로토타입이다. 파이프라인은 `scripts/extract_video_trace.py` → `policy/importance.py` → `policy/action.py` → `core/simulator.py` → `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb` 순이다. 13건 공개 비디오에서 `late_frame_ratio`는 기준 0.3267, 단일 경로 0.2071, 다중 경로 0.2431이었고, `dropped_frame_ratio`는 기준 0.0000, 행동 활성 시 0.1087이었다. `useful_goodput_bytes`·`decodable_gop_ratio`는 단일 경로가 유리했고, 다중 경로는 평균 지연 위반이 더 컸으며 `multipath_usage_ratio`도 매우 낮았다.

**주제어:** 콘텐츠 중요도, Cross-layer 적응 전송, 프레임 단위 스케줄링, 시뮬레이션, H.264

## ABSTRACT

Mid-term trace-driven prototype: H.264 frame metadata plus transport actions as a literature-based hybrid (trimming [1], pacing/batching [2,3], ABR learning [4], multipath partial reliability [5]) composed in `policy/action.py` / `core/simulator.py`, not a direct port. Thirteen videos: mean `late_frame_ratio` 0.3267 / 0.2071 / 0.2431; `dropped_frame_ratio` 0.0000 vs. 0.1087 with actions. Single-path wins on `useful_goodput_bytes` and `decodable_gop_ratio`; multipath is worse on mean lateness with very low `multipath_usage_ratio` under a simplified completion model.

**Keywords:** content-aware transport, cross-layer adaptation, frame scheduling, simulation, H.264

## 1. 서론

재생 마감시한을 넘긴 프레임은 품질에 직접 영향을 준다. I·GOP 민감 프레임의 지각은 연쇄 저하로 이어질 수 있다. 동일 신뢰성·동일 경로로만 전송하면 혼잡 시 중요·비중요 프레임이 같은 큐에서 경쟁한다. 전송만 조정하거나 중요도만 응용에서 다루면 분리되어 “어떤 프레임을 어떤 방식으로 보낼지”를 동시에 정하기 어렵다.

본 보고서는 동일한 문헌 기반 혼합 정책을 trace 시뮬레이터에서 실험한 중간 결과를 기술한다. `core/simulator.py`는 완료 시각·QoE를 근사하는 프로토타입이며, 혼잡 제어·재정렬·세밀 재전송은 제한적으로 반영된다. 결론은 최종 시스템이 아니라 현재 설정에서 관측된 경향에 한정한다.

## 2. 관련 연구 및 연구 문제

중요도·트리밍 [1], TCP pacing·TSQ [2], E2E 배칭 [3], 학습 기반 ABR [4], 다중 경로·부분 신뢰 [5] 등 선행 축이 있다. 행동공간은 위 문헌 축을 코드로 합성한 것이며, 논문 기여와 시뮬레이터 단순화를 구분해 읽어야 한다. 배칭·큐 관점은 지연·ACK penalty 근사에, 중요도 관점은 `policy/importance.py`와 `select_action()` 분기에 반영된다.

연구 문제는 다음 두 가지로 명시한다.

**RQ1.** Heuristic 기반 중요도 산정만으로도, `policy/action.py`에서 정의한 프레임 단위 전송 행동 선택이 동일한 시뮬레이터 설정에서 `late_frame_ratio`와 `useful_goodput_bytes`, `decodable_gop_ratio` 등 지표를 어떻게 바꾸는가?

**RQ2.** 동일한 중요도 산정을 유지한 채 다중 경로 행동을 허용하면(`frame_action_multipath`), 단일 경로(`frame_action_single_path`) 대비 평균 성능이 일관되게 좋아지는가, 아니면 현재 근사 모델과 임계값에서는 역전이나 둔화가 관측되는가?

## 3. 연구 설계 및 구현

### 3.1 파이프라인과 마감시한

`scripts/extract_video_trace.py`는 `ffprobe`로 프레임 메타데이터를 추출하여 `frame_type`, `payload_bytes`, `key_frame`, `gop_id`, `display_deadline_ms` 등을 구성한다. 노트북 실험에서 사용한 표시 마감시한은 `display_deadline_ms = pts_ms + duration_ms + playback_buffer_ms` 형태이며, `playback_buffer_ms=50.0` ms를 둔다. 중요도는 `policy/importance.py`의 `HeuristicImportanceScorer`가 담당하며, 다음 식으로 0–1 범위 점수를 만든다.

`ImportanceScore = clamp(0.45 × type_score + 0.40 × urgency + keyframe_bonus, 0, 1)`

`type_score`는 I=1.0, P=0.6, B=0.2, key frame bonus=0.15이다. `select_action()`은 slack·중요도·경로 수로 `RELIABLE_SINGLE`/`RELIABLE_MULTI`/`UNRELIABLE`/`DUPLICATE`/`DROP`을 고르며, 지각·저중요면 드롭, 고중요·여유·다경로면 중복 후보, 저중요·여유면 비신뢰 등의 분기로 요약된다.

### 3.2 시뮬레이터와 전송 설정

`TransportConfig(rtt_ms=10, bandwidth_mbps=5, delayed_ack_ms=40)`, MSS 1460 bytes, propagation factor 0.5, Nagle penalty 0.25이다. `RELIABLE_SINGLE`은 ACK penalty 포함, `UNRELIABLE`은 ACK 제거·전파 축소, `RELIABLE_MULTI`는 분할 후 최악 경로 완료 시각, `DUPLICATE`는 이중 전송 후 더 빠른 완료 시각을 쓴다. 실제 QUIC 혼잡·재정렬·재전송 전체를 반영하지는 않는다.

### 3.3 비교 정책

`heuristic_baseline`은 `PolicyConfig('heuristic_frame_aware')`로 프레임별 action selection 없이 큐·배칭 휴리스틱 중심으로 동작한다. `frame_action_single_path`는 `PolicyConfig('frame_action_adaptive', available_paths=1, path_profile='balanced')`, `frame_action_multipath`는 `available_paths=2`, `path_profile='heterogeneous'`이다. 세 조건 모두 동일한 heuristic 중요도 Stage A를 공유한다.

### 3.4 콘텐츠 그룹 특성

실험 비디오 13개는 animation 5, movie 3, nature 5이며, 파일 크기로 `small(<10MB)` 6개, `medium(10–50MB)` 7개로 구분하였다. IPB 분포·평균 GOP 길이·평균 payload는 그룹별로 크게 달랐다. nature는 B 프레임 비중이 높고 평균 payload가 커 큐 지연이 누적되기 쉽고, movie는 P 중심·작은 payload로 상대적으로 여유가 있다. animation은 중간 난이도로 작동한다. 표 1은 그룹별 요약이다.

**Table 1. Group-wise frame composition summary**

| Group | Videos | I ratio | P ratio | B ratio | Mean GOP (frames) | Mean payload (bytes) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| animation | 5 | 0.0466 | 0.7435 | 0.2099 | 45.0 | 4544.1 |
| movie | 3 | 0.0326 | 0.9674 | 0.0000 | 127.3 | 1901.8 |
| nature | 5 | 0.0052 | 0.2514 | 0.7434 | 234.2 | 20181.0 |

## 4. 실험 결과 및 해석

### 4.1 전체 평균

표 2는 정책별 전체 평균이다. `late_frame_ratio`는 `frame_action_single_path`가 0.2071로 가장 낮았고, `frame_action_multipath`는 0.2431로 기준 0.3267보다는 낮지만 단일 경로보다 높았다. `dropped_frame_ratio`는 기준 0.0000, 행동 선택을 켠 두 조건에서 0.1087로 동일하였다. `useful_goodput_bytes`는 단일 경로 10,090,070, 기준 9,626,585, 다중 경로 9,657,496이었다. `decodable_gop_ratio`는 단일 0.5820, 기준 0.5750, 다중 0.5542 순이었다.

**Table 2. Overall mean performance by policy**

| Policy | late_frame_ratio | dropped_frame_ratio | useful_goodput_bytes | decodable_gop_ratio |
| --- | ---: | ---: | ---: | ---: |
| heuristic_baseline | 0.3267 | 0.0000 | 9,626,585 | 0.5750 |
| frame_action_single_path | 0.2071 | 0.1087 | 10,090,070 | 0.5820 |
| frame_action_multipath | 0.2431 | 0.1087 | 9,657,496 | 0.5542 |

RQ1: 동일 설정에서 `late_frame_ratio`가 0.3267→0.2071로 감소했으나 `dropped_frame_ratio`는 0.1087로 증가했다. `useful_goodput_bytes` 최대는 단일 경로로, 마감 준수와 포기·유효 처리량을 함께 봐야 한다.

### 4.2 size_bin, 부분 신뢰, 다중 경로 사용

표 3은 size_bin별 `late_frame_ratio` 평균이다. small에서는 기준 0.2090, 단일 0.0714, 다중 0.1202였고, medium에서는 0.4276, 0.3233, 0.3485였다. 작은 파일 구간에서 행동 선택 효과가 더 두드러진다.

**Table 3. Mean late_frame_ratio by size_bin**

| size_bin | heuristic_baseline | frame_action_single_path | frame_action_multipath |
| --- | ---: | ---: | ---: |
| small | 0.2090 | 0.0714 | 0.1202 |
| medium | 0.4276 | 0.3233 | 0.3485 |

`partial_reliability_ratio`는 medium≈0.8846, small≈0.9712, `multipath_usage_ratio`는 medium≈0.0135, small≈0.0037이었다. 중복 전송은 거의 없었다. RQ2: 다중 경로는 평균 `late_frame_ratio`에서 단일 경로보다 나쁘고 사용 빈도도 낮았다.

### 4.3 그룹별 경향

그룹별 `late_frame_ratio`는 animation 0.043346→0.024604→0.031693, movie는 세 정책 모두 0에 가깝고, nature 0.806012→0.513755→0.600416로, 전체 평균은 nature 난도 영향이 크다. nature는 B·payload가 커 행동 여지가 있고, movie는 부하가 작아 세 정책이 비슷하다.

## 5. 결론

문헌 기반 혼합 정책을 코드로 옮긴 프로토타입에서 trace 시뮬레이터 지표 변화를 정리하였다. RQ1: 단일 경로 행동이 평균 지연 위반을 낮추고 `useful_goodput_bytes`·`decodable_gop_ratio`에서도 유리했다. RQ2: 현재 multipath 근사·낮은 사용 비율에서 다중 경로가 단일 경로보다 평균 `late_frame_ratio`가 높았다. 향후 경로·손실·ACK 모델 정교화, 중요도 추정 고도화, QUIC·에뮬레이터 대조가 필요하다.

## 참고문헌

[1] Tüker et al., “Using Packet Trimming at the Edge for In-Network Video Quality Adaption,” *Peer-to-Peer Networking and Applications*, 2024.

[2] Grazia et al., “On the Effect of TCP Pacing and TSQ on Latency and Jitter,” *IEEE Access*, 2021.

[3] Borisov et al., “Batching with End-to-End Performance Estimation,” *HotOS*, 2025.

[4] Mao et al., “Neural Adaptive Video Streaming with Pensieve,” *ACM SIGCOMM*, 2017.

[5] Han et al., “MPR-QUIC: Multipath Partially Reliable QUIC for Video Transport,” 2024.

---
⁺ 박동찬 소속 (기재)  
⁺⁺ 손진곤 소속 (기재)
