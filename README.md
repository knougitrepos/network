# TCP Content-Aware Adaptive Batching

TCP/HTTP2 전송 경로에서 `write -> buffer -> segmentation -> send` 과정의 flush/batching 정책을 비교하기 위한 실험 저장소다. 이 저장소의 현재 정확한 방향성은 [`progress_notes.md`](/C:/git/network/progress_notes.md)를 기준으로 한다.

## 기준 문서

- [`progress_notes.md`](/C:/git/network/progress_notes.md)
  - 현재 저장소의 source of truth
  - 문제 정의, 구현 우선순위, Heuristic -> ML -> RL 로드맵을 관리
- [`init_plan.md`](/C:/git/network/init_plan.md)
  - 연구계획서/발표 자료 기준의 초기 실험 설계 문서

## 문제 정의

- 대상
  - TCP/HTTP2 전송 경로의 flush/batching 정책
- 입력
  - 메시지 도착 패턴
  - 메시지 크기
  - 콘텐츠 타입 (`file`, `stream`)
  - latency 제약
  - RTT
- 의사결정
  - 지금 flush할지 여부
  - 더 기다릴지 여부
  - batch 크기와 flush 주기
- 목적함수
  - latency 최소화
  - throughput 최대화

## 구현 우선순위

1. Heuristic baseline
2. ML adaptive policy
3. RL adaptive transmission policy

현재 문제는 일반적인 분류/예측보다 `Policy Learning / Adaptive Control` 문제로 다루는 것을 기본 전제로 한다.

## 현재 저장소 상태

- [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)
  - heuristic baseline 비교
  - `fixed_sweep`, `pick_oracle`
  - `RandomForestRegressor` 기반 `ml_regression_adaptive`
  - `progress_notes.md` 기준 feature (`message_size`, `inter_arrival_time`, `queue_size`, `elapsed_time_since_last_flush`, `estimated_rtt`)
  - 시나리오별 fixed sweep bounds 기반 `candidate_score`, `oracle_score_gap`
  - repo root 기준 artifact export
  - heatmap / Pareto scatter / CSV export
- [`progress_notes.md`](/C:/git/network/progress_notes.md)
  - Heuristic -> ML -> RL 방향성 메모
- [`init_plan.md`](/C:/git/network/init_plan.md)
  - 초기 실험 설계와 Mermaid 흐름도

## 실험 구성

### 워크로드

- `static_file`
  - 정적 파일 chunk 전송
  - throughput, goodput, syscall 감소 중심으로 해석
- `dynamic_stream`
  - 지속적으로 갱신되는 streaming 메시지 전송
  - latency, staleness, syscall 감소 중심으로 해석

### 정책 단계

- `immediate`
- `fixed_batch`
- `heuristic_adaptive`
- `ml_regression_adaptive`
- `rl_adaptive`
  - 아직 미구현

### 핵심 지표

- `latency_mean_ms`
- `latency_p95_ms`
- `throughput_mbps`
- `goodput_bytes`
- `syscall_count`
- `staleness_penalty`

## 실행 방법

1. Jupyter에서 [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)를 연다.
2. 셀을 위에서 아래로 순서대로 실행한다.
3. 필요한 경우 노트북이 `numpy`, `pandas`, `matplotlib`, `seaborn`, `scikit-learn`을 설치한다.
4. 실행 위치와 무관하게 결과는 저장소 루트 기준 [`output/jupyter-notebook/assets/`](/C:/git/network/output/jupyter-notebook/assets)에 PNG/CSV로 저장된다.

## 현재 검증 메모

- 2026-03-09 기준으로 노트북 코드 셀 순차 실행 검증을 완료했다.
- 기존의 단일-row 정규화 scoring 버그는 제거됐고, 현재는 같은 시나리오의 fixed sweep 결과를 기준으로 ML/heuristic 후보를 평가한다.
- 현재 holdout grid에서는 `ml_regression_adaptive`와 `heuristic_adaptive`가 같은 `batch/flush` 조합을 선택해 동일한 성능을 보인다.
- 이 상태는 scoring 버그가 아니라 현재 시나리오 공간에서 두 정책이 아직 분리되지 않은 결과다.

## 현재 산출물

- `output/jupyter-notebook/assets/reference_policy_overview.png`
- `output/jupyter-notebook/assets/fixed_batch_heatmap.png`
- `output/jupyter-notebook/assets/policy_pareto_scatter.png`
- `output/jupyter-notebook/assets/reference_summary.csv`
- `output/jupyter-notebook/assets/fixed_sweep_results.csv`
- `output/jupyter-notebook/assets/oracle_selection.csv`
- `output/jupyter-notebook/assets/ml_eval_results.csv`

## 다음 단계

- [x] `fixed_sweep`, `pick_oracle`
- [x] `RandomForestRegressor` 기반 `ml_regression_adaptive`
- [x] heatmap / Pareto scatter / CSV export
- [ ] RL 실험용 `rl/env.py` 설계 초안 문서화

## 작업 원칙

- 방향성 판단은 항상 `progress_notes.md`를 우선한다.
- 연구계획서/발표자료 정합성이 필요할 때 `init_plan.md`를 함께 참고한다.
- 실험 축, 정책 단계, 결과 해석 방식이 바뀌면 README와 노트북 설명도 같이 갱신한다.
