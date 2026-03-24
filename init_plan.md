# TCP Video-Aware Adaptive Batching 실험 기준 문서

이 문서는 현재 저장소의 baseline 설계를 고정하는 기준 문서다. 노트북과 결과 해석은 반드시 본 문서와 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)를 기준으로 맞춘다.

## 1. 연구 목적

- TCP 전송에서 batching/flush 정책은 콘텐츠 특성에 따라 서로 다른 trade-off를 만든다.
- 파일 전송은 throughput/goodput/flush 효율이 우선이고, 비디오 스트림은 playback deadline과 keyframe 보호가 우선이다.
- 본 실험은 packet trimming 관련 논문의 `importance-aware adaptation` 아이디어를 TCP batching 문제에 맞게 재해석해 baseline을 재구성한다.
- 이번 단계의 목표는 `논문 재현`이 아니라 `TCP 중심 baseline 재정의`다.

## 2. 범위

### 포함

- 공용 TCP batching simulator
- 실제 H.264 frame trace 기반 `video_stream_trace`
- `fixed_size`, `fixed_time`, `fixed_hybrid`, `heuristic_frame_aware`, `ml_regression_adaptive`
- frame-aware utility metric

### 제외

- BPP/UDP/HAS 프로토콜 비교
- 실제 packet trimming
- kernel TCP 계측
- true SVC transport
- RL 학습 구현

## 3. Workloads

### `static_file`

- 목적: bulk chunk 전송 효율 비교
- 입력
  - `file_size_bytes`
  - `chunk_size_bytes`
  - `generation_gap_ms`
- 기본 실험 축
  - `chunk_size_bytes = [1024, 4096, 16384]`
  - `rtt_ms = [10, 50]`
  - `bandwidth_mbps = [5, 20]`
  - `delayed_ack_ms = [10, 40]`

### `video_stream_trace`

- 목적: frame deadline 기반 전송 비교
- 입력
  - `trace_csv_path`
  - `playback_buffer_ms`
  - `loop_count`
- trace 데이터
  - `data/video-traces/bbb_720p_trace.csv`
  - Big Buck Bunny 10초 720p 샘플에서 `ffprobe`로 추출
- 기본 실험 축
  - `playback_buffer_ms = [33, 50]`
  - `rtt_ms = [10, 50]`
  - `bandwidth_mbps = [5, 20]`
  - `delayed_ack_ms = [10, 40]`

## 4. Frame Trace 규격

CSV 컬럼은 아래로 고정한다.

- `frame_idx`
- `pts_ms`
- `duration_ms`
- `frame_type`
- `payload_bytes`
- `key_frame`
- `gop_id`
- `importance_rank`
- `display_deadline_ms`

규칙:

- `gop_id`는 `I` frame마다 증가한다.
- `importance_rank`는 `I=0`, `P=1`, `B=2`다.
- `display_deadline_ms = pts_ms + duration_ms + playback_buffer_ms`
- `pkt_duration_time`이 비어 있으면 다음 `pts_ms` 차이, 마지막 frame은 median frame interval을 사용한다.

## 5. 정책 정의

- `immediate`
  - 이벤트 도착 즉시 flush
- `fixed_size`
  - timer 없이 `queue_bytes >= batch_bytes`
  - 대표 baseline: `8192B`
- `fixed_time`
  - size 조건 없이 `elapsed >= flush_interval_ms`
  - 대표 baseline: `10ms`
- `fixed_hybrid`
  - size 또는 timer 중 먼저 만족하면 flush
  - best fixed config label 생성과 grid 평가용 기준 정책
- `heuristic_frame_aware`
  - `static_file`
    - `batch = max(4*MSS, 0.5*BDP)`를 grid에 snap
    - `flush = min(0.5*RTT, delayed_ack_ms)`를 grid에 snap
  - `video_stream_trace`
    - queue에 `I` frame이 있거나 최소 slack이 `frame_interval_ms` 이하이면 즉시 flush
    - `critical` queue: `batch=2*MSS`, `flush=4ms`
    - `interactive` queue: `batch=4*MSS`, `flush=8ms`
    - `deferable` queue: `batch=8*MSS`, `flush=16ms`
    - `rtt_ms > playback_buffer_ms / 2`이면 `batch`, `flush`를 절반으로 줄인 뒤 grid에 snap
- `ml_regression_adaptive`
  - `fixed_hybrid` grid에서 뽑은 `best fixed config` label을 `RandomForestRegressor` 2개로 근사
  - output
    - `batch_bytes`
    - `flush_interval_ms`

## 6. 시뮬레이터 규칙

공통 파이프라인:

1. workload 이벤트 생성
2. queue 적재
3. 정책별 flush 결정
4. TCP 근사 완료 시각 계산
5. metric 집계

수식:

- `tx_time_ms = payload_bytes * 8 / bandwidth_mbps / 1000`
- `ack_penalty_ms = min(delayed_ack_ms, nagle_penalty_factor * rtt_ms)` 단, `payload_bytes < MSS`
- `completion_ms = queue_wait_ms + tx_time_ms + propagation_factor * rtt_ms + ack_penalty_ms`

공통 설정값:

- `MSS = 1460`
- `nagle_penalty_factor = 0.25`
- `propagation_factor = 0.5`
- `seed = 20260309`

## 7. 평가 지표

### 공통

- `latency_mean_ms`
- `latency_p95_ms`
- `throughput_mbps`
- `goodput_bytes`
- `flush_count`
- `mean_batch_size_bytes`

### 비디오 유틸리티

- `deadline_miss_ms_sum`
- `late_frame_ratio`
- `keyframe_late_ratio`
- `decodable_gop_ratio`
- `useful_goodput_bytes`

정의:

- `late_frame_ratio`: `completion_ms > display_deadline_ms`인 frame 비율
- `keyframe_late_ratio`: `I` frame subset 기준 late 비율
- `decodable_gop_ratio`: keyframe이 on-time이고 GOP 내 on-time frame 비율이 80% 이상인 GOP 비율
- `useful_goodput_bytes`: on-time frame payload 총합

## 8. Objective Score

score는 시나리오별 `fixed_hybrid` grid min-max 정규화 후 scalar로 계산한다.

### `static_file`

- `throughput_mbps 0.40`
- `goodput_bytes 0.25`
- `latency_p95_ms 0.20` 역방향
- `flush_count 0.15` 역방향

### `video_stream_trace`

- `decodable_gop_ratio 0.30`
- `late_frame_ratio 0.25` 역방향
- `keyframe_late_ratio 0.20` 역방향
- `useful_goodput_bytes 0.15`
- `latency_p95_ms 0.10` 역방향

## 9. Feature Spec

### `static_file`

- `chunk_size_bytes`
- `message_size_mean`
- `inter_arrival_time`
- `queue_size`
- `estimated_rtt`
- `bandwidth_mbps`
- `delayed_ack_ms`

### `video_stream_trace`

- `mean_frame_bytes`
- `p95_frame_bytes`
- `frame_interval_ms`
- `keyframe_interval_frames`
- `i_ratio`
- `p_ratio`
- `b_ratio`
- `estimated_rtt`
- `bandwidth_mbps`
- `delayed_ack_ms`
- `playback_buffer_ms`

## 10. 산출물

노트북 [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)는 아래를 생성한다.

- `reference_policy_overview.png`
- `video_utility_comparison.png`
- `fixed_batch_heatmap.png`
- `policy_pareto_scatter.png`
- `best_fixed_vs_prediction_scatter.png`
- `reference_summary.csv`
- `fixed_policy_grid_results.csv`
- `best_fixed_config_selection.csv`
- `ml_eval_results.csv`

## 11. 수용 기준

- trace CSV는 `pts_ms` 단조 증가와 `I/P/B` frame type을 만족해야 한다.
- `static_file`에서는 batching 계열이 `immediate`보다 flush 수를 줄이면서 throughput을 높이는 시나리오가 하나 이상 있어야 한다.
- `video_stream_trace`에서는 `heuristic_frame_aware`가 적어도 일부 시나리오에서 `fixed_size_8192`보다 `late_frame_ratio` 또는 `keyframe_late_ratio`를 개선해야 한다.
- holdout 평균 `best_fixed_score_gap`에서 `ml_regression_adaptive`가 `heuristic_frame_aware`보다 나쁘지 않아야 한다.

## 12. 다음 단계

- [`rl/env.py`](/C:/git/network/rl/env.py)를 `tcp_batching_core.py` 기반으로 교체
- baseline vs RL 공통 평가 harness 추가
- trace를 1개 이상 더 추가해 단일 비디오 의존성 완화
