# 2026-03-30 — 외부 ΔQoE 라벨 기반 학습 경로 추가

## 변경 배경

기존 `train_importance_model.py`는 heuristic 점수만 라벨로 사용해,
생성한 ΔQoE 라벨 CSV를 직접 학습에 사용할 수 없었다.

이번 변경에서는 외부 라벨 CSV를 입력받아
`delta_qoe_norm` 등 사용자 지정 컬럼으로 학습할 수 있게 확장했다.

## 구현 내역

1. 학습 스크립트 확장
- `scripts/train_importance_model.py`
- 신규 인자:
  - `--label-csv`: 외부 라벨 CSV 경로
  - `--label-column`: 라벨 컬럼명(기본 `delta_qoe_norm`)
- 동작:
  - trace events와 라벨 CSV를 `event_idx`로 병합
  - 누락 라벨 존재 시 오류로 중단
  - 라벨 모드 자동 추적:
    - 내부 라벨: `heuristic_bootstrap`
    - 외부 라벨: `external:<label_column>`

2. 메타데이터 확장
- 모델 메타 JSON에 아래 항목 추가
  - `label_csv`, `label_column`, `label_mode`

3. 문서 반영
- `README.md`
- ΔQoE 라벨 기반 학습 명령 예시 추가

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_train_with_external_labels.md`

### 변경
- `scripts/train_importance_model.py`
- `README.md`

## 검증 결과

1. 문법 검증
- `py -3 -m compileall scripts` 통과

2. 런타임 검증
- `py -3 scripts/train_importance_model.py --trace data/video-traces/bbb_720p_trace.csv --label-csv data/video-traces/bbb_720p_delta_qoe_labels.csv --label-column delta_qoe_norm --output tmp/models/importance_rf_delta_qoe.pkl`
- 모델/메타 파일 생성 확인
- 메타의 `label_mode=external:delta_qoe_norm` 확인

## 영향 범위

- 기존 heuristic bootstrap 학습 경로는 그대로 유지된다.
- 외부 라벨 기반 v2 학습 경로가 추가되어 라벨 고도화 실험을 바로 수행 가능하다.
