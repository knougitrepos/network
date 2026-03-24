# TCP Video-Aware Baseline 점검 메모

## 점검 요청 범위

- 기준 논문: [Using packet trimming at the edge for in-network video quality adaption](https://link.springer.com/article/10.1007/s12243-023-00981-8)
- 연구 기준 문서:
  - `d:/대학원/3학기/컴퓨터통신망/2-제출용/최종 제출용/정보과학과_박동찬_[붙임2-1]구술평가1 발표 양식.pdf`
- 점검 대상:
  - `session_notes_20260315_tcp_video_baseline.md`
  - `tcp_batching_core.py`
  - `scripts/extract_video_trace.py`
  - `init_plan.md`
  - `README.md`

## 최종 판단

- **진행 가능(Go)**: 현재 baseline 방향은 연구계획서의 핵심 질문(정적 vs 스트리밍, TCP batching 정책 비교, latency/throughput trade-off)과 정합적이다.
- 단, 본 작업은 **논문 재현(reproduction)**이 아니라 **논문 아이디어 차용(adaptation)**으로 정의해야 한다.

## 핵심 근거

### 1) 연구계획서와의 정합성

- 연구계획서는 TCP 전송 정책 비교를 중심으로 한다.
- 특히 파일 전송/스트리밍 전송 간 정책 효과 차이와 즉시/고정/적응형 배칭 비교가 질문 중심이다.

### 2) 현재 baseline의 설계 일치성

- `init_plan.md`에 이미 다음 전제가 명시되어 있다:
  - packet trimming 논문의 importance-aware adaptation 관점을 TCP batching 문제로 재해석
  - 이번 단계는 논문 재현이 아니라 TCP 중심 baseline 재정의
- `tcp_batching_core.py`는 frame type, keyframe, deadline slack 기반의 `heuristic_frame_aware` 정책을 구현해 비디오 중요도 기반 의사결정을 반영한다.
- `scripts/extract_video_trace.py`는 H.264 frame trace를 추출하고 `importance_rank`, `display_deadline_ms`를 구성해 video-aware 평가가 가능하다.

### 3) 논문 대비 차이의 해석

- 기준 논문은 BPP/Packet Wash/SVC/edge VNF/UDP-HAS-TCP 비교를 다루는 구조이다.
- 현재 baseline은 TCP batching/flush 정책 비교 중심이다.
- 이는 범위 축소가 아니라, 연구계획서에 맞춘 문제 재정의로 해석 가능하다.

## 보완 필요 사항 (발표/심사 리스크 완화)

1. **용어 고정**
   - "논문 재현" 대신 "논문 아이디어 차용"으로 일관되게 표현할 것.
2. **외적 타당성**
   - 현재 trace가 `bbb_720p_trace.csv` 1개라 콘텐츠 일반화 근거가 약함.
3. **지표 체계 차이 설명**
   - 논문의 QoE 식(세그먼트 기반)과 현재 utility 지표(`late_frame_ratio`, `decodable_gop_ratio`)의 차이를 명시할 것.
4. **ML 설명 정합성**
   - 계획서의 "이진화 모델" 표현과 실제 구현(RandomForest 회귀 기반 파라미터 예측)을 맞춰 설명할 것.

## 발표용 권장 문구

아래 문장을 기준 문구로 고정 권장:

> 본 실험은 10.1007/s12243-023-00981-8의 BPP packet trimming 메커니즘을 직접 재현한 것이 아니라, 해당 논문의 콘텐츠 중요도 기반 적응 아이디어를 TCP batching/flush 정책 비교 문제로 번안한 baseline이다.

## 결론

- 현재 `session_notes_20260315_tcp_video_baseline.md` 방향은 연구계획서 목적에 부합한다.
- 따라서 baseline 구현 방향은 유지 가능하다.
- 다만, 논문과의 관계를 "재현"이 아닌 "번안"으로 명확히 관리하고, trace 다양성 및 지표 해석 근거를 보강하는 것이 필요하다.
