# output/notebooks 파일 설명

작성일: 2026-05-13

## 현재 보존한 노트북

| 파일 | 목적 |
| --- | --- |
| `mininet_actual_experiment_batch_runner.ipynb` | 실제 MP4 기반 Mininet 실험을 한 번에 실행하고, `summary.csv` 결과를 모아 정책별로 비교하는 기본 실행 노트북 |
| `descibe.md` | `output/` 아래 파일들이 어떤 실험 목적을 갖는지 설명하는 안내 문서 |

기존 `mininet_actual_experiment.ipynb`는 이전 단일 분석용 노트북이라 현재 batch runner와 역할이 겹쳐 삭제했다.

## 현재 노트북의 기본 실험 목적

현재 노트북 기본 preset은 `fast_1h`이다. 하루 단위 full matrix가 아니라 1~2시간 내외로 빠르게 정책 차이를 확인하는 것이 목적이다.

기본 설정은 다음과 같다.

- video: `archive_popeye_512kb`
- policy:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - `deadline_feasible_frame_action`
- bandwidth: `1 Mbps`, `5 Mbps`
- RTT: `10 ms`, `50 ms`
- loss: `0%`
- repeat: `1`
- condition 수: `12`
- Mininet repeat 수: `12`

노트북 파일의 기본값은 실수로 긴 실행이 시작되지 않도록 `RUN_EXPERIMENTS = False`이다. 실제 실행할 때만 노트북 첫 설정 셀에서 `RUN_EXPERIMENTS`를 `True`로 바꾼다.

```python
MATRIX_PRESET = "fast_1h"
RUN_EXPERIMENTS = False  # 실제 실행할 때만 True로 변경
SKIP_EXISTING = True
REPEAT_COUNT = 1
```

`SKIP_EXISTING = True`는 이미 존재하는 `summary.csv`를 다시 덮어쓰지 않기 위한 설정이다.

## output/mininet_actual_experiment 구조

실험 결과는 아래 구조로 저장된다.

```text
output/mininet_actual_experiment/<video>/<policy>/<condition>/
```

예시는 다음과 같다.

```text
output/mininet_actual_experiment/archive_popeye_512kb/deadline_feasible_frame_action/1mbps/
output/mininet_actual_experiment/archive_popeye_512kb/deadline_feasible_frame_action/1mbps_rtt50ms_loss0pct/
```

condition 이름 규칙은 다음과 같다.

- `1mbps`: 기본 조건인 `RTT 10 ms / loss 0%`
- `1mbps_rtt50ms_loss0pct`: `RTT 50 ms / loss 0%`

## 각 결과 파일의 의미

| 파일 또는 폴더 | 의미 | 노트북 집계에 필요한가 |
| --- | --- | --- |
| `summary.csv` | 해당 condition의 repeat 전체를 합친 최종 요약 결과 | 예 |
| `by_repeat_summary.csv` | repeat별 요약 결과 | 분석 보강 시 필요 |
| `repeat_XX/summary.csv` | 특정 repeat 하나의 요약 결과 | 검증 시 필요 |
| `repeat_XX/client_events.csv` | 실제 송신 이벤트, 선택 action, 송신 시각, drop 여부 | 검증 시 필요 |
| `repeat_XX/server_events.csv` | 실제 수신 이벤트와 수신 시각 | 검증 시 필요 |
| `repeat_XX/client.log` | client 실행 로그 | 실패 원인 확인 시 필요 |
| `repeat_XX/server.log` | server 실행 로그 | 실패 원인 확인 시 필요 |
| `repeat_XX/client_finished.flag` | client 종료를 server에 알리는 내부 플래그 | 직접 분석 대상 아님 |

노트북의 표 집계는 주로 `summary.csv`만 읽는다. 다만 결과 신뢰성 확인에는 `by_repeat_summary.csv`, `client_events.csv`, `server_events.csv`, 로그가 필요하다.

## 현재 남겨둔 결과 범위

현재 `output/mininet_actual_experiment/`에는 `fast_1h` preset과 직접 관련된 결과만 남겼다.

남아 있는 완료 조건은 다음과 같다.

| video | policy | condition | 목적 |
| --- | --- | --- | --- |
| `archive_popeye_512kb` | `heuristic_frame_aware` | `1mbps` | heuristic batching baseline, 기본 RTT |
| `archive_popeye_512kb` | `heuristic_frame_aware` | `5mbps` | 쉬운 대역폭 조건 baseline |
| `archive_popeye_512kb` | `heuristic_frame_aware` | `1mbps_rtt50ms_loss0pct` | RTT 증가 baseline |
| `archive_popeye_512kb` | `frame_action_single_path` | `1mbps` | 기존 frame action baseline, 기본 RTT |
| `archive_popeye_512kb` | `frame_action_single_path` | `5mbps` | 쉬운 대역폭 조건 baseline |
| `archive_popeye_512kb` | `deadline_feasible_frame_action` | `1mbps` | 신규 정책, 가장 중요한 기본 스트레스 조건 |
| `archive_popeye_512kb` | `deadline_feasible_frame_action` | `5mbps` | 신규 정책, 쉬운 대역폭 조건 |
| `archive_popeye_512kb` | `deadline_feasible_frame_action` | `1mbps_rtt50ms_loss0pct` | 신규 정책, RTT 증가 스트레스 조건 |

아직 없는 빠른 preset 조건은 노트북 실행 시 생성된다.

- `frame_action_single_path / 1mbps_rtt50ms_loss0pct`
- `frame_action_single_path / 5mbps_rtt50ms_loss0pct`
- `heuristic_frame_aware / 5mbps_rtt50ms_loss0pct`
- `deadline_feasible_frame_action / 5mbps_rtt50ms_loss0pct`

## 삭제한 파일 범위

정리 과정에서 다음 범위는 현재 빠른 노트북 실험과 직접 관련이 낮아 삭제했다.

- 과거 고대역폭 조건인 `10mbps`, `30mbps`
- 현재 빠른 preset에 포함되지 않는 `2mbps`, `3mbps`, loss `1%/3%`, RTT `100ms` 조건
- `echo_mediaelement`, `w3c_movie_300`의 이전 산출물
- 이전 단일 분석 노트북 `output/notebooks/mininet_actual_experiment.ipynb`

필요하면 이 조건들은 다시 실행할 수 있지만, 현재 목표는 빠른 1~2시간 검증이므로 기본 출력에서는 제외했다.

## full preset 사용 시 주의

`full` preset은 3개 비디오, 3개 정책, 4개 bandwidth, 3개 RTT, 3개 loss 조합이다. 총 `324` condition이고 repeat까지 고려하면 매우 오래 걸린다. 하루 이상 걸릴 수 있으므로, 최종 논문용 대규모 실험을 실행할 때만 사용한다.
