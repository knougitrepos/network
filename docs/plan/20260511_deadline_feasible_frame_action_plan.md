# Deadline-feasible frame action 개선 계획

작성일: 2026-05-11

## 목적

현재 연구를 `단순 TCP batching 최적화`가 아니라, 실제 비디오 프레임의 중요도와 deadline을 전송 계층 행동에 연결하는 `cross-layer 적응 전송` 연구로 고정한다. 구현 범위는 우선 1~3단계까지이며, 4단계의 GRACE/FEC 결합은 후속 확장으로 분리한다.

## 현재 상태 분석

현재 after-mid 파이프라인은 실제 MP4에서 frame payload를 추출하고, Mininet client/server에서 실제 TCP/UDP 송수신 이벤트를 기록한다. `heuristic_frame_aware`는 TCP batch/flush 기반 baseline이고, `frame_action_single_path`는 frame importance와 deadline slack을 이용해 TCP/UDP/DROP을 선택한다.

핵심 약점은 다음과 같다.

1. `select_action()`의 DROP 판단이 사후적이다.
   - 현재 구조는 `deadline_slack_ms <= 0`에 가까운 상황에서 낮은 중요도 프레임을 drop한다.
   - D3T, MPR-QUIC류 논문과 연결하려면 deadline이 아직 남아 있어도 `예상 완료 시각 > deadline`이면 전송 가치가 낮은 프레임을 사전에 drop해야 한다.

2. Stage A 중요도 점수가 payload 비용과 GOP 의존성을 충분히 반영하지 않는다.
   - 현재 점수는 frame type, urgency, keyframe bonus 중심이다.
   - 같은 P-frame이라도 payload가 크면 deadline miss 위험이 커지고, keyframe은 해당 GOP 전체 복호 가능성에 영향을 준다.

3. 실험 축이 논문형 matrix로 명시되어 있지 않다.
   - 노트북에는 여러 bandwidth 값이 보이지만, after-mid 기준 실험 범위를 코드/문서에서 더 명확히 고정할 필요가 있다.
   - 특히 RTT/loss 변화가 없으면 cross-layer 전송 정책의 강점을 설명하기 어렵다.

4. 지표가 action의 비용과 낭비를 충분히 드러내지 않는다.
   - `late_frame_ratio`, `keyframe_late_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`는 유지한다.
   - 추가로 late bytes, on-time bytes, action별 late/drop 분포가 있어야 “왜 이 정책이 나은지”를 설명할 수 있다.

## 1단계 계획: 단일 경로 actual Mininet 실험 축 고정

### 범위

- 비디오: 기존 실제 MP4 3개 유지
  - `archive_popeye_512kb`
  - `echo_mediaelement`
  - `w3c_movie_300`
- bandwidth: `1`, `2`, `3`, `5 Mbps`
- RTT: `10 ms`, `50 ms`, `100 ms`
- loss: `0%`, `1%`, `3%`
- repeat: 기본 `3회`, 최종 표에는 가능하면 `5회`
- 정책:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - 신규 `deadline_feasible_frame_action`

### 구현 방향

1. `scripts/mininet_actual_experiment.py`의 policy choices에 신규 정책을 추가한다.
2. 실험 matrix를 직접 생성하는 별도 runner 또는 notebook cell에서 위 축을 명시한다.
3. 기존 정책명은 유지하여 과거 결과와 비교 가능하게 한다.
4. output 경로는 기존 구조를 유지한다.
   - `output/mininet_actual_experiment/<video>/<policy>/<bandwidth>mbps/...`
   - RTT/loss가 추가되면 충돌 방지를 위해 `rtt<value>ms_loss<value>` suffix를 붙이는 방식을 검토한다.

### 주의점

- 실제 MP4가 없으면 실패해야 한다.
- Mininet/WSL2/root 조건이 없으면 실패해야 한다.
- mock, synthetic, fallback 실행 경로는 추가하지 않는다.

## 2단계 계획: Stage A 중요도 점수 강화

### 목표

importance를 단순 frame type 점수가 아니라, frame value와 전송 비용을 함께 반영하는 점수로 개선한다.

### 추가할 신호

1. payload 전송 비용
   - `payload_bytes`가 클수록 deadline 내 전송 위험이 커진다.
   - 단, 큰 I-frame은 무조건 낮추면 안 되므로 payload cost는 importance를 낮추는 단독 항목이 아니라 feasibility 판단과 함께 쓴다.

2. GOP 의존성
   - keyframe은 현재 frame 하나가 아니라 GOP 전체 복호 가능성에 영향을 준다.
   - `key_frame == 1` 또는 GOP 시작 frame에는 보호 가중치를 둔다.

3. deadline urgency
   - 기존 urgency는 유지하되, playback buffer 기준만이 아니라 현재 예상 전송 시간과 비교해야 한다.

4. 전송 가능성은 importance와 분리
   - “중요한가”와 “deadline 내 보낼 수 있는가”는 다른 축이다.
   - 따라서 Stage A는 frame value를 계산하고, Stage B에서 feasibility를 결합한다.

### 제안 산식

초기 구현은 과도한 ML 없이 휴리스틱으로 둔다.

```text
importance =
  type_weight
  + urgency_weight
  + keyframe_or_gop_weight
  - payload_cost_weight
```

단, 최종 score는 `0.0~1.0`으로 clamp한다. payload cost는 전체 영상의 payload 분포를 알아야 안정적이므로, 처음에는 `payload_bytes / recent_or_video_max_payload_bytes` 형태의 정규화 값을 쓴다.

### 테스트 기준

- I-frame 또는 keyframe은 같은 조건의 P/B-frame보다 높은 점수를 받아야 한다.
- deadline slack이 작을수록 urgency 점수가 올라가야 한다.
- 같은 frame type과 deadline이면 payload가 큰 frame의 비용 신호가 반영되어야 한다.
- score는 항상 `0.0~1.0` 범위에 있어야 한다.

## 3단계 계획: Stage B를 feasibility-first scheduler로 변경

### 목표

`deadline_feasible_frame_action`은 먼저 “이 frame이 deadline 전에 도착 가능한가”를 계산한 뒤, importance에 따라 TCP/UDP/DROP을 선택한다.

### 핵심 계산

```text
payload_tx_time_ms = payload_bytes * 8 / bandwidth_mbps
estimated_completion_ms =
  current_time_ms
  + payload_tx_time_ms
  + rtt_ms * 0.5
  + queue_delay_ms

feasible = estimated_completion_ms <= display_deadline_ms
```

초기 구현에서는 `queue_delay_ms`를 0 또는 현재 client-side queued bytes 기반 근사로 시작한다. 이후 실제 send/receive event 기반으로 보강한다.

### 권장 action 규칙

1. deadline 내 도착 불가능하고 importance가 낮으면 `DROP`
2. deadline 내 도착 불가능하지만 importance가 높으면 `RELIABLE_SINGLE`
3. deadline 여유가 작고 importance가 중간이면 `UNRELIABLE`
4. deadline 여유가 충분하고 importance가 낮으면 `UNRELIABLE`
5. importance가 높으면 `RELIABLE_SINGLE`
6. batching은 신규 정책에 넣지 않는다.

### 왜 batching을 배제하는가

신규 정책의 목적은 `deadline-aware frame action`을 검증하는 것이다. batching까지 동시에 넣으면 개선 원인이 deadline feasibility인지, TCP flush 조절인지 분리하기 어렵다. 따라서 `heuristic_frame_aware`는 batching baseline으로 남기고, 신규 정책은 frame-level action mapping에 집중한다.

### 이벤트/요약 지표 추가

신규 정책이 실제로 무엇을 바꿨는지 보이려면 summary에 다음 값을 추가한다.

- `on_time_bytes`
- `late_bytes`
- `dropped_bytes`
- `wasted_late_bytes_ratio = late_bytes / sent_bytes`
- `on_time_goodput_ratio = on_time_bytes / sent_bytes`
- `dropped_keyframe_count`
- action별 count: `reliable_single_count`, `unreliable_count`, `drop_count`
- action별 late count: `reliable_single_late_count`, `unreliable_late_count`

### 테스트 기준

- low importance frame이 deadline 내 도착 불가능하면 `DROP`
- high importance frame은 deadline 내 도착 불가능해도 `DROP`하지 않는다.
- medium importance frame은 deadline 여유가 작으면 `UNRELIABLE`을 선택할 수 있다.
- 기존 `frame_action_single_path` 동작은 깨지지 않아야 한다.
- summary aggregation에서 신규 byte/action 지표가 누락되지 않아야 한다.

## 구현 순서

1. 테스트 추가
   - `policy/action.py`의 신규 feasibility 판단 테스트
   - `policy/importance.py`의 payload/GOP/urgency 반영 테스트
   - `eval/metrics.py` 또는 `core/mininet_actual_experiment.py`의 신규 summary 지표 테스트

2. 정책 함수 추가
   - 기존 `select_action()`을 크게 깨지 않고 신규 함수 또는 mode를 추가한다.
   - 권장 이름: `select_deadline_feasible_action()`

3. endpoint 연결
   - `scripts/mininet_frame_endpoint.py`에 `run_deadline_feasible_frame_action_client()` 추가
   - policy name: `deadline_feasible_frame_action`

4. experiment CLI 연결
   - `scripts/mininet_actual_experiment.py` policy choices에 신규 정책 추가
   - README와 notebook matrix는 구현 완료 뒤 별도 문서 갱신

5. summary 지표 확장
   - `ExperimentSummary` dataclass 확장
   - 기존 CSV와 호환이 필요하면 신규 컬럼만 뒤에 추가

6. 검증
   - 단위 테스트
   - 실제 Mininet 전 preflight
   - 작은 실제 MP4 1개, bandwidth 5 Mbps, repeat 1 smoke
   - 이후 논문형 matrix 실행

## 4단계 분석: GRACE/FEC 결합 가능성

10주차 GRACE의 핵심은 단순 FEC 추가가 아니다. GRACE는 neural codec이 손실 상황을 전제로 representation을 만들고, decoder가 partially received packet으로 복원할 수 있게 학습하는 방식이다. 현재 연구에 바로 GRACE를 구현하는 것은 범위가 크고, neural codec 학습/복원/화질평가까지 필요하므로 after-mid의 즉시 구현 대상으로는 부적절하다.

다만 FEC 개념을 제한적으로 조합하는 것은 연구적으로 의미가 있다.

### 가능한 결합 방식

1. frame-level lightweight FEC
   - high importance frame에만 parity/redundant chunk를 추가한다.
   - Reed-Solomon 같은 실제 FEC 라이브러리를 쓰되, requirements에 명시한다.
   - 구현 난이도는 중간이지만 실제 복구 로직과 payload overhead 측정이 필요하다.

2. duplicate 기반 pseudo-FEC
   - 같은 high importance frame을 TCP+UDP 또는 두 경로로 중복 전송한다.
   - 실제 FEC는 아니므로 FEC라고 부르면 안 된다.
   - multipath 실험 전 단계에서 “redundant transmission” baseline으로는 쓸 수 있다.

3. deadline-aware FEC ratio
   - D3T처럼 deadline, loss, importance에 따라 redundancy 비율을 조절한다.
   - 현재 단일 경로 정책이 안정화된 뒤 추가해야 한다.

4. GRACE-style 평가 관점만 차용
   - deadline 이후 도착한 packet/frame은 전송 성공이 아니라 application-level loss로 본다.
   - 이 관점은 지금 바로 지표에 반영할 수 있다.

### 권장 판단

4단계에서 GRACE와 같이 FEC 기술을 조합하는 것은 “좋은 확장”이지만, 지금 논문 기여의 중심으로 두면 연구 범위가 흐려진다. 우선순위는 다음이 적절하다.

1. 1~3단계로 deadline-feasible frame action의 효과를 actual Mininet에서 확정한다.
2. 그 다음 duplicate/redundant transmission을 baseline으로 추가한다.
3. 이후 실제 FEC를 high importance frame에만 제한적으로 적용한다.
4. GRACE 자체는 직접 구현 대상이 아니라 관련 연구와 장기 확장으로 둔다.

### 보고서 표현

사용 가능한 표현:

- `GRACE의 손실-강인 비디오 전송 관점은 deadline 이후 도착한 frame을 application-level loss로 해석하는 본 연구의 지표 설계와 연결된다.`
- `본 연구의 후속 확장으로 high-importance frame에 선택적 redundancy 또는 FEC를 부여하는 방식을 검토할 수 있다.`

피해야 할 표현:

- `GRACE를 구현했다`
- `neural codec 기반 복원을 수행했다`
- `FEC로 화질을 개선했다`
- `패킷 손실 복구를 검증했다`

## 최종 권장 로드맵

1. `deadline_feasible_frame_action`을 신규 정책으로 추가한다.
2. Stage A는 payload/GOP/urgency 반영 휴리스틱으로 강화한다.
3. Stage B는 feasibility-first scheduler로 분리한다.
4. summary에는 byte/action 기반 지표를 추가한다.
5. 3개 실제 MP4, 4개 bandwidth, 3개 RTT, 3개 loss, 3회 반복 matrix를 실행한다.
6. 결과가 안정되면 duplicate baseline을 추가한다.
7. 마지막으로 선택적 FEC를 high importance frame에만 적용하는 후속 실험을 설계한다.
