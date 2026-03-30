# 2026-03-30 — ML 중요도 모델 학습/저장 파이프라인 추가

## 변경 배경

`frame_action_ml_adaptive` 정책을 실제로 사용하려면,
`model_path`로 전달할 학습 모델 산출 경로가 필요했다.

이번 변경에서는 Stage A v2의 초기 실험을 위해
heuristic 점수를 모사하는 bootstrap 학습 스크립트를 추가했다.

## 구현 내역

1. 공용 feature builder 추가
- `policy/importance.py`
- `build_importance_features()`를 추가하여 학습/추론 feature 순서를 통일했다.
- `MLImportanceScorer`는 내부 feature 구성을 공용 함수 호출로 변경했다.
- Python 3.9 호환을 위해 `str | None` 타입 표기를 `Optional[str]`로 수정했다.

2. 학습 스크립트 추가
- `scripts/train_importance_model.py`
- 입력 trace CSV로부터 학습 데이터셋 구성
- 라벨은 현재 `HeuristicImportanceScorer` 출력값을 사용 (`label_mode=heuristic_bootstrap`)
- 모델: `RandomForestRegressor`
- 산출물:
  - 모델 pickle (`--output`)
  - 메타데이터 JSON (`--meta-output`, 미지정 시 `.meta.json`)

3. 문서 반영
- `README.md`
- `scripts/` 목록에 `train_importance_model.py` 추가
- 재현 방법에 학습 명령 예시 추가
- `frame_action_ml_adaptive`에서 `PolicyConfig(model_path=...)` 사용법 추가

## 생성/변경 파일 목록

### 생성
- `scripts/train_importance_model.py`
- `docs/changelog/20260330_ml_model_training_bootstrap.md`

### 변경
- `policy/importance.py`
- `README.md`

## 검증 결과

1. 문법 검증
- `py -3 -m compileall core policy scripts` 통과

2. 학습 스모크
- `py -3 scripts/train_importance_model.py --trace data/video-traces/bbb_720p_trace.csv --output tmp/models/importance_rf.pkl`
- 모델 파일 및 메타데이터 JSON 생성 확인

3. 시뮬레이터 연동 스모크
- `PolicyConfig(name='frame_action_ml_adaptive', model_path='tmp/models/importance_rf.pkl')` 실행
- `importance_scorer_type='ml'` 반환 확인

## 영향 범위

- 기존 정책 동작은 변경되지 않는다.
- ML 정책 실험이 "학습 → 저장 → model_path 연결" 흐름으로 즉시 가능해졌다.
- 현재 라벨은 bootstrap용이므로, 후속 단계에서 ΔQoE 라벨 생성 파이프라인으로 교체가 필요하다.
