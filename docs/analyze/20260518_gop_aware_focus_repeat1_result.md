# gop_aware_focus repeat 1 실행 결과 분석

작성일: 2026-05-18

## 실행 범위

- 노트북: `output/notebooks/mininet_actual_experiment_batch_runner.ipynb`
- batch log: `output/mininet_actual_experiment/batch_logs/batch_run_gop_aware_focus_20260518_023952.csv`
- preset: `gop_aware_focus`
- video: `archive_popeye_512kb`
- policy: `gop_aware_deadline_frame_action`
- bandwidth: `1 Mbps`
- RTT: `50 ms`
- loss: `0%`
- repeat: `1`

이번 노트북 출력 기준 `RUN_EXPERIMENTS=True`, `SKIP_EXISTING=False`, `REPEAT_COUNT=1`로 실행되었다.

## 완료 확인

이번 실행 job은 `completed`, return code `0`, elapsed `442.687 s`다.

주요 산출물:

- `output/mininet_actual_experiment/archive_popeye_512kb/gop_aware_deadline_frame_action/1mbps_rtt50ms_loss0pct/summary.csv`
- `output/mininet_actual_experiment/archive_popeye_512kb/gop_aware_deadline_frame_action/1mbps_rtt50ms_loss0pct/by_repeat_summary.csv`
- `repeat_01/client_events.csv`
- `repeat_01/server_events.csv`
- `repeat_01/client.log`
- `repeat_01/server.log`

`repeat_01` 기준:

- client events: `11098` rows
- server events: `4794` rows
- dropped by policy: `6304`
- `server rows + dropped = 11098`
- client log: `Client completed: policy=gop_aware_deadline_frame_action frames=11098`
- server log: `Server completed: received_frames=4794`

따라서 이번 repeat 1 실행 자체는 완료되었다. 서버 수신 프레임이 적은 것은 전송 실패가 아니라 GOP-aware 정책이 `6304`개 프레임을 DROP했기 때문이다.

## stale repeat 주의

같은 출력 디렉터리에 `repeat_02`, `repeat_03` 파일도 남아 있다. 하지만 이번 노트북 출력과 `by_repeat_summary.csv`는 repeat 1만 포함한다.

- `repeat_02`: 이전 실행 시도에서 남은 완료 산출물
- `repeat_03`: 이전 실행 시도에서 남은 실패 로그, `OSError: [Errno 101] Network is unreachable`

이번 결과 해석에는 `summary.csv`, `by_repeat_summary.csv`, `repeat_01`만 사용해야 한다.

## 요약 지표

| metric | value |
| --- | ---: |
| frame count | 11098 |
| late frame count | 6455 |
| late frame ratio | 0.581636 |
| keyframe late ratio | 0.709189 |
| decodable GOP ratio | 0.289730 |
| on-time goodput ratio | 0.911881 |
| wasted late bytes ratio | 0.088119 |
| dropped frame count | 6304 |
| reliable single count | 400 |
| unreliable count | 4394 |
| drop count | 6304 |
| reliable single late count | 131 |
| unreliable late count | 20 |

## action breakdown

| action | frames | received | dropped | late received |
| --- | ---: | ---: | ---: | ---: |
| `DROP` | 6304 | 0 | 6304 | 0 |
| `RELIABLE_SINGLE` | 400 | 400 | 0 | 131 |
| `UNRELIABLE` | 4394 | 4394 | 0 | 20 |

프레임 타입 기준:

| frame type | frames | received | dropped | late received |
| --- | ---: | ---: | ---: | ---: |
| I | 925 | 400 | 525 | 131 |
| P | 10173 | 4394 | 5779 | 20 |

## 비교 해석

동일 조건의 기존 repeat 3 집계와 단순 비교하면 안 되지만, 방향성은 명확하다.

| policy | repeat | late ratio | keyframe late ratio | decodable GOP ratio | on-time goodput ratio | wasted late bytes ratio | dropped |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `frame_action_single_path` | 3 | 0.076891 | 0.709189 | 0.290811 | 0.756275 | 0.243725 | 0 |
| `deadline_feasible_frame_action` | 3 | 0.083979 | 0.709189 | 0.289730 | 0.751598 | 0.248402 | 24 |
| `gop_aware_deadline_frame_action` | 1 | 0.581636 | 0.709189 | 0.289730 | 0.911881 | 0.088119 | 6304 |

`gop_aware_deadline_frame_action`은 decodable GOP ratio를 개선하지 못했다. keyframe late ratio도 기존 정책들과 같은 `0.709189` 수준이다. 즉 I-frame deadline miss 문제 자체는 아직 해결되지 않았다.

대신 전송 효율은 크게 바뀌었다. 기존 정책들이 늦게 도착하는 바이트를 계속 보낸 반면, GOP-aware 정책은 복호 가치가 낮다고 판단한 GOP의 I/P-frame을 대거 DROP하여 `wasted_late_bytes_ratio`를 `0.088119`까지 낮추고 `on_time_goodput_ratio`를 `0.911881`까지 높였다.

다만 현재 summary의 `late_frame_count`에는 DROP된 프레임도 on-time이 아닌 프레임으로 포함된다. 따라서 DROP을 많이 쓰는 정책에서는 late frame ratio 하나만으로 정책 품질을 판단하면 안 된다. `dropped_frame_count`, `decodable_gop_ratio`, `on_time_goodput_ratio`, `wasted_late_bytes_ratio`를 함께 봐야 한다.

## 결론

이번 repeat 1 결과에서 GOP-aware 개선 정책은 목표를 절반만 달성했다.

- 성공한 부분: 낭비되는 late byte를 크게 줄였다.
- 실패한 부분: keyframe late와 decodable GOP는 개선하지 못했다.

현재 정책은 “복호 불가능한 GOP에 쓰는 바이트를 줄이는 admission control”로는 작동하지만, “더 많은 GOP를 복호 가능하게 만드는 정책”으로는 아직 부족하다.

## 다음 확인

정책 품질 주장을 하려면 stale repeat 파일을 정리하거나 별도 output root를 사용해서 `gop_aware_deadline_frame_action / 1 Mbps / RTT 50 ms / repeat 3`을 깨끗하게 다시 실행해야 한다.

그 다음 비교는 repeat 3 기준으로 `frame_action_single_path`, `deadline_feasible_frame_action`, `gop_aware_deadline_frame_action`의 다음 지표를 함께 봐야 한다.

- `decodable_gop_ratio`
- `keyframe_late_ratio`
- `on_time_goodput_ratio`
- `wasted_late_bytes_ratio`
- `dropped_frame_count`
