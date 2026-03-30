# 비디오 프레임 중요도 기반 적응 전송 실험 기준 문서

> 이 문서는 프로젝트 시작 시점의 실험 설계를 고정하는 기준 문서다. 이후 수정하지 않는다.

## 1. 연구 목적

- H.264 코덱의 프레임 중요도(I/P/B)를 동적으로 판단하여 프레임 단위 전송 행동을 결정한다.
- 참조 논문(Simsek et al., 2023)의 콘텐츠 중요도 기반 적응 전송과 유사한 방향이며, 중요도 판단 방법론(휴리스틱 → ML → RL)의 단계적 고도화를 핵심 기여로 삼는다.
- QUIC(부분 신뢰성) + multipath 환경에서의 프레임 중요도 기반 전송 행동 결정을 실험한다.
- **주의**: 본 연구는 TCP batching 최적화 연구가 아니다. TCP baseline은 초기 프레임워크 구축 단계에 해당한다.

## 2. 범위

### 포함

- 공용 전송 시뮬레이터 (`core/simulator.py`)
- 프레임 중요도 스코어링 (`policy/importance.py`)
- 프레임 단위 전송 행동 결정 (`policy/action.py`)
- Legacy batch/flush 정책 6종 (`policy/legacy.py`)
- QoE 지표 파이프라인 (`eval/metrics.py`, `eval/scoring.py`)
- RL 프레임 스케줄링 환경 (`rl/env.py`)
- H.264 frame trace 기반 workload

### 제외

- BPP/UDP/HAS 프로토콜 비교
- 실제 packet trimming
- kernel TCP/QUIC 계측
- true SVC transport
- 실제 SSIM/VMAF 계산 (ffmpeg 연동은 후속)

## 3. 아키텍처 (2단 분리)

### Stage A — 프레임 중요도 스코어링 (핵심 기여 지점)

- 입력: H.264 frame type(I/P/B), payload size, deadline slack, GOP 위치, buffer 상태
- 출력: importance score (0.0~1.0)
- v1: HeuristicImportanceScorer (IPB+slack+keyframe bonus) — 현재 구현
- v2 (예정): ML 기반 scorer (RandomForest/Gradient Boosting)
- v3 (예정): RL 기반 scorer (QoE 보상 극대화 학습)

### Stage B — 전송 행동 매핑

- 입력: importance score, deadline slack, network state, 사용 가능 경로 수
- 출력: FrameAction (RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP)

## 4. Workloads

### `static_file`

- bulk chunk 전송 효율 비교
- `file_size_bytes`, `chunk_size_bytes`, `generation_gap_ms`

### `video_stream_trace`

- frame deadline 기반 전송 비교
- `trace_csv_path`, `playback_buffer_ms`, `loop_count`
- Big Buck Bunny 10초 720p 샘플에서 `ffprobe`로 추출

## 5. Frame Trace 규격

CSV 컬럼:

- `frame_idx`, `pts_ms`, `duration_ms`, `frame_type`, `payload_bytes`
- `key_frame`, `gop_id`, `importance_rank`, `display_deadline_ms`

## 6. 정책 정의

### Legacy (초기 baseline 정책)

- `immediate`, `fixed_size`, `fixed_time`, `fixed_hybrid`
- `heuristic_frame_aware`, `ml_regression_adaptive`

### Frame-aware (프레임 중요도 기반 — 핵심)

- `FrameAction` enum으로 프레임별 전송 모드 결정
- `HeuristicImportanceScorer` → `select_action()` 파이프라인 (v1)
- 향후 ML/RL scorer로 `ImportanceScorer` 교체하여 중요도 판단 방법론 비교 실험

## 7. 전송 모델

### TCPTransportModel

- 기존 수식 유지: `tx_time + propagation_factor * RTT + ack_penalty`

### QUICTransportModel

- Stream(신뢰) / DATAGRAM(비신뢰) 구분
- 경로별 RTT, bandwidth, loss_rate 반영
- multipath 확장 대비

## 8. 평가 지표

### 공통

- `latency_mean_ms`, `latency_p95_ms`, `throughput_mbps`, `goodput_bytes`, `flush_count`

### 비디오 QoE

- `late_frame_ratio`, `keyframe_late_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`
- `rebuffer_ratio`: 연속 late frame 구간 비율
- `ssim_proxy`: on-time 비율 + keyframe 완전성 기반 근사
- `block_completion_ratio`: 전체 프레임 on-time GOP 비율

## 9. Objective Score

시나리오별 fixed_hybrid grid min-max 정규화 후 scalar로 계산한다.

### `static_file`

- `throughput_mbps 0.40`, `goodput_bytes 0.25`, `latency_p95_ms 0.20` 역방향, `flush_count 0.15` 역방향

### `video_stream_trace`

- `decodable_gop_ratio 0.30`, `late_frame_ratio 0.25` 역방향, `keyframe_late_ratio 0.20` 역방향
- `useful_goodput_bytes 0.15`, `latency_p95_ms 0.10` 역방향
