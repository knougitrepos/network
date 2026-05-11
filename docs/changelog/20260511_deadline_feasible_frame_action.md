# deadline feasible frame action 구현

작성일: 2026-05-11

## 변경 내용

- `deadline_feasible_frame_action` 정책을 신규 단일 경로 정책으로 추가했다.
- Stage A 중요도 점수에 payload 비용과 GOP/keyframe 보호 신호를 반영했다.
- Stage B에 예상 완료 시각 기반 feasibility-first action 선택 함수를 추가했다.
- Mininet 실제 실험 출력 경로가 RTT/loss 조건별로 충돌하지 않도록 조건 디렉터리 이름을 분리했다.
- summary CSV에 sent/on-time/late/drop byte와 action별 count/late count 지표를 추가했다.
- 단위 테스트를 추가해 신규 정책, 실험 matrix, 요약 지표를 검증한다.

## 유지한 원칙

- mock, synthetic, fallback, dummy 데이터 경로는 추가하지 않았다.
- 실제 Mininet 실행 조건은 기존처럼 WSL2 Ubuntu, root 권한, ffprobe, PyAV, Mininet을 요구한다.
- GRACE/FEC 결합은 구현하지 않고 후속 확장으로 남겼다.
