# 연구 목표

최종 갱신: 2026-04-09

## 현재 방향

- 본 연구는 콘텐츠 중요도와 전송 계층 결정을 통합하는 `cross-layer 적응 전송` 연구다.
- 현재 after-mid 단계의 초점은 시뮬레이터 설명이 아니라 실제 비디오 기반 Mininet 실험으로 전환하는 것이다.
- 특히 `P` 프레임 비중이 높고 평균 payload가 작은 비디오에서 `5 Mbps`에서는 0처럼 보이던 지표가 `1~3 Mbps`에서 어떻게 미세하게 변하는지 관찰하는 것이 우선 과제다.

## 즉시 수행할 일

1. 실제 비디오에서 frame trace와 실제 payload를 추출하는 공통 모듈 정리
2. Mininet client/server 실제 전송 경로 구현
3. `heuristic_frame_aware`, `frame_action_single_path` 두 정책만 남겨 단일 경로 실험 정리
4. 이벤트 CSV, 요약 CSV, 노트북 분석 경로 고정

## 실험 원칙

- 실험 입력은 실제 MP4만 허용
- trace CSV는 원본 비디오 기반 캐시만 허용
- `late_frame_ratio`는 항상 `late_frame_count / frame_count`와 함께 제시
- 환경 미충족 시 대체 모드 없이 실패

## 후속 확장

- single-path 실험 안정화 후 multipath 실제 실험 검토
- heuristic 이후 ML/RL scorer 실험 재도입 여부 판단
