# 2026-04-10 Mininet Actual Experiment 결과 평가

## 평가 대상

- 노트북: `output/notebooks/mininet_actual_experiment.ipynb`
- 실제 산출물:
  - `output/mininet_actual_experiment/archive_popeye_512kb/...`
  - `output/mininet_actual_experiment/echo_mediaelement/...`
  - `output/mininet_actual_experiment/w3c_movie_300/...`
- 평가 기준:
  - 실제 송신 시각: `client_events.csv`
  - 실제 수신 시각: `server_events.csv`
  - 실제 전송 결과 기반 집계: `summary.csv`, `by_repeat_summary.csv`

본 평가는 노트북 출력만 보지 않고, 노트북이 참조하는 실제 이벤트 CSV와 요약 CSV를 함께 확인한 결과다.

## 현재 노트북 상태

현재 노트북의 실험 파라미터 셀은 아래처럼 설정되어 있다.

- `VIDEO_NAMES = ["archive_popeye_512kb", "echo_mediaelement", "w3c_movie_300"]`
- `POLICY_NAMES = ["heuristic_frame_aware", "frame_action_single_path"]`
- `BANDWIDTH_VALUES_MBPS = [10]`
- `REPEAT_COUNT = 3`
- `ROUND_TRIP_TIME_MS = 10`
- `LOSS_RATE = 0.0`
- `PLAYBACK_BUFFER_MS = 50.0`

즉, 현재 노트북이 직접 표와 그래프로 보여주는 결과는 `10Mbps` 조건뿐이다. 노트북 마지막 표도 6개 조합 모두 `late_frame_ratio = 0`으로 끝난다.

## 산출물 완결성 점검

완결된 집계가 있는 조합:

- `archive_popeye_512kb / heuristic_frame_aware / 1, 2, 3, 10 Mbps`
- `archive_popeye_512kb / frame_action_single_path / 2, 3, 10 Mbps`
- `echo_mediaelement / heuristic_frame_aware / 10 Mbps`
- `echo_mediaelement / frame_action_single_path / 10 Mbps`
- `w3c_movie_300 / heuristic_frame_aware / 10 Mbps`
- `w3c_movie_300 / frame_action_single_path / 10 Mbps`

불완전한 조합:

- `archive_popeye_512kb / frame_action_single_path / 1 Mbps`
  - `repeat_01`만 완료
  - `repeat_02`는 `client.log`에 프레임 로드까지만 기록되고 종료 로그가 없음
  - `repeat_03` 없음
  - 상위 폴더의 `summary.csv`, `by_repeat_summary.csv` 없음

따라서 `1Mbps / frame_action_single_path`는 참고 수준의 단일 반복 결과로만 해석해야 한다.

## 결과 평가

### 1. 현재 노트북이 보여주는 10Mbps 결과

세 비디오 모두에서 두 정책이 완전히 동일한 결과를 보였다.

| 비디오 | 평균 비트레이트(Mbps) | 정책 | late frame | late ratio | keyframe late ratio | decodable GOP ratio |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| archive_popeye_512kb | 0.5139 | heuristic_frame_aware | 0 / 33294 | 0.000000 | 0.000000 | 1.000000 |
| archive_popeye_512kb | 0.5139 | frame_action_single_path | 0 / 33294 | 0.000000 | 0.000000 | 1.000000 |
| echo_mediaelement | 0.8181 | heuristic_frame_aware | 0 / 4014 | 0.000000 | 0.000000 | 1.000000 |
| echo_mediaelement | 0.8181 | frame_action_single_path | 0 / 4014 | 0.000000 | 0.000000 | 1.000000 |
| w3c_movie_300 | 0.0294 | heuristic_frame_aware | 0 / 21600 | 0.000000 | 0.000000 | 1.000000 |
| w3c_movie_300 | 0.0294 | frame_action_single_path | 0 / 21600 | 0.000000 | 0.000000 | 1.000000 |

평가:

- 현재 노트북 결과는 "실제 Mininet 파이프라인이 10Mbps에서 정상 동작한다"는 점만 보여준다.
- 세 비디오의 평균 비트레이트가 모두 `10Mbps`보다 크게 낮기 때문에, 이 조건은 정책 차이를 드러내는 스트레스 조건이 아니다.
- 따라서 현재 노트북 출력만으로는 `cross-layer 적응 전송`의 효과를 주장할 수 없다.

### 2. 실제로 차이가 드러난 스트레스 조건: `archive_popeye_512kb`

`archive_popeye_512kb`는 평균 비트레이트는 약 `0.514 Mbps`지만, I-frame 최대 크기가 `17174 bytes`, I-frame 평균 크기가 `6954.962 bytes`로 burst가 존재한다. 이 때문에 `1~2 Mbps`에서 실제 deadline miss가 발생했다.

완결된 결과와 참고 가능한 단일 반복 결과를 같이 정리하면 아래와 같다.

| 대역폭 | 정책 | 반복 범위 | late frame | late ratio | keyframe late ratio | decodable GOP ratio | useful goodput(MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 Mbps | heuristic_frame_aware | 3회 집계 | 519 / 33294 | 0.015588 | 0.101261 | 0.898739 | 64.640 |
| 1 Mbps | frame_action_single_path | repeat_01만 | 74 / 11098 | 0.006668 | 0.021622 | 0.977297 | 22.264 |
| 2 Mbps | heuristic_frame_aware | 3회 집계 | 56 / 33294 | 0.001682 | 0.002883 | 0.995315 | 67.893 |
| 2 Mbps | frame_action_single_path | 3회 집계 | 0 / 33294 | 0.000000 | 0.000000 | 1.000000 | 68.054 |
| 3 Mbps | heuristic_frame_aware | 3회 집계 | 0 / 33294 | 0.000000 | 0.000000 | 1.000000 | 68.054 |
| 3 Mbps | frame_action_single_path | 3회 집계 | 0 / 33294 | 0.000000 | 0.000000 | 1.000000 | 68.054 |

평가:

- `2 Mbps`에서는 `frame_action_single_path`가 3회 모두 `late frame 0`을 달성했다.
- 같은 `2 Mbps`에서 `heuristic_frame_aware`는 집계 기준 `56 / 33294` late frame이 남았다.
- `3 Mbps` 이상에서는 두 정책 모두 포화되지 않아 차이가 사라진다.
- `1 Mbps`에서는 `frame_action_single_path`의 단일 반복 결과가 더 좋지만, 아직 3회 반복이 완결되지 않아 확정 결론으로 쓰면 안 된다.

### 3. 반복 안정성

`archive_popeye_512kb / heuristic_frame_aware / 2 Mbps`의 반복별 결과:

- repeat_01: `54` late
- repeat_02: `1` late
- repeat_03: `1` late

해석:

- 현재 `heuristic_frame_aware`는 반복 간 변동성이 크다.
- 특히 repeat_01에서는 I-frame 6개, P-frame 48개가 late였고, 최대 deadline miss가 `234.018854 ms`까지 치솟았다.
- 반면 `frame_action_single_path / 2 Mbps`는 3회 모두 `late frame 0`으로 안정적이다.

이 차이는 현재 구현의 전송 방식과 직접 연결된다.

## 구현 관점 해석

현재 구현을 실제 코드 기준으로 확인한 결과:

- `heuristic_frame_aware`
  - `scripts/mininet_frame_endpoint.py`에서 모든 프레임을 `HEURISTIC_TCP_BATCH`로 기록
  - 실제 전송 프로토콜은 전부 `TCP`
- `frame_action_single_path`
  - `archive_popeye_512kb` 기준 I-frame `925개`는 `TCP`
  - P-frame `10173개`는 `UDP`
  - 바이트 비중은 `TCP 27.0%`, `UDP 73.0%`
- 완료된 실험에서 `dropped_frame_count = 0`

즉, 현재 차이는 "프레임 드롭 정책"에서 나온 것이 아니라, `콘텐츠 중요도 기반 전송 계층 결정`에서 나왔다.

이 점은 연구 방향과도 맞는다.

- 중요한 I-frame은 신뢰 전송(TCP)으로 보호
- 덜 중요한 P-frame은 비신뢰 전송(UDP)으로 보내 head-of-line blocking을 줄임
- 실제 Mininet 단일 병목 링크에서 deadline miss 감소로 이어짐

## 정량 해석 포인트

확정적으로 말할 수 있는 부분:

- `2 Mbps / archive_popeye_512kb`에서는 `frame_action_single_path`가 현재 `heuristic_frame_aware`보다 명확히 우수하다.
  - late ratio: `0.001682 -> 0.000000`
  - keyframe late ratio: `0.002883 -> 0.000000`
  - decodable GOP ratio: `0.995315 -> 1.000000`
  - useful goodput: `67.893 MiB -> 68.054 MiB`

참고 수준으로만 말할 수 있는 부분:

- `1 Mbps / archive_popeye_512kb / repeat_01`에서는 `frame_action_single_path`가 `heuristic_frame_aware`보다 더 좋다.
  - late ratio 약 `57.47%` 감소
  - keyframe late ratio 약 `78.72%` 감소
  - decodable GOP ratio `+7.89%p`
  - useful goodput 약 `3.35%` 증가
- 하지만 이는 `frame_action_single_path`가 1회만 완료된 상태이므로, 반복 안정성을 확인한 결론으로 쓰면 안 된다.

## 최종 판단

현재 노트북 결과 자체에 대한 평가는 다음과 같다.

1. 현재 노트북은 `10Mbps`만 실행했기 때문에, 실험 파이프라인 검증용 결과는 되지만 정책 비교용 결과는 아니다.
2. 실제로 정책 차이가 드러나는 구간은 `archive_popeye_512kb`의 `1~2 Mbps` 조건이다.
3. 완결된 데이터 기준으로는 `2 Mbps`에서 `frame_action_single_path`가 현재 `heuristic_frame_aware`보다 더 좋은 `cross-layer 적응 전송` 결과를 보였다.
4. `1 Mbps`에서도 같은 방향의 개선 신호가 보이지만, `frame_action_single_path` 반복 실행이 미완결이라 아직 확정 결론으로 사용하면 안 된다.

## 바로 필요한 후속 작업

- `archive_popeye_512kb / frame_action_single_path / 1 Mbps`를 3회 반복으로 다시 완료
- 노트북의 `BANDWIDTH_VALUES_MBPS`를 `[3, 2, 1]` 또는 `[10, 3, 2, 1]`로 바꿔 실제 스트레스 조건을 같이 시각화
- 노트북 표에 반복별 분산 또는 `by_repeat_summary.csv` 기반 결과를 추가해 `heuristic_frame_aware / 2 Mbps`의 변동성을 드러내기

