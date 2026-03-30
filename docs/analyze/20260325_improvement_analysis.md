# 2026-03-25 — 프로젝트 개선 포인트 분석

> Phase 1(초기 baseline) 시점에 작성. Phase 2에서 상당수 해결됨.

## 요약 테이블

| 영역 | 우선순위 | Phase 2 반영 |
|------|----------|-------------|
| `requirements.txt` 부재 | 높음 | **완료** |
| 테스트 코드 부재 | 높음 | 미완료 |
| 로깅 시스템 미적용 | 중간 | 미완료 |
| RL 환경 core 분리 | 높음 | **완료** (`FrameSchedulingEnv`) |
| trace 다양성 (BBB 1개) | 중간 | 미완료 |
| 코드 모듈화 (684줄 단일파일) | 중간 | **완료** (`core/`, `policy/`, `eval/`) |
| 동적 bandwidth 시나리오 | 중간 | 미완료 |
| 노트북 셀 번호 | 낮음 | 미완료 |

## 미해결 핵심 항목

### 테스트 코드 부재

- `tests/` 디렉토리 및 핵심 함수 단위 테스트 필요
- 참고: Wilson et al., "Best Practices for Scientific Computing", *PLOS Biology*, 2014

### 로깅 시스템

- `logging` 모듈 적용 필요 (사용자 규칙 4번)

### trace 다양화

- Sintel, Tears of Steel 등 다른 CC 영상 추가
- 다른 해상도(480p, 1080p), 다른 GOP 구조
- 참고: Duanmu et al., "Quality-of-Experience of Adaptive Video Streaming", *ACM MM 2017*

### 동적 대역폭 시나리오

- `TransportConfig`에 `bandwidth_trace` 필드 추가
- 참고: Riiser et al., "Commute Path Bandwidth Traces from 3G Networks", *MMSys 2013*

### Objective Score 검증

- 가중치 민감도 분석 추가 (±10% 변경 시 ranking 변화)
- 참고: Yin et al., "A Control-Theoretic Approach for Dynamic Adaptive Video Streaming", *SIGCOMM 2015*

### 시뮬레이션 한계 문서화

- TCP/QUIC congestion control 상세, packet loss/재전송은 추상화 수준임을 명시
- 참고: Cardwell et al., "BBR: Congestion-Based Congestion Control", *ACM Queue 2016*

## 실행 로드맵

### 완료된 항목

1. `requirements.txt` 생성
2. `rl/env.py` → `FrameSchedulingEnv` 재작성
3. 모듈 분리 (`core/`, `policy/`, `eval/`)

### 진행 중 (중요도 판단 방법론 확장)

4. ML 기반 importance scorer (v2) 도입
5. RL 기반 importance scorer (v3) 실험
6. heuristic/ML/RL 방법론 QoE 기여 비교 분석

### 예정 (품질 향상)

7. 동적 대역폭 시나리오
8. Objective Score 민감도 분석
9. 테스트 코드 / 로깅 / 노트북 셀 번호
