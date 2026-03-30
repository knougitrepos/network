# 2026-03-30 — 정책 action/QoE 요약 리포트 산출 스크립트 추가

## 변경 배경

`frame_action_adaptive`/`frame_action_ml_adaptive` 정책 비교를 반복할 때,
노트북 수동 작업 없이 핵심 지표와 action 분포를 즉시 확인할 산출 자동화가 필요했다.

이번 변경에서는 정책 3종을 실행해 CSV와 그래프를 동시에 생성하는
리포트 스크립트를 추가했다.

## 구현 내역

1. 리포트 스크립트 추가
- `scripts/export_policy_action_report.py`
- 실행 정책:
  - `fixed_hybrid`
  - `frame_action_adaptive`
  - `frame_action_ml_adaptive`
- 산출물:
  - 요약 CSV (`policy_action_summary.csv`)
  - action count bar plot (`policy_action_counts.png`)
  - QoE scatter (`policy_qoe_scatter.png`)

2. 문서 반영
- `README.md`
- scripts 목록에 리포트 스크립트 추가
- 재현 명령 예시에 실행 커맨드 추가

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_policy_action_report_export.md`
- `scripts/export_policy_action_report.py`

### 변경
- `README.md`

## 검증 결과

1. 문법 검증
- `py -3 -m compileall scripts` 통과

2. 런타임 검증
- `py -3 scripts/export_policy_action_report.py --trace data/video-traces/bbb_720p_trace.csv --model-path tmp/models/importance_rf.pkl`
- CSV/PNG 3개 파일 생성 확인

## 영향 범위

- 시뮬레이터/정책 로직 변경 없이 분석 산출 자동화만 추가된다.
- 노트북 외부에서도 정책 비교 리포트를 재현 가능하게 한다.
