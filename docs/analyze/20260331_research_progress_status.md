# 연구 진행 상태 보고서

> 작성일: 2026-03-31  
> 프로젝트: `c:\git\network` — 콘텐츠 중요도 기반 cross-layer 적응 전송 연구  
> 총 커밋: 12회 (df55518 → 5928f14)

---

## 1. 연구 개요

### 한 줄 요약

H.264 비디오 프레임의 중요도(I/P/B)를 ML/RL로 동적 판단하고, 이를 전송 행동(배칭 크기, flush 시점, 신뢰/비신뢰 모드)에 직접 반영하는 **cross-layer 적응 전송 시스템**.

### 연관논문 3편 구조

| 축 | 논문 | 역할 |
|----|------|------|
| 콘텐츠 중요도 | Tüker et al. (2024) | content-aware 선행 연구 |
| TCP latency 메커니즘 | Grazia et al. (2021) | TCP Pacing/TSQ 이론적 근거 |
| 적응형 배칭 | Borisov et al. (2025) | E2E 성능 추정 기반 adaptive batching |

### Research Gap

> 기존 연구는 콘텐츠 중요도와 전송 계층 최적화를 **개별적으로** 다뤄왔으나, **두 축을 ML/RL 기반으로 통합하는 연구는 부재**하다.

---

## 2. 프로젝트 구조

```text
c:\git\network/
├── core/                          # 시뮬레이션 엔진
│   ├── constants.py               #   지표 가중치, 상수 정의
│   ├── transport.py               #   TCP/QUIC 전송 모델 + PathState
│   ├── workload.py                #   워크로드 설정 + 이벤트 생성
│   └── simulator.py               #   통합 시뮬레이션 루프 (402→413줄)
├── policy/                        # 정책 계층
│   ├── importance.py              #   Stage A: 프레임 중요도 스코어링 (166줄)
│   ├── action.py                  #   Stage B: 전송 행동 매핑 (74줄)
│   └── legacy.py                  #   하위 호환 배칭 정책 6종
├── eval/                          # 평가 계층
│   ├── metrics.py                 #   QoE 지표 7종 (120줄)
│   └── scoring.py                 #   Objective Score 산정
├── rl/                            # 강화학습 환경
│   └── env.py                     #   FrameSchedulingEnv (14D state, 261줄)
├── scripts/                       # 실험 스크립트
│   ├── extract_video_trace.py     #   ffprobe 기반 trace 추출
│   ├── build_delta_qoe_labels.py  #   ΔQoE counterfactual 라벨 생성
│   ├── train_importance_model.py  #   ML 모델 학습 (RF Regressor)
│   ├── smoke_policy_regression.py #   정책 회귀 스모크 검증
│   └── export_policy_action_report.py  # 정책 비교 보고서 자동 생성
├── data/video-traces/             # 데이터
│   ├── bbb_720p_trace.csv         #   Big Buck Bunny 10s 720p (300 frames)
│   └── bbb_720p_delta_qoe_labels.csv  # ΔQoE 라벨
├── tmp/models/                    # 학습된 모델 (git 미추적)
│   ├── importance_rf.pkl          #   v2a: heuristic bootstrap (181KB)
│   ├── importance_rf.meta.json
│   ├── importance_rf_delta_qoe.pkl    # v2b: ΔQoE 라벨 기반 (2.1MB)
│   └── importance_rf_delta_qoe.meta.json
├── docs/                          # 프로젝트 문서
│   ├── initial_plan.md            #   초기 실험 설계 (고정, 수정 안 함)
│   ├── research_goal.md           #   연구 목표 (수시 갱신)
│   ├── changelog/ (12건)          #   코드 변경 기록
│   └── analyze/ (6건)             #   분석 요청 기록
├── output/jupyter-notebook/       # 실험 노트북
│   └── tcp-content-aware-batching.ipynb
├── tcp_batching_core.py           # 하위 호환 re-export shim
├── requirements.txt               # 의존성 (5개)
└── README.md                      # 프로젝트 개요
```

---

## 3. 구현 완성도 (모듈별)

### 3.1 Stage A — 프레임 중요도 스코어링

| 버전 | 구분 | 구현 상태 | 파일 | 비고 |
|------|------|-----------|------|------|
| **v1** | HeuristicImportanceScorer | ✅ **완료** | `policy/importance.py` L75-100 | IPB type(0.45) + urgency(0.40) + keyframe bonus(0.15) |
| **v2a** | MLImportanceScorer (heuristic bootstrap) | ✅ **완료** | `policy/importance.py` L103-166 | RF 300trees, MAE≈0, R²=1.0 (heuristic 모사) |
| **v2b** | MLImportanceScorer (ΔQoE 라벨) | ✅ **완료** | `scripts/train_importance_model.py` | RF 300trees, MAE=5.2e-5, R²=0.916 |
| **v3** | RLImportanceScorer | ⬜ **미착수** | `rl/env.py` (환경만 존재) | FrameSchedulingEnv 프로토타입 완료, 학습 루프 미구현 |

**Feature vector 구성 (13차원)**:

| Index | Feature | 출처 |
|-------|---------|------|
| 0-2 | I/P/B one-hot | 콘텐츠 (Tüker 관점) |
| 3 | key_frame | 콘텐츠 |
| 4 | payload_bytes | 콘텐츠 |
| 5-6 | slack_ms, slack_ratio | 콘텐츠+전송 |
| 7-9 | rtt_ms, bandwidth_mbps, loss_rate | 전송 계층 (Grazia 관점) |
| 10 | buffer_level_ms | 응용 계층 |
| 11-12 | queue_bytes, estimated_batch_gain | cross-layer (Borisov 관점) |

### 3.2 Stage B — 전송 행동 매핑

| 항목 | 상태 | 설명 |
|------|------|------|
| FrameAction 5종 | ✅ | RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP |
| select_action() 규칙 기반 | ✅ | 중요도 + deadline slack + 네트워크 상태 → 행동 결정 |
| cross-layer 배칭 유보 | ✅ | estimated_batch_gain ≥ 15% 시 중간 중요도 프레임 flush 지연 (Borisov 관점) |
| ML/RL 기반 행동 결정 | ⬜ | 향후 RL 학습 시 select_action()을 학습된 정책으로 교체 예정 |

### 3.3 시뮬레이션 엔진

| 항목 | 상태 | 설명 |
|------|------|------|
| run_simulation() | ✅ | frame_action_mode에서 Stage A→B 파이프라인 완전 연결 |
| Legacy 정책 호환 | ✅ | 6종 (immediate, fixed_size, fixed_time, fixed_hybrid 등) |
| FrameAction 경로 | ✅ | DROP 스킵, DUPLICATE 2배 전송, 긴급 flush 로직 구현 |
| cross-layer 배칭 이득 추정 | ✅ | min(1, queue/MSS) × nagle_penalty_factor |
| 멀티패스 path selector | ⬜ | available_paths 파라미터만 존재, 실제 경로 선택 로직 미구현 |

### 3.4 전송 모델

| 모델 | 상태 | 설명 |
|------|------|------|
| TCPTransportModel | ✅ | tx_time + propagation + ack_penalty 수식 |
| QUICTransportModel | ⚠️ **시뮬레이션 수준** | Stream/DATAGRAM 구분, loss_rate 반영. 실제 QUIC 스택(aioquic) 연동 없음 |
| PathState | ✅ | 경로별 RTT, bandwidth, loss_rate, last_release_ms |

### 3.5 평가 지표

| 지표 | 상태 | 구현 |
|------|------|------|
| late_frame_ratio | ✅ | on-time 비율 |
| keyframe_late_ratio | ✅ | I-frame 지연 비율 |
| decodable_gop_ratio | ✅ | keyframe on-time + GOP 80% 이상 on-time |
| useful_goodput_bytes | ✅ | on-time 프레임의 총 바이트 |
| rebuffer_ratio | ✅ | 연속 late ≥ 2프레임 구간 비율 |
| ssim_proxy | ⚠️ **proxy** | 0.6×on_time_rate + 0.4×kf_on_time_rate (실측 아님) |
| block_completion_ratio | ✅ | 전체 on-time GOP 비율 |

### 3.6 RL 환경

| 항목 | 상태 | 설명 |
|------|------|------|
| FrameSchedulingEnv | ✅ | reset()/step() 인터페이스, 14차원 state |
| reward 함수 | ✅ | importance × (on_time ? 1 : -0.5) + drop_penalty |
| run_episode() | ✅ | heuristic 기반 smoke 실행 유틸리티 |
| 학습 알고리즘/루프 | ⬜ | PPO/SAC 등 학습 코드 미구현 |
| gymnasium 연동 | ⬜ | 자체 인터페이스만 존재, spaces/wrapper 미구현 |

### 3.7 데이터 및 학습 파이프라인

| 항목 | 상태 | 설명 |
|------|------|------|
| Video trace 추출 | ✅ | `extract_video_trace.py` (ffprobe 기반) |
| Trace 데이터 | ⚠️ **1개** | Big Buck Bunny 10s 720p (300 frames) |
| ΔQoE 라벨 생성 | ✅ | `build_delta_qoe_labels.py` (counterfactual drop) |
| ML 모델 학습 | ✅ | `train_importance_model.py` (RF, train/test split, MAE/R²) |
| 학습된 모델 | ✅ (2개) | heuristic bootstrap (R²=1.0) + ΔQoE 기반 (R²=0.916) |
| 정책 검증 | ✅ | `smoke_policy_regression.py` (3종 정책 불변조건) |
| 정책 보고서 | ✅ | `export_policy_action_report.py` (CSV + PNG 시각화) |

---

## 4. 실험 비교 구조 (현재 코드 매핑)

| 비교군 | 대응 논문 | 코드 정책명 | 구현 상태 |
|--------|-----------|-------------|-----------|
| **Baseline 1**: Content-unaware | Borisov 2025 | `fixed_hybrid` | ✅ 완료 |
| **Baseline 2**: Content-aware + 고정 규칙 | Tüker 2024 | `heuristic_frame_aware` | ✅ 완료 |
| **제안 A**: Content-aware + ML | 본 연구 | `frame_action_adaptive` | ✅ 완료 |
| **제안 B**: Content-aware + ML (v2) | 본 연구 | `frame_action_ml_adaptive` | ✅ 완료 |
| **제안 C**: Content-aware + RL | 본 연구 | (미정) | ⬜ 미착수 |

---

## 5. 전체 완성도 시각화

```text
 구현 완료  ████████████████████░░░░░  80%
─────────────────────────────────────────────
 Stage A v1 (Heuristic)           ██████████  완료
 Stage A v2 (ML Scorer)           ██████████  완료
 Stage A v2 (학습 파이프라인)      ██████████  완료
 Stage A v2 (ΔQoE proxy 라벨)     ██████████  완료
 Stage B (FrameAction 5종)        ██████████  완료
 Simulator ↔ FrameAction          ██████████  완료
 cross-layer 배칭 유보             ██████████  완료
 QoE 지표 7종                     ██████████  완료
 RL 환경 (자체 구현)               ██████████  완료
 정책 검증/보고서 자동화           ██████████  완료
─────────────────────────────────────────────
 실측 VMAF/SSIM 라벨              ░░░░░░░░░░  미완
 RL 학습 루프 (v3)                ░░░░░░░░░░  미착수
 QUIC 실제 스택 연동              ░░░░░░░░░░  미완
 멀티패스 path selector           ░░░░░░░░░░  미완
 video trace 다양성 (≥2종)         ░░░░░░░░░░  미완
```

---

## 6. Git 커밋 이력 (시간순)

| 해시 | 날짜 | 내용 |
|------|------|------|
| `df55518` | 초기 | TCP batching 실험 계획 및 노트북 추가 |
| `96d3884` | — | README.md 추가 |
| `a0069a1` | — | 진행방향 상세 명시 |
| `5cc0d1a` | — | 노트북 sweep/oracle/ML adaptive 확장 |
| `7e6ad50` | — | RL 환경 및 QUIC 전송 모델 추가 |
| `93e9d33` | — | 프레임 중요도 기반 적응 전송 아키텍처 |
| `a720fce` | 03-29 | frame-aware 리팩토링 |
| `d27f9c8` | 03-30 | FrameAction 시뮬레이터 연결 |
| `9f0e4b8` | 03-30 | ML importance scorer + 학습 스크립트 |
| `25abaae` | 03-30 | ΔQoE 라벨 + 정책 검증 자동화 |
| `a9f7e26` | 03-30 | 외부 라벨 기반 ML 학습 + 비교 보고서 |
| `5928f14` | 03-31 | **연관논문 3편 기반 cross-layer 적응 전송 코드 구현** |

---

## 7. 의존성

```text
numpy>=1.24       # 수치 연산
pandas>=2.0       # 데이터프레임
matplotlib>=3.7   # 시각화
seaborn>=0.13     # 시각화 (heatmap 등)
scikit-learn>=1.3 # ML 모델 (RandomForestRegressor)
```

> gymnasium은 requirements.txt에 **포함되지 않음**. rl/env.py는 자체 구현.

---

## 8. 미완 항목 및 후속 작업 우선순위

### 🔴 핵심 경로 (논문 기여에 직접 영향)

| 우선순위 | 작업 | 현재 상태 | 비고 |
|----------|------|-----------|------|
| **P0** | video trace 다양성 확대 | 1종 (BBB 300 frames) | 최소 2-3종 추가 필요 (다양한 해상도/장르) |
| **P0** | ML v2 모델 다양한 네트워크 조건 실험 | 단일 조건 (RTT=30, BW=8) | RTT/loss/BW 조합 grid sweep 필요 |
| **P0** | 3그룹 비교 실험 결과 생성 | 코드 준비 완료, 실행 안 함 | Baseline1 vs Baseline2 vs 제안 QoE 비교 |
| **P1** | RL 학습 루프 구현 (v3) | 환경만 있음 | PPO/SAC + gymnasium wrapper |
| **P1** | Feature importance 분석 | 데이터 없음 | 콘텐츠 vs 전송 피처 기여도 비교 → cross-layer 효과 정량화 |
| **P1** | 어블레이션 실험 | 미착수 | v1 vs v2a vs v2b QoE 비교 |

### 🟡 보강 작업

| 우선순위 | 작업 | 현재 상태 | 비고 |
|----------|------|-----------|------|
| **P2** | 실측 VMAF/SSIM 라벨 전환 | ssim_proxy (on-time 비율 근사) | ffmpeg 연동 필요 |
| **P2** | QUIC 실제 스택 연동 | 시뮬레이션 수준만 | aioquic 통합 |
| **P2** | 멀티패스 path selector | `available_paths` 파라미터만 존재 | 어느 경로로 보낼지 결정 로직 |
| **P3** | Mininet 에뮬레이션 연동 | 미착수 | 제어 가능 환경 검증 |
| **P3** | 실환경 (Wi-Fi + LTE/5G) 검증 | 미착수 | 외부 요인 포함 강건성 |

---

## 9. 변경 이력 추적 체계

### 문서 구조 (AGENTS.md 규칙)

| 카테고리 | 파일 | 파일 수 | 설명 |
|----------|------|---------|------|
| 초기 설계 | `docs/initial_plan.md` | 1개 (고정) | 수정하지 않음 |
| 코드 변경 | `docs/changelog/*.md` | **12건** | 시간순 append-only |
| 연구 목표 | `docs/research_goal.md` | 1개 (수시 갱신) | 최종 갱신: 2026-03-31 |
| 분석 기록 | `docs/analyze/*.md` | **6건** | 분석 요청 시 append-only |

### 최근 주요 변경 (2026-03-29 ~ 03-31)

| 날짜 | changelog 파일 | 핵심 내용 |
|------|----------------|-----------|
| 03-29 | `frame_aware_refactoring` | 프레임 중요도 기반 아키텍처 2단 분리 |
| 03-30 | `frame_action_simulation_hook` | FrameAction ↔ simulator 연결 |
| 03-30 | `ml_importance_scorer_scaffold` | MLImportanceScorer 구현 |
| 03-30 | `ml_model_training_bootstrap` | RF 모델 학습 스크립트 |
| 03-30 | `delta_qoe_label_bootstrap` | ΔQoE counterfactual 라벨 생성 |
| 03-30 | `policy_regression_smoke` | 정책 회귀 자동 검증 |
| 03-31 | `cross_layer_adaptation_code` | **연관논문 3편 통합, cross-layer 코드 구현** |

---

## 10. 학습된 모델 현황

| 모델명 | 라벨 방식 | 피처 수 | 데이터 수 | MAE | R² | 파일 크기 |
|--------|-----------|---------|-----------|-----|----|-----------|
| `importance_rf.pkl` | heuristic bootstrap | 11 | 300 | ≈0 | 1.000 | 181KB |
| `importance_rf_delta_qoe.pkl` | external ΔQoE | 11 | 300 | 5.2e-5 | 0.916 | 2.1MB |

> **참고**: 두 모델 모두 학습 시점에서 11피처 기준. 현재 코드는 13피처로 확장되었으므로, 모델 재학습이 필요함.

---

## 참고 논문

1. **Tüker et al. (2024)** — "Using Packet Trimming at the Edge for In-Network Video Quality Adaption". H.264 SVC 기반 edge packet trimming.
2. **Grazia et al. (2021)** — "The New TCP Modules on the Block: TCP Pacing & TCP Small Queues", IEEE Access, Vol.9. TCP 내부 latency 메커니즘 분석.
3. **Borisov, Amit, Tsafrir (2025)** — "Batching with End-to-End Performance Estimation", HotOS '25. Little's Law 기반 E2E 성능 추정으로 adaptive batching.
4. **Breiman (2001)** — "Random Forests", Machine Learning, 45(1), pp.5-32. Stage A v2 모델의 베이스 알고리즘.
5. **Li et al. (2016)** — "Toward A Practical Perceptual Video Quality Metric", Netflix Tech Blog. 실측 품질 라벨(VMAF) 전환 시 참조.
