# mininet_actual_experiment_batch_runner repeat 3 재실행 결과 분석

작성일: 2026-05-13

## 실행 범위

- 노트북: `output/notebooks/mininet_actual_experiment_batch_runner.ipynb`
- batch log: `output/mininet_actual_experiment/batch_logs/batch_run_fast_1h_20260513_144628.csv`
- preset: `fast_1h`
- video: `archive_popeye_512kb`
- policy:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - `deadline_feasible_frame_action`
- bandwidth: `1 Mbps`, `5 Mbps`
- RTT: `10 ms`, `50 ms`
- loss: `0%`
- repeat: `3`
- `SKIP_EXISTING=False`

이번 재실행은 기존 결과를 재사용하지 않고 12개 조건을 모두 repeat 3으로 다시 수행했다. 따라서 이전 분석에서 문제가 되었던 repeat 1과 repeat 3 혼합 문제는 해소되었다.

## 완료 확인

노트북 preflight는 WSL2 Ubuntu에서 다음 항목을 통과했다.

- 원본 MP4 존재 확인
- `python3`
- `ffprobe`
- `mn`
- `pyav`
- `sudo -n true`

12개 job 모두 `completed`, return code `0`이다. 각 job은 약 `1315~1337 s`가 걸렸고, 총 36개 Mininet repeat가 수행되었다.

반복별 산출물 검증 결과:

- 모든 `client_events.csv`는 `11098`행이다.
- `frame_action_single_path`와 `heuristic_frame_aware`는 모든 조건에서 `server_events.csv`가 `11098`행이다.
- `deadline_feasible_frame_action`은 정책상 DROP이 있는 조건에서 서버 수신 수가 줄었다.
  - `1mbps`: repeat마다 `server_rows=11097`, `drop=1`
  - `1mbps_rtt50ms_loss0pct`: repeat마다 `server_rows=11090`, `drop=8`
- 모든 조건에서 `server_rows + dropped_frame_count = 11098`이므로 수신 부족은 전송 실패가 아니라 정책 DROP 결과로 정합적이다.
- 로그에는 각 repeat별 `Client completed`와 `Server completed`가 남아 있다.
- 오류 패턴(`Traceback`, `RuntimeError`, `ERROR`, `failed`, `Exception`) 검색 결과는 없다.

## repeat 3 전체 요약

| condition | policy | frames | late frames | late ratio | keyframe late ratio | decodable GOP ratio | on-time goodput ratio | wasted late bytes ratio | dropped |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 Mbps, RTT 10 ms | `deadline_feasible_frame_action` | 33294 | 201 | 0.006037 | 0.020541 | 0.978378 | 0.982946 | 0.017054 | 3 |
| 1 Mbps, RTT 10 ms | `frame_action_single_path` | 33294 | 222 | 0.006668 | 0.021622 | 0.977297 | 0.981476 | 0.018524 | 0 |
| 1 Mbps, RTT 10 ms | `heuristic_frame_aware` | 33294 | 512 | 0.015378 | 0.099099 | 0.900901 | 0.950679 | 0.049321 | 0 |
| 1 Mbps, RTT 50 ms | `deadline_feasible_frame_action` | 33294 | 2796 | 0.083979 | 0.709189 | 0.289730 | 0.751598 | 0.248402 | 24 |
| 1 Mbps, RTT 50 ms | `frame_action_single_path` | 33294 | 2560 | 0.076891 | 0.709189 | 0.290811 | 0.756275 | 0.243725 | 0 |
| 1 Mbps, RTT 50 ms | `heuristic_frame_aware` | 33294 | 18602 | 0.558719 | 0.727928 | 0.002162 | 0.388903 | 0.611097 | 0 |
| 5 Mbps, RTT 10 ms | `deadline_feasible_frame_action` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 10 ms | `frame_action_single_path` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 10 ms | `heuristic_frame_aware` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 50 ms | `deadline_feasible_frame_action` | 33294 | 6 | 0.000180 | 0.002162 | 0.997838 | 0.998685 | 0.001315 | 0 |
| 5 Mbps, RTT 50 ms | `frame_action_single_path` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 50 ms | `heuristic_frame_aware` | 33294 | 15912 | 0.477924 | 0.000000 | 0.007568 | 0.645649 | 0.354351 | 0 |

## 조건별 해석

### 1 Mbps, RTT 10 ms

이 조건에서는 `deadline_feasible_frame_action`이 가장 좋다.

- `frame_action_single_path` 대비 late frame: `222 -> 201`
- `frame_action_single_path` 대비 late ratio: `0.006668 -> 0.006037`
- `frame_action_single_path` 대비 decodable GOP ratio: `0.977297 -> 0.978378`
- `frame_action_single_path` 대비 on-time goodput ratio: `0.981476 -> 0.982946`

개선 폭은 크지 않지만 repeat 3에서 일관된다. RTT가 낮고 bandwidth가 빡빡한 조건에서는 deadline-aware action 선택이 기존 frame action baseline보다 약하게 우세하다.

### 1 Mbps, RTT 50 ms

이 조건에서는 `deadline_feasible_frame_action`이 `frame_action_single_path`를 넘지 못한다.

- `frame_action_single_path`: late `2560`, late ratio `0.076891`, decodable GOP `0.290811`
- `deadline_feasible_frame_action`: late `2796`, late ratio `0.083979`, decodable GOP `0.289730`
- `heuristic_frame_aware`: late `18602`, late ratio `0.558719`, decodable GOP `0.002162`

`deadline_feasible_frame_action`은 기존 휴리스틱보다는 훨씬 낫지만, `frame_action_single_path`보다 late frame이 `236`개 더 많고 on-time goodput도 `0.004677` 낮다.

상세 원인은 action/frame breakdown에서 보인다.

| policy | action | frame type | frames | late | late ratio |
| --- | --- | --- | ---: | ---: | ---: |
| `frame_action_single_path` | `RELIABLE_SINGLE` | I | 2775 | 1968 | 0.709189 |
| `frame_action_single_path` | `RELIABLE_SINGLE` | P | 30519 | 592 | 0.019398 |
| `deadline_feasible_frame_action` | `RELIABLE_SINGLE` | I | 1545 | 738 | 0.477670 |
| `deadline_feasible_frame_action` | `UNRELIABLE` | I | 1230 | 1230 | 1.000000 |
| `deadline_feasible_frame_action` | `UNRELIABLE` | P | 30495 | 804 | 0.026365 |
| `deadline_feasible_frame_action` | `DROP` | P | 24 | 0 | 0.000000 |

핵심은 I-frame late ratio가 두 frame action 계열에서 동일하게 `0.709189`라는 점이다. deadline 정책은 일부 I-frame을 `RELIABLE_SINGLE`에서 `UNRELIABLE`로 바꿨지만, `UNRELIABLE` I-frame은 전부 late가 되었다. 결과적으로 I-frame 보호가 개선되지 않았고, P-frame late와 DROP만 추가되어 전체 지표가 약간 나빠졌다.

### 5 Mbps, RTT 10 ms

세 정책 모두 late frame이 없다. 이 조건은 정책 우열을 가르기에는 너무 쉽다.

### 5 Mbps, RTT 50 ms

이 조건에서는 `frame_action_single_path`가 완전하고, `deadline_feasible_frame_action`도 거의 안정적이다.

- `frame_action_single_path`: late `0`, decodable GOP `1.000000`
- `deadline_feasible_frame_action`: late `6`, decodable GOP `0.997838`
- `heuristic_frame_aware`: late `15912`, decodable GOP `0.007568`

`deadline_feasible_frame_action`의 late 6개는 모두 `RELIABLE_SINGLE` I-frame이다. `UNRELIABLE` P-frame은 late 0이다. 5 Mbps에서는 P-frame을 UDP로 보내는 선택이 문제를 만들지 않지만, I-frame에 대해서는 아주 작은 deadline miss가 남는다.

## 종합 결론

이번 repeat 3 재실행 결과는 실제 MP4와 Mininet 기반 cross-layer 적응 전송 실험으로 신뢰할 수 있다. 모든 조건이 같은 repeat 수로 맞춰졌기 때문에 정책 비교도 이전보다 명확하다.

정책 성능은 다음처럼 정리된다.

- `deadline_feasible_frame_action`은 `1 Mbps / RTT 10 ms`에서 가장 좋다.
- `deadline_feasible_frame_action`은 `1 Mbps / RTT 50 ms`에서는 `frame_action_single_path`보다 약간 나쁘다.
- `5 Mbps / RTT 10 ms`는 세 정책 모두 완전해서 판별력이 낮다.
- `5 Mbps / RTT 50 ms`에서는 `frame_action_single_path`가 완전하고, `deadline_feasible_frame_action`은 거의 완전하지만 I-frame late 6개가 남는다.
- `heuristic_frame_aware`는 RTT 50 ms에서 크게 무너진다. cross-layer action 정책군과 기존 휴리스틱의 차이는 명확하다.

현재 `deadline_feasible_frame_action`의 주된 한계는 deadline 판단 자체보다 I-frame action 선택이다. 특히 `1 Mbps / RTT 50 ms`에서는 I-frame을 UDP로 넘긴 선택이 전부 late가 되었고, TCP I-frame도 절반 가까이 late였다. 단순히 I-frame을 더 많이 TCP로 보내는 것만으로는 충분하지 않을 수 있으며, I-frame의 deadline 여유와 크기를 함께 보는 별도 분기나 GOP 단위 의사결정이 필요하다.

## 다음 확인

다음 판별 실험은 RTT 50 ms에서 bandwidth 중간 구간을 채우는 것이다. 현재는 `1 Mbps`에서는 `deadline_feasible_frame_action`이 지고, `5 Mbps`에서는 거의 안정적이다. `2 Mbps`, `3 Mbps`를 추가해야 어느 지점에서 cross-layer 적응 전송 정책이 의미 있게 회복되는지 확인할 수 있다.

권장 조건:

- video: `archive_popeye_512kb`
- policies: `heuristic_frame_aware`, `frame_action_single_path`, `deadline_feasible_frame_action`
- bandwidth: `2 Mbps`, `3 Mbps`
- RTT: `50 ms`
- loss: `0%`
- repeat: `3`

이 결과가 나오면 다음 정책 수정 방향을 판단하기 쉽다. `2/3 Mbps`에서도 deadline 정책이 `frame_action_single_path`를 넘지 못하면, 다음 구현은 I-frame deadline guard와 GOP 단위 중요도 결정을 먼저 다뤄야 한다.
