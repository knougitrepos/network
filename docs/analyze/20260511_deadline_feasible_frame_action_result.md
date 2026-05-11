# deadline_feasible_frame_action 1차 결과 비교

작성일: 2026-05-11

## 검토 범위

- 비디오: `archive_popeye_512kb`
- 정책:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - `deadline_feasible_frame_action`
- 조건: RTT `10 ms`, loss `0%`
- bandwidth: `1`, `2`, `3`, `5 Mbps`

## 완료 상태

`deadline_feasible_frame_action`은 `1`, `2`, `3`, `5 Mbps`에서 repeat 3 집계가 완료되었다. 따라서 `archive_popeye_512kb / RTT 10 ms / loss 0%` 기준 최소 matrix는 완결되었다.

## 1 Mbps 핵심 비교

| 정책 | 반복 | late frame | late ratio | keyframe late ratio | decodable GOP ratio | useful goodput bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `heuristic_frame_aware` | 3 | 508 / 33294 | 0.015258 | 0.097658 | 0.902342 | 67,881,345 |
| `frame_action_single_path` | 3 | 222 / 33294 | 0.006668 | 0.021622 | 0.977297 | 70,037,742 |
| `deadline_feasible_frame_action` | 3 | 204 / 33294 | 0.006127 | 0.021261 | 0.977658 | 70,091,292 |

신규 정책은 1 Mbps에서 기존 `frame_action_single_path` 대비 late frame을 `222 -> 204`로 줄였다. 개선폭은 크지 않지만, repeat 3 집계 기준으로 일관되게 낮다. `heuristic_frame_aware` 대비로는 late frame이 `508 -> 204`로 크게 줄었다.

## bandwidth별 요약

| bandwidth | heuristic late | frame action late | deadline feasible late | 판단 |
| ---: | ---: | ---: | ---: | --- |
| 1 Mbps | 508 / 33294 | 222 / 33294 | 204 / 33294 | 신규 정책이 가장 낮음 |
| 2 Mbps | 56 / 33294 | 0 / 33294 | 0 / 33294 | frame action 계열 둘 다 0 |
| 3 Mbps | 0 / 33294 | 0 / 33294 | 0 / 33294 | 모두 0 |
| 5 Mbps | 0 / 33294 | 0 / 33294 | 0 / 33294 | 모두 0 |

## 신규 byte/action 지표

`deadline_feasible_frame_action / 1 Mbps / repeat 3` 기준:

- `sent_bytes`: 71,329,878
- `on_time_bytes`: 70,091,292
- `late_bytes`: 1,238,586
- `dropped_bytes`: 29,751
- `wasted_late_bytes_ratio`: 0.017364
- `on_time_goodput_ratio`: 0.982636
- `reliable_single_count`: 2,481
- `unreliable_count`: 30,810
- `drop_count`: 3
- `dropped_keyframe_count`: 0

DROP은 repeat마다 P-frame 1개씩 총 3개 발생했고, keyframe drop은 없었다.

## 해석

현재 신규 정책은 실험 경로와 집계 지표가 정상 동작함을 보였다. 1 Mbps에서는 기존 `frame_action_single_path`보다 late frame이 약간 줄었다. 다만 개선폭은 제한적이므로, 논문에서는 “큰 성능 향상”보다는 “deadline feasibility를 명시적으로 반영했을 때 저대역폭에서 late frame과 useful goodput이 소폭 개선됨” 정도로 쓰는 것이 안전하다.

현재 가장 중요한 약점은 일부 I-frame이 `UNRELIABLE`로 선택되어 late가 발생한다는 점이다. 다음 정책 튜닝에서는 keyframe/I-frame을 더 강하게 보호하는 조건을 검토할 필요가 있다.

## 다음 절차

1. 단위 테스트와 `compileall`, CLI help 검증을 다시 수행한다.
2. 현재 구현 변경을 커밋한다.
3. 노트북 또는 별도 집계 스크립트에 신규 byte/action 지표를 표시한다.
4. 이후 선택지:
   - 정책 튜닝: I-frame은 가능하면 `UNRELIABLE`로 보내지 않도록 보호 강화
   - 실험 확장: RTT `50/100 ms`, loss `1/3%` 조건 추가
