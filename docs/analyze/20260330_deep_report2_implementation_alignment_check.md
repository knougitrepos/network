# 2026-03-30 deep_report2_implementation_alignment_check

## 요청

- 대상 문서: deep-research-report (2).md
- 목적: 현재 프로젝트 코드 구현 상태와 보고서 내용의 정합성 점검

## 판정

- 결론: 방향성은 대체로 맞지만, 구현 상태 서술 중 핵심 2개가 최신 코드 대비 구버전 기준으로 작성되어 부분적으로 부정확하다.

## 주요 불일치 (핵심)

1. ML 파이프라인 부재 주장
- 보고서: "현재 가장 큰 공백은 학습 가능한 ML 중요도 스코어러의 실제 파이프라인" / "v2(ML)의 데이터/라벨/학습/검증이 코드로 제공되지 않는다."
- 실제 코드: 외부 라벨 학습 경로와 학습 스크립트가 존재한다.
  - scripts/train_importance_model.py: --label-csv, --label-column, external:<label_column>
  - scripts/build_delta_qoe_labels.py: delta_qoe_norm 라벨 생성
  - README.md: 위 스크립트 실행 예시 문서화
- 판단: "완전 부재" 표현은 부정확. 다만 실측 VMAF 기반 고도화가 남아 있다는 표현은 타당.

2. Simulator에서 FrameAction 미반영/legacy 우세 주장
- 보고서: run_simulation이 legacy batch/flush 중심이며 FrameAction 반영 리팩토링이 최우선이라고 서술.
- 실제 코드: frame_action_adaptive / frame_action_ml_adaptive 경로가 run_simulation에 이미 연결되어 있다.
  - core/simulator.py: frame_action_mode 분기, MLImportanceScorer 선택, action 카운트/드롭/importance 메트릭 반환
  - policy/legacy.py: frame_action_adaptive, frame_action_ml_adaptive 정책 해석 추가
- 판단: 현재 구현 기준으로는 "미반영" 서술이 부정확.

## 정확한 서술 (유지 가능)

- Stage A/B 구조 분리 및 행동 공간(FrameAction) 존재
- QUIC DATAGRAM/멀티패스 스케줄링이 연구 기여 지점이라는 문제정의
- proxy 지표를 실측 지표로 고도화해야 한다는 방향

## 권고 수정 문구

- "ML 파이프라인이 없다" -> "bootstrap/외부 라벨 기반 파이프라인은 구현되었고, 실측 VMAF/SSIM 기반 라벨 고도화가 남아 있다."
- "FrameAction이 simulator에 미반영" -> "FrameAction 경로는 simulator에 반영되었고, 향후에는 정책 고도화와 실환경 검증(Mininet/LTE-WiFi)으로 확장한다."

## 참고

- 본 문서는 구현 정합성 점검 기록이며, 기존 deep-research-report (2).md 원문은 수정하지 않았다.
