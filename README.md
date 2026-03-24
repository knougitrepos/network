# TCP Video-Aware Adaptive Batching

TCP/HTTP-style 전송 경로에서 `write -> queue -> batching -> flush -> send` 정책을 비교하는 실험 저장소다. 현재 기준선은 단순 synthetic streaming이 아니라, 실제 H.264 frame trace를 이용한 `video_stream_trace` workload와 공용 시뮬레이터 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)를 중심으로 구성된다.

## 현재 기준

- 연구 범위
  - TCP 중심 batching/flush 정책 비교
  - packet trimming 논문은 `content importance`, `video-aware evaluation`, `edge-side adaptation 관점`만 차용
  - `BPP/UDP/HAS`, 실제 packet trimming, kernel TCP 계측은 이번 저장소 범위 밖
- source of truth
  - [`init_plan.md`](/C:/git/network/init_plan.md)
  - [`progress_notes.md`](/C:/git/network/progress_notes.md)
  - [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)

## 주요 파일

- [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)
  - 공용 workload 생성, policy 해석, TCP 근사 시뮬레이션, fixed policy grid 평가와 최적 고정 설정 scoring
- [`scripts/extract_video_trace.py`](/C:/git/network/scripts/extract_video_trace.py)
  - `ffprobe` 기반 frame trace CSV 추출기
- [`data/video-traces/bbb_720p_trace.csv`](/C:/git/network/data/video-traces/bbb_720p_trace.csv)
  - 10초 Big Buck Bunny 720p 샘플에서 추출한 frame-level trace
- [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)
  - baseline orchestration notebook
- [`rl/env.py`](/C:/git/network/rl/env.py)
  - 아직 baseline 공용 시뮬레이터에 연결되지 않은 RL 환경 초안

## Workloads

- `static_file`
  - bulk file chunk 전송
  - `file_size_bytes`, `chunk_size_bytes`, `generation_gap_ms`
  - throughput/goodput/flush 효율 해석 중심
- `video_stream_trace`
  - 실제 frame trace 기반 전송
  - `trace_csv_path`, `playback_buffer_ms`, `loop_count`
  - late frame, keyframe 보호, GOP decodability 해석 중심

## 정책 집합

- `immediate`
- `fixed_size`
- `fixed_time`
- `fixed_hybrid`
- `heuristic_frame_aware`
- `ml_regression_adaptive`

`heuristic_frame_aware`는 파일 전송에서는 BDP 기반 batch 규칙을, 비디오 전송에서는 frame type과 deadline slack을 반영한 flush 규칙을 사용한다. `ml_regression_adaptive`는 `fixed_hybrid` grid에서 얻은 `best fixed config`의 `batch_bytes`, `flush_interval_ms`를 `RandomForestRegressor` 두 개로 근사한다.

## 핵심 지표

- 공통
  - `latency_mean_ms`
  - `latency_p95_ms`
  - `throughput_mbps`
  - `goodput_bytes`
  - `flush_count`
  - `mean_batch_size_bytes`
- 비디오 유틸리티
  - `deadline_miss_ms_sum`
  - `late_frame_ratio`
  - `keyframe_late_ratio`
  - `decodable_gop_ratio`
  - `useful_goodput_bytes`

## Objective Score

시나리오별 `fixed_hybrid` grid 결과를 min-max 정규화한 뒤 scalar score를 계산한다.

- `static_file`
  - `throughput_mbps 0.40`
  - `goodput_bytes 0.25`
  - `latency_p95_ms 0.20` 역방향
  - `flush_count 0.15` 역방향
- `video_stream_trace`
  - `decodable_gop_ratio 0.30`
  - `late_frame_ratio 0.25` 역방향
  - `keyframe_late_ratio 0.20` 역방향
  - `useful_goodput_bytes 0.15`
  - `latency_p95_ms 0.10` 역방향

## 재현 방법

### 1. 비디오 trace 재생성

`ffprobe`와 `ffmpeg`가 PATH에 있다고 가정한다. 이 저장소에서는 `py -3.9`를 기준으로 CLI 예시를 맞춘다.

```powershell
py -3.9 scripts/extract_video_trace.py `
  --input tmp/video-traces/bbb_720_10s.mp4 `
  --output data/video-traces/bbb_720p_trace.csv `
  --playback-buffer-ms 50
```

### 2. 노트북 실행

```powershell
py -3.9 -m jupyterlab
```

이후 [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)를 위에서 아래로 실행한다.

### 3. 산출물

노트북 실행 시 아래 파일이 갱신된다.

- `output/jupyter-notebook/assets/reference_policy_overview.png`
- `output/jupyter-notebook/assets/video_utility_comparison.png`
- `output/jupyter-notebook/assets/fixed_batch_heatmap.png`
- `output/jupyter-notebook/assets/policy_pareto_scatter.png`
- `output/jupyter-notebook/assets/best_fixed_vs_prediction_scatter.png`
- `output/jupyter-notebook/assets/reference_summary.csv`
- `output/jupyter-notebook/assets/fixed_policy_grid_results.csv`
- `output/jupyter-notebook/assets/best_fixed_config_selection.csv`
- `output/jupyter-notebook/assets/ml_eval_results.csv`

## 현재 상태

- [x] 공용 baseline simulator를 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)로 분리
- [x] Big Buck Bunny trace CSV 생성 및 로딩 경로 반영
- [x] baseline 정책군을 `fixed_size`/`fixed_time`/`fixed_hybrid`/`heuristic_frame_aware`/`ml_regression_adaptive`로 재정의
- [x] notebook orchestration을 공용 모듈 기반으로 재작성
- [ ] RL 환경을 공용 시뮬레이터와 통합

## 주의사항

- [`rl/env.py`](/C:/git/network/rl/env.py)는 아직 placeholder physics를 사용한다.
- 이번 저장소는 연구 발표용 비교 실험이며 실제 kernel TCP trace나 실제 edge packet trimming 구현은 포함하지 않는다.
