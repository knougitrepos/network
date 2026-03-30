# 2026-03-30 — 노트북 산출물 자동 로딩 셀 추가

## 변경 배경

정책 리포트 CSV/PNG와 ΔQoE 라벨 CSV를 생성한 뒤,
노트북에서 매번 수동으로 파일 경로를 찾아 로딩하는 반복 작업이 있었다.

이번 변경에서는 노트북 하단에 자동 로딩 셀을 추가해
산출물 확인 과정을 즉시 재현 가능하게 만들었다.

## 구현 내역

1. 노트북 셀 추가
- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`
- 추가 셀:
  - markdown: `Artifact Auto Load`
  - code: `# cell 8 : 정책 산출물 CSV/이미지 자동 로딩`
  - code: `# cell 9 : ΔQoE 라벨 로딩 및 프레임 타입 통계`

2. 자동 로딩 동작
- repo root 자동 탐지
- 정책 산출물 로딩
  - `output/jupyter-notebook/assets/policy_action_summary.csv`
  - `output/jupyter-notebook/assets/policy_action_counts.png`
  - `output/jupyter-notebook/assets/policy_qoe_scatter.png`
- 라벨 산출물 로딩
  - `data/video-traces/bbb_720p_delta_qoe_labels.csv`
- 파일 누락 시 missing 경로 및 재생성 명령 안내 출력

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_notebook_artifact_autoload.md`

### 변경
- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`

## 검증 결과

1. 파일 생성 검증
- 정책 산출물 CSV/PNG 파일 존재 확인
- ΔQoE 라벨 CSV 존재 확인

2. 노트북 실행 검증 참고
- 노트북 커널이 선택되지 않은 상태에서는 셀 실행 완료를 자동 확인할 수 없음
- 커널 선택 후 신규 셀 2개를 순서대로 실행하면 산출물 미리보기가 가능

## 영향 범위

- 기존 시뮬레이터/정책/학습 로직에는 영향 없음
- 분석 생산성 및 재현성(산출 확인 단계) 개선
