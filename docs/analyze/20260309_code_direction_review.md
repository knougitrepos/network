# 2026-03-09 — 코드 방향성 평가

> 프로젝트 초기(Phase 1) 시점의 코드 방향성 평가 기록이다.

## 종합 평가

진행 방향성은 타당하다. Policy Learning / Adaptive Control 문제로 정의한 것은 프레임 중요도 기반 전송 의사결정 방식과 정확히 일치한다.

## Heuristic → ML → RL 로드맵 평가

- **Heuristic (v1)**: H.264 I/P/B 프레임 타입, deadline slack, GOP 위치 등 도메인 지식 기반 규칙 스코어링
- **ML (v2)**: 프레임 특성 + 네트워크 상태로 중요도를 예측하는 경량 ML (RandomForest, GBM)
- **RL (v3)**: 프레임 스케줄링 환경에서 QoE 보상을 극대화하는 중요도 판단 정책 학습

이 3단계 파이프라인은 복잡한 시스템 제어 문제를 풀 때 논문에 제시하기 가장 이상적인 형태다.

## 코드 구현 평가

### 강점

1. `WorkloadConfig`/`PolicyConfig`을 `dataclass`로 분리 — Feature Engineering 및 확장 용이
2. `static_file`/`dynamic_stream` 워크로드 특성을 각기 다르게 설계

### 개선 권고

1. **Edge Case 방어 코드**: `latencies`/`batch_sizes` 배열이 빈 경우 `NaN` 방지 필요
2. **시뮬레이션 한계 명시**: Application 계층 중심 간소화 시뮬레이션임을 Limitations에 서술
3. **노트북 셀 번호 표기**: 사용자 규칙(셀 상단에 `# cell N : 목적`) 미반영

## 참고문헌 권장

- TCP Nagle 알고리즘과 Delayed ACK 충돌로 인한 Latency Spike 연구들을 Background에 포함 권장
