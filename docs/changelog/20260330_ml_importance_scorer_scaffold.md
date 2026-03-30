# 2026-03-30 — MLImportanceScorer 스캐폴딩 및 시뮬레이터 연결

## 변경 배경

Stage A의 v2(ML 기반 중요도 스코어링)를 실험하려면,
기존 heuristic scorer를 코드 수정 없이 교체 가능한 경로가 필요했다.

이번 변경에서는 ML 모델 파일(pickle) 로딩과 추론 인터페이스를 추가하고,
`run_simulation()`에서 신규 정책으로 ML scorer를 선택할 수 있도록 연결했다.

## 구현 내역

1. Stage A v2 스캐폴딩 추가
- `policy/importance.py`
- `MLImportanceScorer` 클래스 추가
  - `model_path` 기반 pickle 모델 로딩 (`load_model()`)
  - 프레임/네트워크 기반 feature vector 구성 (`_build_features()`)
  - `predict_proba` 또는 `predict` 추론 지원
  - 모델 미로딩 또는 추론 실패 시 heuristic scorer로 폴백

2. 정책 설정 확장
- `policy/legacy.py`
- `PolicyConfig`에 `model_path` 필드 추가
- `resolve_policy()`에 `frame_action_ml_adaptive` 정책 추가

3. 시뮬레이터 연결
- `core/simulator.py`
- frame action 모드가 `frame_action_ml_adaptive`일 경우 `MLImportanceScorer` 선택
- ML 모델 미지정/초기화 실패 시 heuristic fallback 사용
- 결과 컬럼 `importance_scorer_type` 추가
  - `ml`, `ml_fallback_heuristic`, `heuristic`, `heuristic_fallback`, `none`

4. 문서 반영
- `README.md`
- 정책 목록에 `frame_action_ml_adaptive` 추가
- Frame-aware 섹션에 `MLImportanceScorer` 및 `importance_scorer_type` 설명 추가

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_ml_importance_scorer_scaffold.md`

### 변경
- `policy/importance.py`
- `policy/legacy.py`
- `core/simulator.py`
- `README.md`

## 검증 결과

1. 문법/정적 검증
- `py -3 -m compileall core policy` 실행
- `core/`, `policy/` 컴파일 성공

2. 런타임 스모크(ML 정책, 모델 미지정)
- `PolicyConfig(name='frame_action_ml_adaptive', available_paths=2)`로 `run_simulation()` 실행
- `importance_scorer_type='ml_fallback_heuristic'` 반환 확인
- action count / importance / drop 메트릭 컬럼 정상 반환 확인

## 영향 범위

- 기존 정책 경로는 유지된다.
- 신규 정책 선택 시에만 ML scorer 경로가 활성화된다.
- v2 실험은 모델 학습 파일 준비 후 `model_path` 지정만으로 바로 연결 가능하다.
