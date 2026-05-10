# 연관 논문 기반 연구 개선 제안

작성일: 2026-05-11

## 검토 범위

- 포함: 2, 3, 4, 5, 6, 9, 10주차 논문분석보고서 PDF
- 제외: 1, 7, 8주차
- 대조한 현재 연구 기준: `docs/research_goal.md`, `policy/importance.py`, `policy/action.py`, `scripts/mininet_frame_endpoint.py`, `eval/metrics.py`

## 한 줄 결론

현재 연구는 `TCP batching 최적화`가 아니라 `실제 비디오 프레임의 중요도와 deadline을 전송 계층 행동으로 연결하는 cross-layer 적응 전송`으로 더 선명하게 좁혀야 한다. 가장 먼저 보강할 부분은 ML/RL이 아니라, 실제 Mininet 전송에서 `deadline 전에 도착 가능한가`를 사전에 판정하고 그 결과를 frame-level TCP/UDP/drop 결정과 지표에 반영하는 것이다.

## 논문별 반영 포인트

| 주차 | 논문 방향 | 현재 연구에 반영할 점 |
| --- | --- | --- |
| 2주차 | BPP 기반 edge packet trimming, H.264 SVC, 중요도 기반 부분 전송 | frame 단위 결정에서 더 나아가 장기적으로 frame/layer/chunk 단위 중요도를 분리할 수 있다. 단, 지금은 SVC/packet trimming을 구현했다고 쓰면 안 되고, `프레임 중요도 기반 전송 행동`으로 제한해야 한다. |
| 3주차 | TCP pacing, TCP Small Queues, 지연-처리량 trade-off | 현재 `heuristic_frame_aware`는 batching 성격이 강하므로 baseline으로 격하시켜야 한다. 연구 본문은 batching 효과보다 socket queue, RTT, payload size, pacing/flush 지연이 deadline miss에 주는 영향을 측정하는 쪽으로 정리하는 것이 낫다. |
| 4주차 | MPR-QUIC, priority/deadline-aware partial reliability | 가장 가까운 관련 연구다. 현재 코드는 QUIC가 아니라 TCP/UDP socket 실험이므로 `MPR-QUIC 구현`이 아니라 `MPR-QUIC류의 priority/deadline 아이디어를 실제 Mininet frame action으로 축소 검증`한다고 써야 한다. |
| 5주차 | Pensieve, RL 기반 ABR | 바로 RL을 넣기보다 현재 이벤트 CSV를 state/action/reward 데이터셋으로 남기는 설계가 먼저다. 이후 `late_frame_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`를 reward 후보로 쓸 수 있다. |
| 6주차 | aCroSS, AI 기반 cross-layer adaptive streaming | 현재 `NetworkState`는 구조는 있지만 실제 실행에서는 설정값 중심이다. ACK/receive event 기반 RTT, loss, queue pressure 추정값을 채워 넣어야 cross-layer 주장에 힘이 생긴다. |
| 9주차 | D3T, deadline-aware scheduler, FEC/sending rate DRL | 가장 즉시 반영해야 할 논문이다. `deadline 초과 후 drop`이 아니라 `전송 전 예상 완료 시각 > deadline이면 low-value frame을 사전 drop 또는 UDP 전송`하는 feasibility scheduler를 넣어야 한다. |
| 10주차 | GRACE, neural codec 기반 loss-resilient video | 현 단계 구현 대상은 아니다. 대신 `deadline 이후 도착한 packet/frame도 loss로 본다`는 평가 관점을 가져오고, 논문 작성 시 실제 SSIM/VMAF가 없으면 `ssim_proxy`를 실제 화질 지표처럼 쓰지 않아야 한다. |

## 현재 구현에서 바로 고칠 연구 약점

1. `select_action()`의 drop 기준이 약하다.
   - 현재는 `deadline_slack_ms <= 0 and low importance`에 가까운 사후 drop이다.
   - D3T/MPR-QUIC 관점에서는 전송 전에 `now + payload_tx_time + RTT/2 <= deadline`을 계산해야 한다.
   - 즉, 아직 deadline이 지나지 않았더라도 도착 불가능하면 낮은 중요도 프레임은 drop하고, 중간 중요도는 UDP, 높은 중요도는 TCP 또는 향후 duplicate로 보내는 식이 더 설득력 있다.

2. `NetworkState`가 실제 측정 상태가 아니다.
   - 현재 `scripts/mininet_frame_endpoint.py`의 single-path 정책은 설정된 bandwidth/RTT/loss를 그대로 넣고, `queue_bytes=0`, `estimated_batch_gain=0.0`으로 둔다.
   - aCroSS식 cross-layer 연구라고 주장하려면 실제 receive event/ACK 간격/송신 큐 대기시간/최근 goodput에서 동적으로 상태를 추정해야 한다.

3. 지표가 논문 주장에 비해 아직 부족하다.
   - 이미 `late_frame_ratio`, `keyframe_late_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`가 있어 방향은 좋다.
   - 추가로 `late_bytes`, `wasted_late_bytes_ratio`, `on_time_goodput_ratio`, `dropped_keyframe_count`, `policy_action_distribution`을 넣으면 2/4/9주차 논문과 직접 연결된다.
   - `ssim_proxy`는 실제 SSIM이 아니므로 논문/보고서에서는 이름을 `quality_proxy` 정도로 낮추거나 실제 VMAF/SSIM 계산을 별도로 붙여야 한다.

4. baseline 정체성을 분리해야 한다.
   - `heuristic_frame_aware`는 TCP batching/flush baseline으로 두고, 연구 기여는 `frame_action_single_path`의 priority/deadline-aware action mapping으로 잡는 편이 명확하다.
   - 그래야 연구 방향이 `단순 TCP batching`으로 읽히지 않는다.

## 권장 실험 설계

### 1단계: 단일 경로 actual Mininet을 논문형 실험으로 고정

- 비디오: 현재 3개 실제 MP4 유지
- 대역폭: 1, 2, 3, 5 Mbps
- RTT: 10 ms 기본에 50 ms 또는 100 ms 추가
- loss: 0% 기본에 1%, 3% 추가
- 정책:
  - FIFO TCP 또는 현재 heuristic batching baseline
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - 개선형 `deadline_feasible_frame_action`
- 반복: 최소 3회, 가능하면 5회

### 2단계: Stage A 중요도 점수 강화

현재 점수는 frame type, urgency, keyframe bonus 중심이다. 다음 항목을 추가하면 논문과 더 잘 맞는다.

- payload 전송 비용: 같은 I/P/B라도 큰 프레임은 deadline miss 위험이 크다.
- GOP 의존성: keyframe뿐 아니라 해당 GOP에서 후속 프레임을 살리는 효과를 반영한다.
- 전송 가능성: bandwidth/RTT 기준으로 deadline 내 완료 가능성을 importance와 별도 축으로 둔다.
- 콘텐츠 변화량: 장기 확장으로 scene change, motion, saliency를 넣는다. 단, 실제 추출 전에는 주장하지 않는다.

### 3단계: Stage B를 feasibility-first scheduler로 바꾸기

권장 규칙은 다음 순서다.

1. 예상 완료 시각을 계산한다.
2. deadline 내 도착 불가능하고 중요도가 낮으면 drop한다.
3. deadline 여유가 작고 중요도가 중간이면 UDP로 보낸다.
4. 중요도가 높으면 TCP로 보내되, 향후 multipath에서는 duplicate 또는 best path를 선택한다.
5. batching은 높은 중요도 프레임에는 적용하지 않고, deadline 여유가 충분한 중간 프레임에만 제한한다.

### 4단계: multipath/QUIC는 후속 확장으로 격상

현재 코드는 실제 QUIC/MPR-QUIC 구현이 아니다. 따라서 보고서에서는 다음처럼 쓰는 것이 안전하다.

- 현재: TCP/UDP 기반 단일 경로 actual Mininet 검증
- 다음: 두 개의 Mininet path를 만든 뒤 `RELIABLE_MULTI`, `DUPLICATE`, path selection 검증
- 장기: QUIC DATAGRAM 또는 WebRTC/FEC 기반 prototype 검토

## 논문 작성 방향

### 연구 질문

실제 비디오 프레임의 중요도와 deadline을 전송 계층 행동에 반영하면, 제한된 대역폭의 실제 Mininet 환경에서 단순 TCP/batching 대비 deadline 내 유효 도착 프레임과 decodable GOP 비율을 개선할 수 있는가?

### 기여 서술

- 실제 MP4에서 추출한 frame metadata/payload를 사용한다.
- frame importance와 deadline feasibility를 결합한 Stage A/B 정책을 제안한다.
- TCP/UDP/drop action을 실제 Mininet 송수신 이벤트로 기록한다.
- 실제 송신 시각, 수신 시각, payload byte 기반으로 late frame, useful goodput, decodable GOP를 계산한다.

### 피해야 할 서술

- `MPR-QUIC를 구현했다`
- `QUIC partial reliability를 검증했다`
- `실제 SSIM/VMAF를 개선했다`
- `단순 TCP batching 최적화 연구다`
- `시뮬레이터 결과로 실제 전송 성능을 증명했다`

## 우선순위

1. `deadline_feasible_frame_action` 정책을 추가한다.
2. 이벤트 CSV에 action별 count, late bytes, on-time bytes를 집계한다.
3. `ssim_proxy` 표현을 실제 화질 지표와 분리한다.
4. 1/2/3/5 Mbps, RTT/loss 변화 실험을 고정한다.
5. 결과가 안정화된 뒤 multipath와 ML/RL을 후속 장으로 둔다.
