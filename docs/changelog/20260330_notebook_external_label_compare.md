# 2026-03-30 — 노트북 외부 라벨 모델 비교 섹션 추가

## 변경 배경

기존 노트북은 baseline/ML-regression 비교 중심으로 구성되어 있었고,
새로 추가된 ΔQoE 라벨 기반 모델(`importance_rf_delta_qoe.pkl`)을
노트북 내에서 즉시 비교 확인하는 흐름이 없었다.

이번 변경에서는 노트북 하단에 외부 라벨 모델 비교 섹션을 추가해
라벨/모델 준비, 정책 비교, 산출물 저장을 한 번에 실행할 수 있도록 구성했다.

## 구현 내역

1. 노트북 섹션 추가
- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`
- 추가 셀:
  - Cell 11 (Markdown): `External Label Model Check`
  - Cell 12 (Code): ΔQoE 라벨/모델 아티팩트 준비
  - Cell 13 (Code): heuristic vs ML(bootstrap/delta) 정책 비교 테이블 생성
  - Cell 14 (Code): QoE/action 비교 그래프 생성 및 CSV/PNG 저장

2. 자동 생성/비교 흐름
- 라벨 파일 없으면 `build_delta_qoe_labels.py` 실행
- ΔQoE 모델 없으면 `train_importance_model.py`를 외부 라벨 모드로 실행
- `frame_action_adaptive`, `frame_action_ml_adaptive(bootstrap)`, `frame_action_ml_adaptive(delta_qoe)` 결과를 동일 시나리오에서 비교

3. 산출물
- `output/jupyter-notebook/assets/ml_label_model_comparison.csv`
- `output/jupyter-notebook/assets/ml_label_model_comparison.png`

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_notebook_external_label_compare.md`

### 변경
- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`

## 검증 결과

1. 노트북 파일 반영 검증
- 노트북 파일 내 신규 섹션/셀 마커 문자열 존재 확인
- `copilot_getNotebookSummary` 기준 Cell 11~14로 반영 확인

2. 실행 검증 참고
- 현재 커널 미선택 상태로 셀 실행 결과는 아직 없음
- 커널 선택 후 Cell 12 → Cell 13 → Cell 14 순서로 실행하면 산출물 생성 가능

## 영향 범위

- 코어 시뮬레이터 로직 변경 없음
- 분석 재현성 및 모델 비교 생산성 개선
