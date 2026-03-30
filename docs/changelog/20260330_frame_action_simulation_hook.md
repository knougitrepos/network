# 2026-03-30 — frame_action_adaptive 시뮬레이터 연결 구현

## 변경 배경

Stage A(`HeuristicImportanceScorer`)와 Stage B(`select_action`)가 `core/simulator.py` 기본 실행 경로에 직접 연결되지 않아,
프레임 단위 의사결정(importance/action)이 시뮬레이션 결과에 어떻게 반영되는지 추적하기 어려웠다.

이번 변경에서는 기존 정책 경로를 유지한 채, 신규 정책 `frame_action_adaptive`를 통해
프레임별 의사결정과 결과 메트릭을 함께 관찰할 수 있는 최소 구현을 추가했다.

## 구현 내역

1. 정책 확장
- `policy/legacy.py`
- `PolicyConfig`에 `available_paths` 필드를 추가했다. (기본값 1)
- `resolve_policy()`에 `frame_action_adaptive` 정책을 추가했다.

2. 시뮬레이터 Stage A/B 연결
- `core/simulator.py`
- `frame_action_adaptive` 정책일 때 아래 로직을 활성화한다.
  - 프레임별 중요도 계산: `HeuristicImportanceScorer`
  - 행동 선택: `select_action(importance, deadline_slack, network, available_paths)`
  - `DROP` 선택 시 큐에 넣지 않고 프레임 레코드에 dropped 상태를 기록
  - `RELIABLE_MULTI`/`DUPLICATE` 또는 매우 촉박한 `RELIABLE_SINGLE`은 즉시 flush
  - `DUPLICATE`는 `available_paths > 1`일 때 전송 바이트를 2배로 반영
- flush 계산 시 `payload_bytes` 대신 `tx_payload_bytes`(실제 전송량)를 사용한다.

3. 결과 메트릭 확장
- `run_simulation()` 반환값에 다음 항목을 추가했다.
  - `frame_action_mode`, `available_paths`
  - `mean_importance_score`
  - `dropped_frame_count`, `dropped_frame_ratio`
  - `action_reliable_single_count`, `action_reliable_multi_count`
  - `action_unreliable_count`, `action_duplicate_count`, `action_drop_count`

4. 문서 반영
- `README.md` 정책 목록에 `frame_action_adaptive`를 추가했다.
- Frame-aware 섹션에 신규 정책의 역할(Stage A/B 추적 연결)을 설명했다.

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_frame_action_simulation_hook.md`

### 변경
- `policy/legacy.py`
- `core/simulator.py`
- `README.md`

## 검증 결과

아래 스모크 테스트를 로컬에서 실행해 정상 동작을 확인했다.

1. 신규 정책 실행 확인
- 명령: `py -3` 인라인 스크립트로 `PolicyConfig(name='frame_action_adaptive', available_paths=2)` 실행
- 결과 요약:
  - `policy='frame_action_adaptive'`
  - `frame_action_mode=1`
  - `mean_importance_score=0.12400000000000001`
  - `action_reliable_single_count=6`
  - `action_reliable_multi_count=2`
  - `action_unreliable_count=292`
  - `late_frame_ratio=0.013333333333333334`

2. 기존 정책 회귀 확인
- 명령: `PolicyConfig(name='fixed_hybrid', batch_bytes=8192, flush_interval_ms=8.0)` 실행
- 결과 요약:
  - `policy='fixed_hybrid'`
  - `frame_action_mode=0`
  - `flush_count=300`

## 영향 범위

- 기존 정책(`immediate`, `fixed_*`, `heuristic_frame_aware`, `ml_regression_adaptive`) 동작 경로는 유지된다.
- 신규 정책 선택 시에만 Stage A/B 기반 프레임 행동 로직이 활성화된다.
- 결과 테이블 컬럼이 확장되므로, 후속 분석 노트북에서 신규 컬럼을 활용한 시각화가 가능하다.
