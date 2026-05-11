# keyframe reliability guard 추가

작성일: 2026-05-11

## 배경

`deadline_feasible_frame_action / archive_popeye_512kb / 1 Mbps / RTT 50 ms / loss 0%` 실험에서 I-frame 대부분이 `UNRELIABLE`로 선택되었고, `keyframe_late_ratio`가 0.681081까지 상승했다. 이는 GOP 복호 가능성을 크게 낮추므로 deadline feasibility 정책의 Stage B에서 keyframe 보호가 필요하다.

## 변경 내용

- `select_deadline_feasible_action()`에 `protected_frame` 인자를 추가했다.
- 보호 프레임은 deadline feasibility가 낮더라도 `UNRELIABLE`이나 `DROP`으로 낮추지 않고 reliable action을 선택한다.
- Mininet endpoint에서는 `key_frame == 1` 또는 `frame_type == "I"`인 프레임을 보호 대상으로 전달한다.
- 보호 프레임이 중간 중요도이면서 deadline 내 도착 불가능한 경우에도 `RELIABLE_SINGLE`을 유지하는 단위 테스트를 추가했다.

## 후속 확인

동일 조건인 `archive_popeye_512kb / deadline_feasible_frame_action / 1 Mbps / RTT 50 ms / loss 0% / repeat 3`을 다시 실행해 keyframe late와 decodable GOP 변화량을 확인해야 한다.
