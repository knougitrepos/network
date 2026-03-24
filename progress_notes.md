# 진행 메모

## 2026-03-15 baseline 재설계 반영

### 핵심 변경

1. baseline truth source를 노트북 내부 코드에서 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)로 이동했다.
2. synthetic `dynamic_stream` workload를 제거하고 실제 frame trace 기반 `video_stream_trace`로 교체했다.
3. baseline 정책군을 아래로 재정의했다.
   - `immediate`
   - `fixed_size`
   - `fixed_time`
   - `fixed_hybrid`
   - `heuristic_frame_aware`
   - `ml_regression_adaptive`
4. objective를 workload별 scalar score로 통일했다.
5. 노트북 [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)을 공용 모듈 orchestration 구조로 재작성했다.

### 추가된 자산

- [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)
- [`scripts/extract_video_trace.py`](/C:/git/network/scripts/extract_video_trace.py)
- [`data/video-traces/bbb_720p_trace.csv`](/C:/git/network/data/video-traces/bbb_720p_trace.csv)

### 새 지표

- `deadline_miss_ms_sum`
- `late_frame_ratio`
- `keyframe_late_ratio`
- `decodable_gop_ratio`
- `useful_goodput_bytes`

### 검증 메모

- Big Buck Bunny 10초 720p 샘플에서 `bbb_720p_trace.csv`를 추출했다.
- trace CSV는 `pts_ms` 단조 증가, `I/P/B` frame type, GOP id를 만족한다.
- `static_file` smoke 시뮬레이션은 정상 동작한다.
- `video_stream_trace`에서는 낮은 RTT 시나리오에서 `heuristic_frame_aware`가 `fixed_size_8192`보다 `late_frame_ratio`를 개선하는 조합이 확인됐다.

### 남은 항목

- [ ] notebook 전체 실행 결과가 수용 기준을 만족하는지 최종 확인
- [ ] [`rl/env.py`](/C:/git/network/rl/env.py)와 공용 simulator 통합
- [ ] trace 다양성 확대
