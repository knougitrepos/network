# deadline-aware keyframe guard 적용

작성일: 2026-05-11

## 배경

`keyframe reliable 보호 정책 추가` 이후 `archive_popeye_512kb / 1 Mbps / RTT 50 ms / loss 0% / repeat 3` 조건에서 keyframe late ratio가 `0.7091891891891892`까지 상승했다. I-frame을 무조건 `RELIABLE_SINGLE`로 보내는 hard guard가 TCP 지연을 키워 GOP 복호 가능성을 낮춘 것으로 해석된다.

## 변경 내용

- 보호 프레임도 deadline feasibility를 먼저 반영하도록 Stage B 규칙을 조정했다.
- `protected_frame`이 deadline 내 도착 가능하면 reliable action을 유지한다.
- `protected_frame`이 deadline 내 도착 불가능하면 drop하지 않고 `UNRELIABLE`로 전송한다.
- 중간 중요도와 낮은 중요도 보호 프레임 모두 infeasible 조건에서는 `UNRELIABLE`을 선택하는 회귀 테스트를 추가했다.
- feasible 보호 프레임은 계속 `RELIABLE_SINGLE`을 유지하는 테스트를 추가했다.

## 후속 확인

동일 조건인 `archive_popeye_512kb / deadline_feasible_frame_action / 1 Mbps / RTT 50 ms / loss 0% / repeat 3`을 다시 실행해 hard guard 결과와 비교해야 한다.
