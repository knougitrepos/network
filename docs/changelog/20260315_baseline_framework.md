# 2026-03-15 — 초기 Baseline 프레임워크 구축

## 배경

- 참조 논문(Simsek et al., 2023)의 콘텐츠 중요도 기반 적응 전송 아이디어를 차용
- 연구계획서 기준의 baseline 코드 점검 후, 프레임 중요도 기반 적응 전송 연구를 위한 초기 시뮬레이터 프레임워크를 구축

## 확정한 방향

### 연구 범위 (Phase 1)

- **구축**: H.264 frame trace 기반 시뮬레이터, 프레임 중요도 반영 `heuristic_frame_aware` 정책 (v1), 네트워크 지표 + 비디오 QoE 혼합 평가 체계
- **제외**: BPP/UDP/HAS 프로토콜, 실제 packet trimming, kernel TCP/QUIC 계측

### 전송 정책 정의

- `immediate`, `fixed_size`, `fixed_time`, `fixed_hybrid`, `heuristic_frame_aware`, `ml_regression_adaptive`

### workload 재정의

- `static_file` 유지
- synthetic `dynamic_stream` 제거, 실제 H.264 frame trace 기반 `video_stream_trace` 추가

### 평가 지표

- 공통: `latency_mean_ms`, `latency_p95_ms`, `throughput_mbps`, `goodput_bytes`, `flush_count`, `mean_batch_size_bytes`
- 비디오 QoE: `deadline_miss_ms_sum`, `late_frame_ratio`, `keyframe_late_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`

## 구현 내역

### 공용 시뮬레이터

- `tcp_batching_core.py` 추가 — workload 생성, policy 해석, TCP 근사 전송 계산, fixed policy grid 평가, objective scoring 통합
- notebook이 자체 시뮬레이터를 들고 있지 않고 공용 모듈을 호출하는 구조로 전환

### 비디오 trace 추출기

- `scripts/extract_video_trace.py` — `ffprobe`로 H.264 frame 메타데이터 추출
- 출력 컬럼: `frame_idx`, `pts_ms`, `duration_ms`, `frame_type`, `payload_bytes`, `key_frame`, `gop_id`, `importance_rank`, `display_deadline_ms`

### 실제 trace CSV 생성

- `data/video-traces/bbb_720p_trace.csv` — Big Buck Bunny 10초 720p (300 frames, 2 GOPs, I/P/B frame type)

### 노트북 재구성

- `output/jupyter-notebook/tcp-content-aware-batching.ipynb` — 공용 시뮬레이터 orchestration 구조, reference cases / fixed policy grid / best fixed config / ML holdout / plot·export 중심

## 검증 결과

| 항목 | 결과 |
|------|------|
| `py_compile` (tcp_batching_core.py, extract_video_trace.py) | 통과 |
| trace CSV (pts_ms 단조증가, I/P/B type, gop_id) | 정상 |
| notebook 전체 실행 (`nbconvert --execute`) | 통과 |

### 수용 기준 점검

- **static_file**: `fixed_time_10ms`가 `immediate`보다 throughput 높고 flush 수 적음 — 충족
- **video_stream_trace**: `heuristic_frame_aware` late_frame_ratio=0.0167 vs `fixed_size_8192`=0.6633 — 충족
- **ML**: `ml_regression_adaptive` score_gap=0.0000 vs `heuristic_frame_aware`=0.3506 — 충족

## 생성/갱신된 산출물

- `output/jupyter-notebook/assets/reference_policy_overview.png`
- `output/jupyter-notebook/assets/video_utility_comparison.png`
- `output/jupyter-notebook/assets/fixed_batch_heatmap.png`
- `output/jupyter-notebook/assets/policy_pareto_scatter.png`
- `output/jupyter-notebook/assets/best_fixed_vs_prediction_scatter.png`
- `output/jupyter-notebook/assets/reference_summary.csv`
- `output/jupyter-notebook/assets/fixed_policy_grid_results.csv`
- `output/jupyter-notebook/assets/best_fixed_config_selection.csv`
- `output/jupyter-notebook/assets/ml_eval_results.csv`

## 메모

- 시뮬레이터 truth source는 notebook이 아닌 `tcp_batching_core.py`
- 프레임 중요도 기반 heuristic은 낮은 RTT/낮은 bandwidth에서 의미 있는 개선, 모든 시나리오에서 항상 우세하지는 않음 → ML/RL 기반 중요도 판단으로 개선 여지
