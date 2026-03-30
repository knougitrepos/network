# 2026-03-30 — 정책 회귀 스모크 자동 검증 추가

## 변경 배경

Stage A/B 통합 및 ML 정책 확장 이후,
기본 정책 경로의 핵심 불변조건을 빠르게 확인할 자동 검증 스크립트가 필요했다.

이번 변경에서는 `fixed_hybrid`, `frame_action_adaptive`, `frame_action_ml_adaptive` 3개 정책을
한 번에 검사하는 회귀 스모크 스크립트를 추가했다.

## 구현 내역

1. 회귀 스모크 스크립트 추가
- `scripts/smoke_policy_regression.py`
- 검증 항목:
  - 결과 필수 컬럼 존재 여부
  - 주요 ratio(`mean_importance_score`, `dropped_frame_ratio`, `late_frame_ratio` 등) 범위 [0,1]
  - action count 합계와 프레임 수 일치 여부
  - 정책별 기본 불변조건
    - `fixed_hybrid`: `frame_action_mode == 0`
    - `frame_action_adaptive`: `importance_scorer_type == heuristic`
    - `frame_action_ml_adaptive`: model_path 유무에 따른 scorer type 검증

2. 실행 환경 호환성 보강
- `scripts/smoke_policy_regression.py`
- 직접 실행 시 `core.*`/`policy.*` import가 동작하도록 repo root를 `sys.path`에 추가했다.

3. 문서 반영
- `README.md`
- scripts 목록에 회귀 스모크 스크립트를 추가했다.
- 재현 명령 예시에 스모크 실행 커맨드를 추가했다.

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_policy_regression_smoke.md`
- `scripts/smoke_policy_regression.py`

### 변경
- `README.md`

## 검증 결과

1. 문법 검증
- `py -3 -m compileall scripts` 통과

2. 런타임 검증
- `py -3 scripts/smoke_policy_regression.py --trace data/video-traces/bbb_720p_trace.csv --model-path tmp/models/importance_rf.pkl`
- 3개 정책 경로 모두 검증 통과

## 영향 범위

- 기존 시뮬레이터/정책 로직은 변경하지 않는다.
- 정책 확장 이후 회귀 검증을 자동화해 추후 리팩터링 안정성을 높인다.
