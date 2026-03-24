# 2026-03-15 세션 기록: TCP 중심 Video-Aware Baseline 재설계

## 1. 세션 목적

- 사용자 요청:
  - `Using packet trimming at the edge for in-network video quality adaption` 논문을 참고해 박동찬 연구계획서 기준의 baseline 코드를 점검하고, 이후 그 계획을 실제 저장소에 구현
- 최종 목표:
  - 연구 범위를 `TCP batching/flush policy` 중심으로 유지하면서
  - 논문에서 `content importance`, `video-aware evaluation`, `edge-side adaptation 관점`만 차용한
  - 새로운 baseline simulator / notebook / 문서 체계를 반영

## 2. 초기 점검 내용

세션 초반에는 아래 자료와 현재 저장소 상태를 먼저 확인했다.

- 논문 PDF:
  - `C:\Users\Administrator\Downloads\memo-Using packet trimmingattheedgeforin-networkvideoquality.pdf`
- 연구계획서/발표 자료 PDF:
  - `d:\대학원\3학기\컴퓨터통신망\2-제출용\최종 제출용\정보과학과_박동찬_[붙임2-1]구술평가1 발표 양식.pdf`
- 저장소 주요 파일:
  - [`README.md`](/C:/git/network/README.md)
  - [`init_plan.md`](/C:/git/network/init_plan.md)
  - [`progress_notes.md`](/C:/git/network/progress_notes.md)
  - [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)
  - [`rl/env.py`](/C:/git/network/rl/env.py)

초기 점검에서 확인한 핵심 차이는 다음과 같았다.

1. 기존 노트북은 `static_file + synthetic dynamic_stream` 구조였다.
2. 논문은 `BPP/Packet Wash/HAS/UDP` 비교와 `layered video significance`를 다루지만, 연구계획서는 `TCP batching/flush policy` 비교에 초점이 있었다.
3. 따라서 논문 전체를 재현하기보다, `video-aware importance` 개념만 TCP baseline 쪽으로 번안하는 것이 맞다고 정리했다.

## 3. 세션 중 확정한 방향

이 세션에서 아래 사항을 명시적으로 확정했다.

### 연구 범위

- 유지:
  - TCP 중심 baseline
- 도입:
  - 실제 H.264 frame trace 기반 `video_stream_trace`
  - frame importance를 반영한 `heuristic_frame_aware`
  - 네트워크 지표 + 비디오 유용성 지표 혼합 평가
- 제외:
  - BPP/UDP/HAS 프로토콜 구현
  - 실제 packet trimming
  - kernel TCP 계측
  - RL 학습 구현

### baseline 정의

- baseline 정책군:
  - `immediate`
  - `fixed_size`
  - `fixed_time`
  - `fixed_hybrid`
  - `heuristic_frame_aware`
  - `ml_regression_adaptive`

### workload 재정의

- 유지:
  - `static_file`
- 제거:
  - synthetic `dynamic_stream`
- 추가:
  - `video_stream_trace`

### 평가 지표

- 공통:
  - `latency_mean_ms`
  - `latency_p95_ms`
  - `throughput_mbps`
  - `goodput_bytes`
  - `flush_count`
  - `mean_batch_size_bytes`
- 비디오 유틸리티:
  - `deadline_miss_ms_sum`
  - `late_frame_ratio`
  - `keyframe_late_ratio`
  - `decodable_gop_ratio`
  - `useful_goodput_bytes`

## 4. 구현한 항목

### 공용 시뮬레이터 추가

- 추가 파일:
  - [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)

이 파일에 아래 내용을 통합했다.

- workload 생성
- policy 해석
- TCP 근사 전송 계산
- fixed policy grid 평가
- 최적 고정 설정 선택
- scalar objective scoring

즉, notebook이 자체 시뮬레이터를 들고 있지 않고 공용 모듈을 호출하는 구조로 바뀌었다.

### 비디오 trace 추출기 추가

- 추가 파일:
  - [`scripts/extract_video_trace.py`](/C:/git/network/scripts/extract_video_trace.py)

주요 역할:

- `ffprobe`로 frame 메타데이터 추출
- `frame_idx`, `pts_ms`, `duration_ms`, `frame_type`, `payload_bytes`, `key_frame`, `gop_id`, `importance_rank`, `display_deadline_ms` 생성

### 실제 trace CSV 생성

- 추가 파일:
  - [`data/video-traces/bbb_720p_trace.csv`](/C:/git/network/data/video-traces/bbb_720p_trace.csv)

입력 영상:

- Big Buck Bunny 10초 720p 샘플

생성 결과:

- frame 수: `300`
- GOP 수: `2`
- frame type: `I/P/B`
- `pts_ms` 단조 증가 확인

### 노트북 재구성

- 수정 파일:
  - [`output/jupyter-notebook/tcp-content-aware-batching.ipynb`](/C:/git/network/output/jupyter-notebook/tcp-content-aware-batching.ipynb)

변경 내용:

- 공용 시뮬레이터 orchestration 구조로 변경
- `reference cases`, `fixed policy grid`, `best fixed config`, `ML holdout`, `plot/export` 중심으로 재구성
- `py -3.9` 기준 실행 힌트 반영
- `video_stream_trace` 기반 실험 반영

### 문서 갱신

- 수정 파일:
  - [`README.md`](/C:/git/network/README.md)
  - [`init_plan.md`](/C:/git/network/init_plan.md)
  - [`progress_notes.md`](/C:/git/network/progress_notes.md)
  - [`.gitignore`](/C:/git/network/.gitignore)

갱신 목적:

- 기존 synthetic streaming 기반 설명 제거
- 현재 baseline 설계와 구현 결과를 일치시킴
- 새 PNG/CSV/trace 파일 추적 규칙 반영

## 5. 생성/갱신된 산출물

노트북 실행 후 아래 산출물이 갱신되었다.

- [`output/jupyter-notebook/assets/reference_policy_overview.png`](/C:/git/network/output/jupyter-notebook/assets/reference_policy_overview.png)
- [`output/jupyter-notebook/assets/video_utility_comparison.png`](/C:/git/network/output/jupyter-notebook/assets/video_utility_comparison.png)
- [`output/jupyter-notebook/assets/fixed_batch_heatmap.png`](/C:/git/network/output/jupyter-notebook/assets/fixed_batch_heatmap.png)
- [`output/jupyter-notebook/assets/policy_pareto_scatter.png`](/C:/git/network/output/jupyter-notebook/assets/policy_pareto_scatter.png)
- [`output/jupyter-notebook/assets/best_fixed_vs_prediction_scatter.png`](/C:/git/network/output/jupyter-notebook/assets/best_fixed_vs_prediction_scatter.png)
- [`output/jupyter-notebook/assets/reference_summary.csv`](/C:/git/network/output/jupyter-notebook/assets/reference_summary.csv)
- [`output/jupyter-notebook/assets/fixed_policy_grid_results.csv`](/C:/git/network/output/jupyter-notebook/assets/fixed_policy_grid_results.csv)
- [`output/jupyter-notebook/assets/best_fixed_config_selection.csv`](/C:/git/network/output/jupyter-notebook/assets/best_fixed_config_selection.csv)
- [`output/jupyter-notebook/assets/ml_eval_results.csv`](/C:/git/network/output/jupyter-notebook/assets/ml_eval_results.csv)

## 6. 검증 기록

이 세션에서 아래 검증을 실행했다.

### 스크립트/모듈 검증

- `py -3.9 -m py_compile tcp_batching_core.py scripts/extract_video_trace.py`
  - 통과

### trace 검증

- `bbb_720p_trace.csv` 확인 결과
  - `pts_ms` 단조 증가
  - `frame_type in {I, P, B}`
  - `gop_id` 존재

### 노트북 실행 검증

- `py -3.9 -m jupyter nbconvert --to notebook --execute ...`
  - 전체 실행 통과

## 7. 수용 기준 점검 결과

세션 계획에서 정한 acceptance를 실제 산출물 기준으로 확인했다.

### static_file acceptance

- 기준:
  - batching 계열이 `immediate`보다 flush 수를 줄이면서 throughput을 높이는 시나리오 존재
- 확인:
  - `static_reference`에서 `fixed_time_10ms`가 `immediate`보다 throughput이 높고 flush 수가 적었다

### video_stream_trace acceptance

- 기준:
  - `heuristic_frame_aware`가 `fixed_size_8192`보다 `late_frame_ratio` 또는 `keyframe_late_ratio` 개선
- 확인:
  - `video_reference`에서 `late_frame_ratio`
    - `fixed_size_8192 = 0.6633`
    - `heuristic_frame_aware = 0.0167`
  - 조건 충족

### ML acceptance

- 기준:
  - holdout 평균 `best_fixed_score_gap`에서 `ml_regression_adaptive`가 `heuristic_frame_aware`보다 나쁘지 않아야 함
- 확인:
  - `heuristic_frame_aware = 0.3506`
  - `ml_regression_adaptive = 0.0000`
  - 조건 충족

## 8. 세션에서 남긴 중요한 메모

- 현재 baseline truth source는 notebook이 아니라 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py)다.
- [`rl/env.py`](/C:/git/network/rl/env.py)는 이번 세션 범위에서 수정하지 않았다.
- 비디오 쪽 heuristic은 낮은 RTT/낮은 bandwidth 시나리오에서 의미 있는 개선이 보였지만, 모든 시나리오에서 항상 우세한 것은 아니다.
- 이번 결과는 `논문 재현`이 아니라 `TCP 연구계획서에 맞춘 baseline 재설계`라는 점을 문서와 README에 명확히 남겼다.

## 9. 후속 작업 후보

- [`rl/env.py`](/C:/git/network/rl/env.py)를 [`tcp_batching_core.py`](/C:/git/network/tcp_batching_core.py) 기반으로 연결
- video trace를 1개 이상 추가해 단일 콘텐츠 의존성 완화
- 비디오 utility 지표와 flush 규칙을 더 세분화
- 발표 자료에 들어갈 핵심 그래프 선정 및 해석 문구 정리
