# 비디오 프레임 중요도 기반 적응 전송 시스템

H.264 코덱의 프레임 중요도(I/P/B)를 동적으로 판단하여 프레임 단위 전송 행동을 결정하는 적응 전송 연구 저장소다.
참조 논문(Simsek et al., 2023)의 콘텐츠 중요도 기반 적응 전송과 유사한 방향이며,
중요도 판단 방법론(휴리스틱 → ML → RL)의 단계적 고도화를 통한 QoE 개선을 핵심 기여로 삼는다.

## 디렉터리 구조

```
docs/
  initial_plan.md              # 초기 실험 설계 (고정)
  research_goal.md             # 연구 목표 (수시 갱신)
  changelog/                   # 코드 변경 기록 (시간순)
    20260315_baseline_framework.md
    20260329_frame_aware_refactoring.md
    20260330_frame_action_simulation_hook.md
    20260330_ml_importance_scorer_scaffold.md
  analyze/                     # 분석 요청 기록 (시간순)
    20260309_code_direction_review.md
    20260325_improvement_analysis.md
    20260330_identity_alignment.md

core/
  constants.py      # 공유 상수 (grid, weights, seed)
  workload.py       # StaticFileConfig, VideoTraceConfig, generate_workload
  transport.py      # TransportConfig, TCPTransportModel, QUICTransportModel
  simulator.py      # run_simulation, evaluate_fixed_policy_grid

policy/
  importance.py     # Stage A: HeuristicImportanceScorer (IPB+slack+GOP)
  action.py         # Stage B: FrameAction enum, select_action
  legacy.py         # PolicyConfig, resolve_policy (기존 batch/flush 정책)

eval/
  metrics.py        # late_frame_ratio, rebuffer_ratio, ssim_proxy, block_completion 등
  scoring.py        # objective score 계산, select_best_fixed_config

rl/
  env.py            # FrameSchedulingEnv (Gymnasium-style reset/step)

scripts/
  extract_video_trace.py   # ffprobe 기반 frame trace CSV 추출
  build_delta_qoe_labels.py # ΔQoE proxy 라벨 생성 (v2 학습용 초안)
  train_importance_model.py # Stage A v2 bootstrap 학습/저장 (pickle)
  smoke_policy_regression.py # 정책 핵심 경로 회귀 스모크 점검
  export_policy_action_report.py # 정책 요약 CSV/그래프 산출

data/video-traces/         # H.264 frame trace CSV
output/jupyter-notebook/   # 실험 노트북 및 산출물

tcp_batching_core.py       # 하위 호환 shim (기존 import 유지)
```

## 연구 목표

- **핵심**: H.264 비디오 프레임의 중요도(I/P/B type, deadline, GOP 위치)를 동적으로 판단하여 효율적인 전송 행동을 결정
- **참조 논문과의 관계**: Simsek et al.(2023)의 packet trimming 논문과 "콘텐츠 중요도 기반 적응 전송"이라는 동일한 방향을 공유하되, 본 연구는 중요도 판단 방법론(heuristic → ML → RL)의 단계적 고도화를 기여점으로 삼음
- **주의**: 본 연구는 TCP batching 연구가 아님. TCP baseline은 초기 프레임워크 구축 단계에 해당

## 변경 이력

### Phase 1 — 초기 Baseline 프레임워크 (2026-03-15)

- H.264 frame trace 기반 시뮬레이터 구축
- 6종 전송 정책 비교 (immediate, fixed_size, fixed_time, fixed_hybrid, heuristic_frame_aware, ml_regression_adaptive)
- 프레임 중요도 기반 적응 전송의 기초 검증

### Phase 2 — 프레임 중요도 기반 적응 전송 구조 (2026-03-30)

- 의사결정 단위를 프레임 단위로 전환, H.264 I/P/B 중요도 동적 판단
- FrameAction enum: RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP
- Stage A (중요도 스코어링) + Stage B (전송 행동 매핑) 2단 분리
- 중요도 판단 v1: HeuristicImportanceScorer (향후 ML/RL 확장 예정)
- QUIC Stream/DATAGRAM + multipath 전송 모델 추상화 도입
- QoE 지표 확장: rebuffer_ratio, ssim_proxy, block_completion_ratio
- rl/env.py를 FrameSchedulingEnv로 재작성

## Workloads

- `static_file`: bulk file chunk 전송 (throughput/goodput/flush 효율)
- `video_stream_trace`: 실제 frame trace 기반 (late frame, keyframe 보호, GOP decodability)

## 정책 집합

### Legacy (초기 baseline 정책)
- `immediate`, `fixed_size`, `fixed_time`, `fixed_hybrid`
- `heuristic_frame_aware`, `ml_regression_adaptive`, `frame_action_adaptive`, `frame_action_ml_adaptive`

### Frame-aware (프레임 중요도 기반 — 핵심)
- `HeuristicImportanceScorer`: H.264 I/P/B type + deadline slack + GOP 위치 → 동적 중요도 점수 (v1)
- `MLImportanceScorer`: pickle 모델 기반 추론 + 실패 시 heuristic 폴백 (v2 스캐폴딩)
- `FrameAction`: importance score + deadline slack → 전송 모드/경로/중복 결정
- `frame_action_adaptive`: Stage A/B를 `run_simulation()` 경로에 연결하여 프레임별 `importance_score`/`selected_action`을 추적하고 결과 메트릭으로 반환
- `frame_action_ml_adaptive`: `MLImportanceScorer`를 동일 경로에 연결해 v2 실험을 준비하고, 결과 컬럼 `importance_scorer_type`으로 scorer 상태를 추적
- 향후: ML scorer (v2), RL scorer (v3)

## 평가 지표

### 공통
- `latency_mean_ms`, `latency_p95_ms`, `throughput_mbps`, `goodput_bytes`, `flush_count`

### 비디오 QoE
- `late_frame_ratio`, `keyframe_late_ratio`, `decodable_gop_ratio`, `useful_goodput_bytes`
- `rebuffer_ratio`, `ssim_proxy`, `block_completion_ratio` (Phase 2 추가)

## 재현 방법

```powershell
pip install -r requirements.txt

py -3.9 scripts/extract_video_trace.py `
  --input tmp/video-traces/bbb_720_10s.mp4 `
  --output data/video-traces/bbb_720p_trace.csv `
  --playback-buffer-ms 50

py -3.9 scripts/build_delta_qoe_labels.py `
  --trace data/video-traces/bbb_720p_trace.csv `
  --output data/video-traces/bbb_720p_delta_qoe_labels.csv

py -3.9 scripts/train_importance_model.py `
  --trace data/video-traces/bbb_720p_trace.csv `
  --output tmp/models/importance_rf.pkl `
  --playback-buffer-ms 50

py -3.9 scripts/train_importance_model.py `
  --trace data/video-traces/bbb_720p_trace.csv `
  --label-csv data/video-traces/bbb_720p_delta_qoe_labels.csv `
  --label-column delta_qoe_norm `
  --output tmp/models/importance_rf_delta_qoe.pkl

py -3.9 scripts/smoke_policy_regression.py `
  --trace data/video-traces/bbb_720p_trace.csv `
  --model-path tmp/models/importance_rf.pkl

py -3.9 scripts/export_policy_action_report.py `
  --trace data/video-traces/bbb_720p_trace.csv `
  --model-path tmp/models/importance_rf.pkl `
  --output-csv output/jupyter-notebook/assets/policy_action_summary.csv

py -3.9 -m jupyterlab
```

이후 `output/jupyter-notebook/tcp-content-aware-batching.ipynb`를 실행한다.

`frame_action_ml_adaptive` 정책에서 학습 모델을 쓰려면 `PolicyConfig(model_path="tmp/models/importance_rf.pkl")`를 전달한다.

## 주의사항

- 이 저장소는 비디오 프레임 중요도 기반 적응 전송 연구의 시뮬레이션 환경이며, 실제 kernel TCP/QUIC trace나 실제 edge packet trimming 구현은 포함하지 않는다.
- QUIC 전송 모델은 시뮬레이션 수준의 추상화이며 실제 QUIC 프로토콜 구현(aioquic 등)은 후속 작업이다.
- 본 연구는 TCP batching 최적화가 아닌 **프레임 중요도 동적 판단 + 전송 행동 결정**이 핵심이다.
