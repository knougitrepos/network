# 미흡점 기반 Gap 분석 보고서

작성일: 2026-04-06  
기준 문서: `미흡점.md`  
비교 대상 코드: `policy/importance.py`, `policy/action.py`, `core/simulator.py`, `eval/metrics.py`, `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`  

## 1) 분석 기준

- 평가 스케일
  - **구현됨**: 코드/실험 산출로 기능이 확인됨
  - **부분 구현**: 인터페이스/근사 로직은 있으나 논문 핵심 메커니즘을 완전히 재현하지 못함
  - **미구현**: 스캐폴드/계획 단계로 실제 동작 경로가 없음

- 연구 정체성 기준
  - 본 평가는 "단순 TCP batching"이 아니라 **콘텐츠 중요도 기반 cross-layer 적응 전송** 관점에서 수행함 (`AGENTS.md`, `docs/research_goal.md` 기준).

## 2) 미흡점 항목별 Gap 매트릭스

### 2-1. 품질 지표 이론 근거 (VMAF/SSIM)

- 현재 상태: **부분 구현**
- 근거:
  - `eval/metrics.py`에 `ssim_proxy`는 존재하지만 실제 SSIM/VMAF 계산이 아닌 근사식 기반.
  - `미흡점.md`에서 지적한 VMAF 원천 근거(Netflix 원 논문) 인용/연계 문서 부재.
- gap:
  - "왜 이 지표를 쓰는지"에 대한 이론적/문헌적 정당화가 코드/문서에 약함.
  - 실제 VMAF 계산 파이프라인(예: ffmpeg + libvmaf) 미연동.

### 2-2. 핵심 논문 대비 구현 격차

| 논문 | 요구되는 핵심 | 현재 코드 근거 | 판정 | 남은 gap |
| --- | --- | --- | --- | --- |
| Tüker et al. (2024) | 중요도 기반 trimming/drop | `policy/action.py`의 `FrameAction.DROP`, `core/simulator.py`의 drop 기록/집계 | 부분 구현 | edge packet trimming 수준의 세밀한 payload trimming 로직은 없음 (프레임 단위 drop 중심) |
| Grazia et al. (2021) | TCP Pacing/TSQ 실동작 | `core/simulator.py`의 `ack_penalty_ms`, `nagle_penalty_factor` 근사 모델 | 부분 구현 | 실제 커널 큐(TSQ), pacing 제어 루프 미구현 |
| Borisov et al. (2025) | E2E 추정 기반 adaptive batching | `policy/importance.py`의 `queue_bytes`, `estimated_batch_gain`, `policy/action.py`의 배칭 유보 규칙 | 부분 구현 | 네트워크 상태가 실측 기반 동적 추정이 아님(시뮬레이터 파라미터 의존) |
| Han et al. (2024) | MPR-QUIC 부분신뢰 + multipath | `FrameAction`에 `RELIABLE_MULTI`, `UNRELIABLE`, `DUPLICATE` 존재 | 부분 구현 | 실제 QUIC multipath 스케줄링/Datagram 전송 스택 부재(정책 시뮬레이션 수준) |
| Mao et al. (2017) | RL 학습 기반 최적화(Pensieve) | `docs/research_goal.md`에 RL 확장 계획 명시 | 미구현 | 실제 RL 학습 루프/보상 학습 결과/정책 반영 경로 미흡 |

### 2-3. Top 3 미흡 포인트 재검증

1. **Cross-layer 통합 미흡**
   - 상태: **부분 완화**
   - 근거: 중요도와 전송 상태를 함께 보는 입력(`NetworkState`, `select_action`)은 존재.
   - 잔여 gap: 전송 계층의 실제 동적 상태 추정 및 프로토콜 실장 연동이 약함.

2. **RL 고도화 전 단계**
   - 상태: **유지**
   - 근거: heuristic/ML 폴백 경로는 있으나 RL 학습 파이프라인이 실험 결과로 연결되지 않음.

3. **실제 프로토콜 연동 부재**
   - 상태: **유지**
   - 근거: 현재 검증의 주 실행 경로가 시뮬레이터와 노트북 중심.
   - 참고: `docs/research_goal.md`는 실환경/에뮬레이션 로드맵을 유지하지만, 현 코드 기준 완전한 실장 단계는 아님.

## 3) 중간보고 노트북 관점의 추가 gap

- 현재 상태: **부분 구현**
- 근거:
  - `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`는 재현성 셀, 도출식 로그, 차트 개선을 반영.
  - 다만 공개 데이터셋 다운로드 결과에서 다수 URL이 `HTTP 403`으로 실패한 출력이 존재.
- gap:
  - "공개 데이터셋 기반 완전 재현성"이 네트워크/호스트 정책에 취약.
  - 대체 미러/자동 fallback 소스 체계가 더 필요.

## 4) 즉시 실행 가능한 보완 액션

### A. 코드/실험

1. `eval/metrics.py`에 VMAF 실측 지표 연동 레이어 추가(옵션 플래그로 on/off)
2. `core/simulator.py`에 late frame 원시 카운트(`late_frame_count`)를 반환해 도출식 로그의 추정치 의존도 감소
3. 노트북의 공개 데이터셋 소스를 403-safe mirror 우선순위 리스트로 재구성

### B. 문서/근거

1. `docs/research_goal.md`에 "실제 VMAF vs proxy 사용 조건"을 명시
2. `docs/analyze`에 문헌 근거 보강 문서(지표/프로토콜 표준 중심) 추가

### C. 발표 대응

1. "현재는 시뮬레이터 기반 검증 단계, 프로토콜 실장 단계는 후속"을 명시적으로 구분
2. "부분 구현 vs 미구현" 경계(예: multipath 정책 모델 vs 실제 QUIC 스택)를 슬라이드에 분리 표기

## 5) 참고문헌 보강 권고 (미흡점.md 반영)

- 우선순위 높음
  1. VMAF 원천 문헌 (지표 정당화)
  2. RFC 9221 (QUIC Datagram, 부분신뢰 전송 근거)
  3. H.264/AVC 표준 개요 문헌 (I/P/B 의존성 근거)

- 기대 효과
  - 품질 지표의 타당성, 프로토콜 실현 가능성, 코덱 기반 중요도 판단의 학술적 근거를 동시에 보강할 수 있음.

## 6) 최종 결론

현재 코드는 **콘텐츠 중요도 기반 cross-layer 적응 전송**의 방향성은 맞게 구현되어 있으며, heuristic/ML 기반 프레임 행동 결정과 시뮬레이터 지표 체계가 정리되어 있다.  
다만 논문 대응 관점에서는 여전히 **부분 구현(근사 모델 중심)** 비중이 높고, 특히 VMAF 근거/실측, 실제 QUIC multipath·부분신뢰 실장, RL 학습 파이프라인에서 명확한 gap이 남아 있다.  
즉, 연구 단계는 "방향 정합 + 핵심 골격 구현 완료, 실증 고도화 진행 필요"로 평가한다.
