# 연관논문 3편 기반 프로젝트 방향 정렬 분석

> 작성일: 2026-03-31

## 분석 배경

연관논문 3편(Tüker 2024, Grazia 2021, Borisov 2025)과 현재 프로젝트 코드/연구 방향의 정합성을 분석하고, 방향 수정 사항을 도출하였다.

## 핵심 발견

### 기존 문제: 연구 정체성과 연관논문 간의 긴장

- 연관논문 3편 중 2편(Grazia, Borisov)이 TCP 전송 계층 메커니즘을 다루고 있으나, 프로젝트는 "TCP batching 연구가 아니다"라고 선언되어 있었음
- 이 긴장을 해소하기 위해 연구 정체성을 **재정의**

### 해결: "cross-layer 적응 전송 연구"로 재정의

- "TCP batching이 아니다" → "**단순** TCP batching 최적화가 아니다"로 수정
- 3편 논문의 역할을 명시적으로 구조화:
  - Tüker 2024: 콘텐츠 중요도(content-aware) 축의 선행 연구
  - Grazia 2021: TCP 전송 계층 latency 메커니즘의 이론적 근거
  - Borisov 2025: adaptive batching 필요성의 근거(E2E 성능 추정)
- Research Gap: "콘텐츠 중요도를 전송 계층 결정에 ML/RL로 통합하는 시스템"이 부재

### 실행한 변경

1. `docs/research_goal.md` 전면 갱신 (연관논문 3편 위치 명시, 실험 비교 3그룹 구조, 발표용 문구 수정)
2. `AGENTS.md` 연구 정체성 섹션 수정 (cross-layer 적응 전송, 연관논문 역할 명시)

## 후속 코드 수정 권고 (미실행)

1. `NetworkState`에 동적 추정값(estimated RTT/bw) 반영
2. `select_action()` 입력에 queue/batch 상태 추가
3. ML scorer feature importance 분석 추가
4. 다양한 네트워크 조건(RTT/loss/bw 조합)에서 3그룹 비교 실험

## 참고 논문

- Tüker et al. (2024) "Using Packet Trimming at the Edge for In-Network Video Quality Adaption"
- Grazia et al. (2021) "The New TCP Modules on the Block: TCP Pacing & TCP Small Queues", IEEE Access, Vol.9
- Borisov, Amit, Tsafrir (2025) "Batching with End-to-End Performance Estimation", HotOS '25
