# 2026-03-31 노트북 정체성 정렬 및 실행 검증 보정

## 변경 배경

`output/jupyter-notebook/tcp-content-aware-batching.ipynb`가 연구를 단순 TCP batching 중심처럼 서술하고 있었고, 후반부 산출물 검토 셀과 외부 importance 모델 검증 셀도 현재 코드베이스 상태와 완전히 맞지 않았다.

특히 외부 ML importance 모델은 예전 11-feature schema로 저장되어 있었는데, 현재 추론 경로는 13-feature schema를 사용하고 있어 비교 셀이 heuristic fallback에 의존하는 문제가 있었다. 노트북을 실행하면 끝까지 돌아가더라도 결과 해석이 왜곡될 수 있어 보정이 필요했다.

## 구현 내역

- 첫 번째 마크다운 셀의 제목과 objective를 `cross-layer 적응 전송` 관점으로 수정
- `Experiment Scope`와 validation 서술을 baseline vs 연구 초점 구조로 정리
- 코드 셀 헤더를 `# cell N : ...` 형식으로 통일
- artifact review 셀이 현재 노트북이 실제로 생성하는 CSV/PNG만 점검하도록 수정
- external label model check 셀에 schema 불일치 감지 및 자동 재학습 로직 추가
- 저장된 `execution_count`와 `outputs`를 정리해 노트북 상태를 일관되게 정리

## 생성/변경 파일 목록

- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`
- `docs/analyze/20260331_notebook_alignment_and_validation.md`
- `docs/changelog/20260331_notebook_alignment_and_validation.md`
- 검증 실행으로 갱신된 산출물
- `output/jupyter-notebook/assets/reference_summary.csv`
- `output/jupyter-notebook/assets/fixed_sweep_results.csv`
- `output/jupyter-notebook/assets/oracle_selection.csv`
- `output/jupyter-notebook/assets/ml_eval_results.csv`
- `output/jupyter-notebook/assets/reference_policy_overview.png`
- `output/jupyter-notebook/assets/video_utility_comparison.png`
- `output/jupyter-notebook/assets/fixed_batch_heatmap.png`
- `output/jupyter-notebook/assets/policy_pareto_scatter.png`
- `output/jupyter-notebook/assets/oracle_vs_prediction_scatter.png`
- `output/jupyter-notebook/assets/ml_label_model_comparison.csv`
- `output/jupyter-notebook/assets/ml_label_model_comparison.png`
- `tmp/models/importance_rf.pkl`
- `tmp/models/importance_rf.meta.json`
- `tmp/models/importance_rf_delta_qoe.pkl`
- `tmp/models/importance_rf_delta_qoe.meta.json`

## 검증 결과

1. 정적 검증
- 노트북 JSON 파싱 성공
- 모든 코드 셀 컴파일 성공
- 코드 셀 헤더 형식 통일 확인

2. 실행 검증
- 노트북 top-to-bottom 실행 성공
- 외부 importance 모델 2종이 11-feature schema에서 13-feature schema로 자동 재학습됨
- `cell 12` ML 비교에서 기존 fallback warning이 발생하지 않음을 확인

3. 해석 관점 검증
- 고정 batching 정책은 baseline으로 남기고, 콘텐츠 중요도 기반 적응 전송이 중심이라는 서술로 정렬됨
- 외부 ML 비교가 더 이상 stale artifact에 의존하지 않도록 보정됨
