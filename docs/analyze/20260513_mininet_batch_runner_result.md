# mininet_actual_experiment_batch_runner 결과 분석

작성일: 2026-05-13

## 실행 범위

- 노트북: `output/notebooks/mininet_actual_experiment_batch_runner.ipynb`
- preset: `fast_1h`
- video: `archive_popeye_512kb`
- policy:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - `deadline_feasible_frame_action`
- bandwidth: `1 Mbps`, `5 Mbps`
- RTT: `10 ms`, `50 ms`
- loss: `0%`
- notebook repeat 설정: `1`
- `SKIP_EXISTING=True`

노트북 preflight는 WSL2 Ubuntu에서 `python3`, `ffprobe`, `mn`, `pyav`, `sudo -n true`, 원본 MP4 존재 여부를 통과했다.

## 완료 확인

이번 노트북 실행에서 새로 수행된 조건은 4개다.

| job | policy | bandwidth | RTT | status | elapsed |
| ---: | --- | ---: | ---: | --- | ---: |
| 4 | `heuristic_frame_aware` | 5 Mbps | 50 ms | completed, return code 0 | 436.735 s |
| 6 | `frame_action_single_path` | 1 Mbps | 50 ms | completed, return code 0 | 443.657 s |
| 8 | `frame_action_single_path` | 5 Mbps | 50 ms | completed, return code 0 | 441.422 s |
| 12 | `deadline_feasible_frame_action` | 5 Mbps | 50 ms | completed, return code 0 | 440.890 s |

네 조건 모두 `repeat_01/client_events.csv`와 `repeat_01/server_events.csv`가 각각 `11098`행이며, 로그에서 `Client completed`와 `Server completed: received_frames=11098`가 확인된다. 따라서 이번에 새로 실행된 Mininet 전송은 축소 실행이나 실패 산출물이 아니라 실제 완료 산출물로 볼 수 있다.

## 주의할 점

노트북의 최종 비교 표는 12개 조건을 모두 로드하지만, `SKIP_EXISTING=True` 때문에 기존 산출물과 이번 신규 산출물이 섞여 있다.

- 기존 재사용 산출물 중 일부는 repeat 3 집계라서 `frame_count=33294`다.
- 이번 신규 산출물은 repeat 1이라서 `frame_count=11098`다.
- 따라서 같은 표 안의 ratio는 참고 가능하지만, raw count와 반복 안정성은 동일 조건으로 직접 비교하면 안 된다.

특히 `1 Mbps / RTT 50 ms / loss 0%` 조건은 `frame_action_single_path`만 이번에 repeat 1로 새로 실행되었고, `deadline_feasible_frame_action`과 `heuristic_frame_aware`는 기존 repeat 3 산출물이다. 이 조건의 정책 우열은 현재 표만으로 확정하기보다 repeat 수를 맞춰 다시 보는 것이 맞다.

## 전체 요약 지표

| condition | policy | frames | late frames | late ratio | keyframe late ratio | decodable GOP ratio | on-time goodput ratio | wasted late bytes ratio | dropped |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 Mbps, RTT 10 ms | `deadline_feasible_frame_action` | 33294 | 204 | 0.006127 | 0.021261 | 0.977658 | 0.982636 | 0.017364 | 3 |
| 1 Mbps, RTT 10 ms | `frame_action_single_path` | 33294 | 222 | 0.006668 | 0.021622 | 0.977297 | N/A | N/A | 0 |
| 1 Mbps, RTT 10 ms | `heuristic_frame_aware` | 33294 | 508 | 0.015258 | 0.097658 | 0.902342 | N/A | N/A | 0 |
| 1 Mbps, RTT 50 ms | `deadline_feasible_frame_action` | 33294 | 2800 | 0.084099 | 0.709550 | 0.289369 | 0.751399 | 0.248601 | 24 |
| 1 Mbps, RTT 50 ms | `frame_action_single_path` | 11098 | 854 | 0.076951 | 0.709189 | 0.290811 | 0.756240 | 0.243760 | 0 |
| 1 Mbps, RTT 50 ms | `heuristic_frame_aware` | 33294 | 18602 | 0.558719 | 0.727928 | 0.002162 | 0.388885 | 0.611115 | 0 |
| 5 Mbps, RTT 10 ms | `deadline_feasible_frame_action` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 10 ms | `frame_action_single_path` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | N/A | N/A | 0 |
| 5 Mbps, RTT 10 ms | `heuristic_frame_aware` | 33294 | 0 | 0.000000 | 0.000000 | 1.000000 | N/A | N/A | 0 |
| 5 Mbps, RTT 50 ms | `deadline_feasible_frame_action` | 11098 | 2 | 0.000180 | 0.002162 | 0.997838 | 0.998685 | 0.001315 | 0 |
| 5 Mbps, RTT 50 ms | `frame_action_single_path` | 11098 | 0 | 0.000000 | 0.000000 | 1.000000 | 1.000000 | 0.000000 | 0 |
| 5 Mbps, RTT 50 ms | `heuristic_frame_aware` | 11098 | 5309 | 0.478374 | 0.001081 | 0.007568 | 0.644949 | 0.355051 | 0 |

## 해석

### 1. 실행 성공 여부

이번 배치 실행은 성공했다. 새로 수행된 4개 조건 모두 Mininet 실제 전송 로그, 이벤트 CSV, 요약 CSV가 일관된다.

### 2. `5 Mbps / RTT 50 ms` 결과

이 조건은 세 정책이 모두 이번 실행의 repeat 1 산출물이므로 직접 비교가 가능하다.

| policy | late frames | late ratio | keyframe late ratio | decodable GOP ratio | on-time goodput ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| `frame_action_single_path` | 0 / 11098 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |
| `deadline_feasible_frame_action` | 2 / 11098 | 0.000180 | 0.002162 | 0.997838 | 0.998685 |
| `heuristic_frame_aware` | 5309 / 11098 | 0.478374 | 0.001081 | 0.007568 | 0.644949 |

`frame_action_single_path`가 가장 깨끗하고, `deadline_feasible_frame_action`도 거의 완전한 수준이다. 반면 `heuristic_frame_aware`는 충분한 대역폭처럼 보이는 `5 Mbps`에서도 RTT가 50 ms로 증가하면 P-frame 지연이 크게 발생한다. 이는 cross-layer 적응 전송 정책이 기존 휴리스틱 전송보다 RTT 변화에 더 안정적이라는 근거가 된다.

다만 `deadline_feasible_frame_action`은 I-frame 925개 중 2개가 late였다. 비율은 작지만 GOP 복호 가능성 지표에는 바로 반영되므로, 최종 정책에서는 I-frame deadline 여유를 더 보수적으로 잡는 튜닝 여지가 있다.

### 3. `1 Mbps / RTT 50 ms` 결과

이 조건은 표면상 `frame_action_single_path`가 late ratio와 goodput에서 `deadline_feasible_frame_action`보다 약간 좋다.

- `frame_action_single_path`: late ratio `0.076951`, decodable GOP `0.290811`, on-time goodput `0.756240`
- `deadline_feasible_frame_action`: late ratio `0.084099`, decodable GOP `0.289369`, on-time goodput `0.751399`
- `heuristic_frame_aware`: late ratio `0.558719`, decodable GOP `0.002162`, on-time goodput `0.388885`

하지만 이 비교는 repeat 수가 다르다. `deadline_feasible_frame_action`과 `heuristic_frame_aware`는 repeat 3 집계이고, `frame_action_single_path`는 이번 실행의 repeat 1이다. repeat 1끼리만 보면 다음과 같다.

| policy | repeat | late frames | keyframe late ratio | decodable GOP ratio | on-time goodput ratio |
| --- | ---: | ---: | ---: | ---: | ---: |
| `frame_action_single_path` | 1 | 854 / 11098 | 0.709189 | 0.290811 | 0.756240 |
| `deadline_feasible_frame_action` | 1 | 933 / 11098 | 0.710270 | 0.288649 | 0.751572 |
| `heuristic_frame_aware` | 1 | 6201 / 11098 | 0.728649 | 0.002162 | 0.388770 |

현재 `deadline_feasible_frame_action`은 1 Mbps, RTT 50 ms의 강한 제약에서는 `frame_action_single_path`보다 낫다고 말하기 어렵다. 오히려 `UNRELIABLE`로 보낸 I-frame 410개가 모두 late였고, `RELIABLE_SINGLE` I-frame 515개 중 247개도 late였다. 이 조건에서는 TCP 고정도, UDP 전환도 I-frame deadline을 충분히 지키지 못했다.

### 4. `1 Mbps / RTT 10 ms` 결과

기존 repeat 3 산출물 기준으로는 `deadline_feasible_frame_action`이 가장 좋다.

- `deadline_feasible_frame_action`: late `204 / 33294`, decodable GOP `0.977658`
- `frame_action_single_path`: late `222 / 33294`, decodable GOP `0.977297`
- `heuristic_frame_aware`: late `508 / 33294`, decodable GOP `0.902342`

이 조건에서는 deadline-aware action 선택이 기존 frame action baseline보다 약간 개선된다. 효과는 크지 않지만 방향은 맞다.

## 결론

이번 결과는 `fast_1h` 배치가 실행 가능한 형태로 정리되었고, 실제 MP4와 Mininet 기반 산출물이 정상적으로 생성된 것을 보여준다.

정책 성능 측면에서는 다음처럼 정리된다.

- `heuristic_frame_aware`는 RTT 50 ms 조건에서 크게 무너진다.
- `deadline_feasible_frame_action`은 RTT 10 ms 또는 5 Mbps 조건에서는 안정적이다.
- 가장 어려운 `1 Mbps / RTT 50 ms` 조건에서는 `deadline_feasible_frame_action`이 아직 `frame_action_single_path`를 넘지 못한다.
- 병목은 전체 late frame 수보다 I-frame deadline miss다. I-frame late ratio가 약 `0.71`까지 올라가면서 decodable GOP ratio가 약 `0.29`로 떨어진다.

## 다음 확인

가장 먼저 repeat 수를 맞춰야 한다. 현재 노트북 결과는 기존 repeat 3과 신규 repeat 1이 섞여 있으므로, `1 Mbps / RTT 50 ms / loss 0%`에서 세 정책을 모두 repeat 3으로 다시 맞추는 것이 다음 판별 실험이다.

권장 실행 방향:

```powershell
# 노트북 설정에서 current_focus 또는 fast_1h를 사용하되,
# 1 Mbps / RTT 50 ms 조건의 세 정책이 모두 repeat 3으로 재생성되도록 설정한다.
# 기존 summary.csv 재사용을 피하려면 해당 조건만 별도 output으로 돌리거나 SKIP_EXISTING=False를 사용한다.
```

그 다음 정책 튜닝 축은 I-frame deadline 보호다. 단순히 I-frame을 TCP로 고정하는 방식은 RTT 50 ms, 1 Mbps에서 충분하지 않았으므로, deadline 여유가 부족한 I-frame을 어떻게 처리할지 별도 정책으로 분리해 검증해야 한다.
