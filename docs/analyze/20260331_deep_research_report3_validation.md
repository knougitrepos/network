# deep-research-report (3).md 검증 분석

> **분석 일자**: 2026-03-31
> **분석 대상**: `deep-research-report (3).md` vs 현재 저장소 코드
> **목적**: 보고서의 프로젝트 분석이 실제 코드와 정합하는지 확인

## 1. 검증 요약

### ✅ 보고서 분석이 올바른 항목

| 항목 | 보고서 내용 | 코드 확인 결과 |
|------|------------|----------------|
| **13차원 피처 벡터** | `build_importance_features()`가 13차원 피처 생성 | ✅ `policy/importance.py:49-87` — I/P/B one-hot + slack + 네트워크/큐 상태 포함 |
| **HeuristicImportanceScorer** | IPB type + deadline slack + keyframe bonus | ✅ `policy/importance.py:90-115` |
| **MLImportanceScorer** | pickle 모델 로드/추론/폴백 포함 | ✅ `policy/importance.py:118-174` |
| **ΔQoE proxy 라벨 생성** | `build_delta_qoe_labels.py` 존재 | ✅ `scripts/build_delta_qoe_labels.py` — drop 시나리오 기반 delta_qoe_norm 생성 |
| **외부 라벨 CSV 학습 경로** | `--label-csv`, `--label-column` 지원 | ✅ `scripts/train_importance_model.py:121-122` |
| **NetworkState cross-layer 확장** | queue_bytes, estimated_batch_gain 포함 | ✅ `policy/importance.py:33-35` |
| **시뮬레이터 ML 연결** | `frame_action_ml_adaptive` 정책 지원 | ✅ `core/simulator.py:94-110` — MLImportanceScorer 초기화 및 폴백 로직 |
| **FrameAction 5종** | RELIABLE_SINGLE/MULTI, UNRELIABLE, DUPLICATE, DROP | ✅ `policy/action.py:15-20` |
| **QoE proxy 지표** | rebuffer_ratio, ssim_proxy, block_completion_ratio | ✅ `eval/metrics.py:49-95` |
| **QUIC 모델은 시뮬 추상화** | QUICTransportModel은 프로토타입 | ✅ `core/transport.py:80-96` — 실제 RFC 기반 구현 아님 |
| **Mininet 실행 코드 부재** | 토폴로지/스크립트 미확인 | ✅ 저장소 내 Mininet 관련 파일 없음 |

### ⚠️ 보고서와 미세 차이 또는 추가 확인 필요 항목

| 항목 | 보고서 내용 | 실제 상태 | 비고 |
|------|------------|----------|------|
| **배칭 유보 로직** | 보고서는 "cross-layer 배칭 유보"를 언급 | ✅ 코드에 존재 | `policy/action.py:62-72` — `estimated_batch_gain >= 0.15` 조건 |
| **RL 환경** | "v3 RL은 가능성만 열려 있음" | ✅ 정확 | `rl/env.py` 스켈레톤만 존재 |
| **모델 다양화** | RandomForest만 구현 | ✅ 정확 | GBDT 등 추가 모델은 TODO |

## 2. 보고서의 "이미 반영(OK)" vs "TODO" 분류 검증

### A. ML 라벨·피처·모델 옵션

| 항목 | 보고서 판정 | 코드 검증 결과 |
|------|-----------|---------------|
| 피처 벡터 규격(13차원) | OK | ✅ 일치 |
| Heuristic→ML scorer 교체 인터페이스 | OK | ✅ 일치 |
| ML 학습 스크립트(bootstrap) | OK | ✅ 일치 |
| 외부 라벨 CSV 학습 경로 | OK | ✅ 일치 |
| ΔQoE proxy 라벨 생성 | OK(Proxy) | ✅ 일치 — `label_mode: delta_qoe_proxy_v1` |
| 실측 VMAF/SSIM 기반 ΔQoE 라벨 | TODO | ✅ 일치 — 코드 없음 |
| 모델 다양화(GBDT 등) | TODO(선택) | ✅ 일치 |

### B. 실험 설계(에뮬·실환경)

| 항목 | 보고서 판정 | 코드 검증 결과 |
|------|-----------|---------------|
| 시뮬레이터 기반 1차 검증 | OK | ✅ 일치 |
| Mininet 에뮬레이션 설계(문서) | OK(문서) | ✅ 일치 — `docs/research_goal.md`에 명시 |
| Mininet 실행 코드/토폴로지 | TODO | ✅ 일치 — 코드 없음 |
| 실환경(Wi-Fi + LTE/5G) 설계(문서) | OK(문서) | ✅ 일치 |
| 실환경 실행 앱/스크립트 | TODO | ✅ 일치 — 코드 없음 |
| 실제 QUIC 스택 구현 | TODO | ✅ 일치 — QUICTransportModel은 시뮬 추상화 |

## 3. 연구 정체성 정합성

| 검증 항목 | 결과 |
|----------|------|
| "TCP batching 최적화가 아니다" 선언 | ✅ `docs/research_goal.md:12-14`에 명확히 기술 |
| cross-layer 적응 전송 정체성 | ✅ 코드 전반에 일관 반영 (NetworkState, select_action 등) |
| 연관논문 3편 관계 정의 | ✅ `docs/research_goal.md:16-64`에 상세 기술 |
| 2단 아키텍처(Stage A/B) | ✅ 코드 구조와 일치 (`policy/importance.py`, `policy/action.py`) |

## 4. 결론

**보고서 `deep-research-report (3).md`의 프로젝트 분석은 전반적으로 정확합니다.**

### 정확한 점
1. **ML 파이프라인 반영 상태** — 이전 보고서들과 달리 "ML이 코드에 없다"는 주장을 정확히 수정하여 "이미 구현됨"으로 판정
2. **피처/스코어러/학습 경로** — 13차원 피처, MLImportanceScorer, 외부 라벨 학습 모두 코드로 확인
3. **TODO 항목 식별** — 실측 VMAF/SSIM 라벨, Mininet 실행 코드, 실환경 하네스, 실제 QUIC 스택이 구현 필요 사항임을 정확히 식별
4. **연구 정체성** — "단순 TCP batching이 아닌 cross-layer 적응 전송"이라는 정체성이 코드와 문서에 일관되게 반영되어 있음을 확인

### 보고서 권고사항의 적절성
보고서가 제시한 "주 기여 선택" 두 갈래:
- **(가) 실측 라벨/지표 고도화** — VMAF/SSIM 기반 ΔQoE로 ML 설득력 강화
- **(나) Mininet→실환경 검증 파이프라인** — 시스템 실증성 강화

두 방향 모두 현재 코드 상태를 정확히 반영한 합리적인 권고입니다.

---

*이 분석은 코드 수정 없이 검증만 수행하였습니다.*
