# deep-research-report (2).md 검증 보고서

> 작성일: 2026-03-30  
> 검증 대상: `deep-research-report (2).md` (22,114 bytes, 235 lines)  
> 검증 방법: 보고서에서 언급한 14개 파일 + 보고서에서 누락된 4개 파일의 실제 코드를 전수 확인

---

## 1. 종합 평가

| 평가 항목 | 결과 |
|---|---|
| **파일별 핵심 발견 테이블 (14개 파일)** | 정확 9건 / 부분 정확 3건 / 오류 2건 |
| **갭 분석 (4개 항목)** | 정확 2건 / **과장 또는 오래된 정보** 2건 |
| **보고서에서 누락된 구현** | **4건** (중요) |
| **지표 테이블** | 대체로 정확, 세부 1건 수정 필요 |
| **requirements.txt 기술** | **부분 오류** |

> 보고서는 전체적 방향과 아키텍처 분석은 우수하나, **보고서 작성 시점 이후 추가된 구현(ML 파이프라인 스크립트 4개)을 반영하지 못해 갭 분석이 과장**되어 있다.

---

## 2. 파일별 정확성 검증

### ✅ 정확하게 기술된 항목 (9건)

| # | 파일 | 보고서 기술 | 검증 결과 |
|---|---|---|---|
| 1 | `README.md` | "TCP batching이 아니라 프레임 중요도 기반 적응 전송을 목표" | ✅ README.md L1-3에 정확히 일치 |
| 2 | `docs/initial_plan.md` | "Stage A/B, 지표/가중치, 제외 항목 명시" | ✅ §3 아키텍처 2단 분리, §8 평가 지표, §9 Objective Score에 정확히 존재 |
| 3 | `core/workload.py` | "display_deadline_ms = pts + duration + playback_buffer" | ✅ L126: `trace_df["display_deadline_ms"] = trace_df["pts_ms"] + trace_df["duration_ms"] + float(cfg.playback_buffer_ms)` |
| 4 | `core/transport.py` | "TCPTransportModel과 QUICTransportModel 존재, 멀티패스 path state/손실 모델 포함" | ✅ `PathState`(L22-28), `QUICTransportConfig`(L72-78), `QUICTransportModel`(L80-96) 모두 존재 |
| 5 | `policy/importance.py` | "IPB 타입/슬랙/키프레임 보너스로 0~1 스코어" | ✅ L86: `_TYPE_BASE_SCORES`, L94: urgency from slack, L97: `keyframe_bonus = 0.15`, L99: `raw = 0.45 * type_score + 0.40 * urgency + keyframe_bonus` |
| 6 | `policy/action.py` | "FrameAction 5종 (신뢰 단일/멀티/비신뢰/중복/드롭)" | ✅ L15-20: 정확히 5종 Enum 정의됨 |
| 7 | `policy/legacy.py` | "과거 batch/flush 정책 호환 레이어" | ✅ L69-92: `resolve_policy()`에서 8종 정책 지원 |
| 8 | `eval/scoring.py` | "metric들을 종합해 objective score 산정(가중치 적용)" | ✅ L34-42: OBJECTIVE_WEIGHTS 기반 정규화 + 가중합 |
| 9 | `core/constants.py` | "지표 가중치/상수 정의" | ✅ L15-31: `STATIC_OBJECTIVE_WEIGHTS`, `VIDEO_OBJECTIVE_WEIGHTS` 정의 |

### ⚠️ 부분적으로 정확한 항목 (3건)

| # | 파일 | 보고서 기술 | 실제 코드 상태 | 차이점 |
|---|---|---|---|---|
| 1 | `core/simulator.py` | "run_simulation이 아직 legacy batch/flush 형태가 강함" | `run_simulation()`은 L88-114에서 `frame_action_mode`를 감지하고, L180-228에서 프레임별 importance scoring → action selection → DROP/DUPLICATE 처리가 완전히 구현됨 | **보고서가 과소평가**. legacy flush 로직이 공존하는 것은 맞지만, FrameAction 경로는 이미 완전히 작동하는 수준으로 연결되어 있다 |
| 2 | `requirements.txt` | "numpy/pandas/scikit-learn/gymnasium 등" | `gymnasium`은 requirements.txt에 **없음** (실제 내용: numpy, pandas, matplotlib, seaborn, scikit-learn) | **gymnasium 언급은 오류**. rl/env.py는 gymnasium 스타일이지만 gymnasium을 import하지 않고 자체 구현 |
| 3 | `rl/env.py` | "Gymnasium 기반 RL 환경 스켈레톤. 현재는 TCP 모델 기반이고 action의 효과가 제한적" | `FrameSchedulingEnv`는 reset()/step() 인터페이스, 12차원 state, reward 계산, `compute_all_video_metrics` 연동까지 구현됨 | "스켈레톤"이라는 표현이 **과소평가**. 상당히 완성도 있는 구현이나, gymnasium 라이브러리 자체와의 연동(spaces, wrapper 등)은 미완 |

### ❌ 오류가 있는 항목 (2건)

| # | 파일 | 보고서 기술 | 실제 상태 | 문제 |
|---|---|---|---|---|
| 1 | `eval/metrics.py` | "BufRatio/aSSIM/Block completion/goodput/latency로 확장 가능한 **뼈대**" | `compute_all_video_metrics()` (L98-119)에서 7개 지표를 완전히 계산하여 반환함. 단순 "뼈대"가 아님 | **과소평가**. "뼈대"가 아니라 작동하는 구현. ssim_proxy만 실측이 아닌 것은 맞음 |
| 2 | `scripts/extract_video_trace.py` | "다만 현재는 프레임 특징량이 제한적" | L35-47에서 7개 필드 추출. ML feature 확장은 `build_importance_features()` 함수에서 11차원으로 이미 구현됨 | "프레임 특징량이 제한적"이라는 평가는 **모호**. trace CSV 수준에서는 충분한 feature가 추출되고 있음 |

---

## 3. 보고서에서 누락된 중요 구현 (4건)

> 보고서가 "ML 기반 중요도 스코어링의 **실재화**가 비어있다"고 분석했으나, 실제로는 아래 4개 파일이 이미 구현되어 있다. 이것이 보고서의 가장 큰 부정확성이다.

### 3.1 `scripts/build_delta_qoe_labels.py` (252 lines)
- ΔQoE 기반 프레임 중요도 라벨 생성 스크립트
- baseline frame record에서 counterfactual drop 영향을 계산하여 `delta_qoe`, `delta_qoe_norm` 라벨 생성
- 보고서 §갭분석이 "라벨이 코드로 제공되지 않는다"라고 했으나 → 라벨 생성은 이미 구현됨

### 3.2 `scripts/train_importance_model.py` (208 lines)
- Stage A v2 ML 모델 학습 스크립트 (RandomForestRegressor)
- train/test split, MAE/R2 검증, pickle 저장
- 외부 라벨 CSV (delta_qoe_norm) 연동 지원
- 보고서가 "학습/검증이 코드로 제공되지 않는다"라고 했으나 → 학습+검증+모델 저장까지 구현됨

### 3.3 `scripts/smoke_policy_regression.py` (212 lines)
- 정책 회귀 스모크 검증 스크립트
- 3종 정책의 결과 컬럼/범위/불변조건 자동 점검

### 3.4 `scripts/export_policy_action_report.py` (190 lines)
- 정책 요약 보고서 자동 생성 (CSV + action bar chart PNG + QoE scatter PNG)

### 3.5 `policy/importance.py`의 MLImportanceScorer (L103-159)
- pickle 모델 로드, 11차원 feature 생성, predict_proba/predict 지원, 실패 시 heuristic 폴백까지 완전 구현

---

## 4. 갭 분석 재평가

| 보고서 갭 항목 | 보고서 평가 | 실제 상태 | 수정된 평가 |
|---|---|---|---|
| **ML 기반 중요도 스코어링 실재화** | "코드로 제공되지 않음" | 라벨·학습·추론·검증 파이프라인 모두 구현 | ⚠️ **과장됨**. 초안(proxy 라벨) 수준이지만 파이프라인 자체는 end-to-end 존재 |
| **부분 신뢰성의 표준 기반 실행** | "실제 QUIC 스택 바인딩은 미완" | 시뮬레이션 수준만 존재, 실제 aioquic 연동 없음 | ✅ **정확** |
| **멀티패스 스케줄링 정식화** | "기여 지점" | `select_action()`에서 available_paths 분기 존재, path selector 미구현 | ⚠️ **부분 정확** |
| **지표 proxy→실측 전환** | "ssim_proxy는 실제 SSIM/VMAF가 아님" | on-time 비율 기반 근사값, 실측 미완 | ✅ **정확** |

---

## 5. 현재 구현 완성도 요약

```
구현 완료 ████████████████░░░░ 80%
────────────────────────────────
✅ Stage A v1 (Heuristic Scorer)     완료
✅ Stage A v2 (ML Scorer 구조)       완료
✅ Stage A v2 (학습 스크립트)         완료
✅ Stage A v2 (ΔQoE proxy 라벨)      완료
✅ Stage B (FrameAction 5종)         완료
✅ Simulator ↔ FrameAction 연결     완료
✅ QoE 지표 7종                      완료
✅ RL 환경 (자체 구현)                완료
⚠️ 실측 VMAF/SSIM 라벨              미완
⚠️ 어블레이션 실험                    미완
⚠️ QUIC 실제 스택 연동               미완
⚠️ 멀티패스 path selector            미완
```

---

## 6. 보고서 수정 권고 (6건)

1. **§갭분석 - ML 중요도 스코어링**: "코드로 제공되지 않는다" → "proxy 라벨 기반 초안 파이프라인이 구현되어 있으나, 실측 VMAF/SSIM 기반 라벨과 교차검증/어블레이션 미완"
2. **§열람 파일 테이블**: 4개 scripts 파일 추가 필요
3. **requirements.txt**: "gymnasium" 언급 삭제
4. **simulator.py**: "리팩토링이 최우선" → "FrameAction 경로가 완전히 연결됨, legacy와의 공존 정리가 필요한 수준"
5. **rl/env.py**: "스켈레톤" → "기능적 프로토타입"
6. **eval/metrics.py**: "뼈대" → "작동하는 구현"

---

## 참고 논문/방법론

- **ΔQoE 기반 라벨링**: Simsek et al. (2023) "Content-aware Packet Trimming for Real-time Video Traffic" 및 MPR-QUIC (Han et al.)의 deadline 기반 우선순위 방식과 정합적
- **RandomForest Regressor**: Breiman, 2001 "Random Forests", Machine Learning, 45(1), pp.5-32. 온라인 추론 비용이 낮고 feature importance 해석이 용이
- **VMAF**: Li et al. (2016) "Toward A Practical Perceptual Video Quality Metric", Netflix Tech Blog. 실측 품질 라벨 전환 시 참조
