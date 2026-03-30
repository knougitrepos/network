# cross-layer 적응 전송 코드 구현 (연관논문 3편 통합)

> 변경일: 2026-03-31

## 변경 배경

연관논문 3편(Tüker 2024, Grazia 2021, Borisov 2025)의 관점을 코드에 통합하여
"cross-layer 적응 전송" 연구 정체성을 코드 수준에서 실현.

보고서(`research_direction_advice.md`) §3.4의 코드 수정 권고 사항을 반영.

## 구현 내역

### 1. `policy/importance.py` — NetworkState 확장 + feature vector 13차원화

- `NetworkState`에 cross-layer 확장 필드 추가:
  - `queue_bytes: int = 0` — 현재 배칭 큐에 쌓인 바이트 수
  - `estimated_batch_gain: float = 0.0` — 배칭으로 인한 예상 throughput 향상률
- `build_importance_features()` 출력을 11→13차원으로 확장
  - 기존 11피처 + `queue_bytes` + `estimated_batch_gain`
- 기본값 0.0으로 하위 호환성 유지

### 2. `policy/action.py` — select_action() cross-layer 배칭 유보 로직

- `select_action()`에 `queue_bytes`, `estimated_batch_gain` 파라미터 추가
- **cross-layer 배칭 유보 규칙** 신설:
  - `estimated_batch_gain >= 15%` AND `deadline_slack > RTT*3` AND 중간 중요도 → RELIABLE_SINGLE (flush 유보)
  - 이는 Borisov(2025)의 "배칭 유지 시 throughput 향상 예상" 시그널을 Tüker(2024)의 "콘텐츠 중요도"와 결합한 것
- 기존 호출은 기본값(0, 0.0)으로 동작하므로 하위 호환

### 3. `core/simulator.py` — 동적 배칭 이득 추정

- `NetworkState` 생성 시 현재 `queue_bytes`와 `estimated_batch_gain` 전달
- 배칭 이득 추정: `min(1.0, queue_bytes / mss_bytes) * nagle_penalty_factor`
  - Borisov(2025)의 Little's Law 기반 E2E 추정을 간소화한 근사
  - 큐에 MSS 이상 데이터가 쌓이면 Nagle 패널티 회피 → throughput 향상
- `select_action()` 호출에도 동일 값 전달

### 4. `rl/env.py` — state vector 12→14차원 확장

- state vector에 `estimated_batch_gain`(index 12), `loss_rate`(index 13) 추가
- `NetworkState` 생성에 `queue_bytes` 전달
- `run_episode()` 유틸리티의 NetworkState에도 `queue_bytes` 반영

## 변경 파일 목록

| 파일 | 변경 유형 |
|---|---|
| `policy/importance.py` | 수정 (NetworkState 확장, feature 13D) |
| `policy/action.py` | 수정 (select_action 파라미터 + 배칭 유보 로직) |
| `core/simulator.py` | 수정 (배칭 이득 추정 + 파라미터 전달) |
| `rl/env.py` | 수정 (state 14D + NetworkState 확장) |
| `docs/research_goal.md` | 수정 (연관논문 3편 구조 + 실험 비교 3그룹) |
| `AGENTS.md` | 수정 (연구 정체성 재정의) |
| `docs/analyze/20260331_related_paper_alignment.md` | 신규 (분석 기록) |

## 검증 결과

- `py scripts/smoke_policy_regression.py` — PASS (3종 정책 모두 통과)
- `NetworkState` 하위 호환성 — PASS (기존 코드 기본값으로 동작)
- `select_action()` 하위 호환성 — PASS (기존 호출 시그니처 유지)
- RL 환경 state 차원 — 14D 확인
- Feature vector 차원 — 13D 확인
