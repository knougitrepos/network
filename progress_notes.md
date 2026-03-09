# 진행 메모

## 2026-03-09 연구 방향 요약

### 핵심 결론

1. 본 주제는 일반적인 DL 분류/예측보다 **Policy Learning / Adaptive Control** 문제로 정의하는 것이 타당하다.
2. 구현 우선순위는 아래 순서를 따른다.
   1) Heuristic baseline
   2) ML adaptive policy (경량 회귀/트리)
   3) RL adaptive transmission policy
3. CNN/RNN 중심 접근은 현재 문제 구조(저차원 feature, 제한된 데이터, 제어 중심 의사결정)와 적합성이 낮다.

### 문제 정의

- 대상: TCP/HTTP2 전송 경로에서 `write -> buffer -> segmentation -> send` 과정의 flush/batching 정책
- 입력: 메시지 도착 패턴, 메시지 크기, 콘텐츠 타입(file/stream), latency 제약, RTT 등
- 의사결정:
  - 지금 flush할지 여부
  - batch를 더 대기할지 여부
  - batch 크기/flush 주기
- 목적함수: latency 최소화 + throughput 최대화

### 실험/모델링 로드맵

#### 1) Heuristic Baseline (필수)

- immediate send
- fixed size batching
- fixed time batching
- content-aware rule (streaming은 작은 batch, file은 큰 batch)

#### 2) ML Adaptive Policy

- 입력 feature(초안):
  - `message_size`
  - `inter_arrival_time`
  - `queue_size`
  - `content_type`
  - `elapsed_time_since_last_flush`
  - `estimated_rtt`
- 출력:
  - `flush_now`(0/1) 또는 `batch_size`
- 모델 우선순위:
  - Decision Tree
  - Random Forest
  - Gradient Boosting / LightGBM

#### 3) RL Adaptive Policy

- state: `queue_size`, `message_rate`, `message_size`, `rtt`, `content_type`
- action: `flush`, `wait`, `increase_batch`, `decrease_batch`
- reward 예시:
  - `reward = throughput - alpha * latency`
- 후보 알고리즘: DQN, PPO

### 논문 구조 권장안

1. Introduction
2. Background (TCP batching, Nagle, HTTP/2 segmentation)
3. Transmission Policy (immediate/fixed/adaptive)
4. Learning-based Policy (ML, RL)
5. Experiment (file transfer, streaming transfer)
6. Results (latency, throughput, syscall count)

### 저장소 반영용 작업 항목

- [x] 노트북에 `fixed_sweep`, `pick_oracle` 구현
- [x] `RandomForestRegressor` 기반 `ml_regression_adaptive` 셀 추가
- [x] heatmap / Pareto scatter / CSV export 추가
- [ ] RL 실험을 위한 `rl/env.py` 설계 초안 문서화
- [x] 결과 비교 지표에 `syscall_count` 포함 검토

## 2026-03-09 구현 진행 업데이트

### 완료한 항목

- [x] 노트북에 `fixed_sweep`, `pick_oracle` 구현
- [x] `RandomForestRegressor` 기반 `ml_regression_adaptive` 평가 셀 추가
- [x] heatmap / Pareto scatter / CSV export 셀 및 파일 저장 로직 추가
- [x] 결과 비교 지표에 `syscall_count`(flush 호출 수 근사치) 포함

### 남은 항목

- [ ] RL 실험을 위한 `rl/env.py` 설계 초안 문서화

### 산출 파일(노트북 실행 시 생성)

- `output/jupyter-notebook/assets/fixed_batch_heatmap.png`
- `output/jupyter-notebook/assets/policy_pareto_scatter.png`
- `output/jupyter-notebook/assets/reference_summary.csv`
- `output/jupyter-notebook/assets/fixed_sweep_results.csv`
- `output/jupyter-notebook/assets/oracle_selection.csv`
- `output/jupyter-notebook/assets/ml_eval_results.csv`
