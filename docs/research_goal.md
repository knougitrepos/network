# 연구 목표

> **최종 갱신**: 2026-04-06 (중간보고 재현성/설명성 보강)

## 한 줄 요약

H.264 비디오 프레임의 중요도(I/P/B)를 동적으로 판단하여 프레임별 전송 행동(배칭 크기, flush 시점, 신뢰/비신뢰 모드, 경로 선택)을 결정하는 **cross-layer 적응 전송 연구**다.
기존 연구가 콘텐츠 중요도(Tüker 2024)와 전송 계층 최적화(Grazia 2021, Borisov 2025)를 개별적으로 다뤄온 반면, 본 연구는 두 축을 ML/RL 기반으로 통합하는 교차점을 기여 포인트로 삼는다.

## 연구 정체성

> **본 연구는 단순 TCP batching 최적화가 아니다.**
> TCP/QUIC 전송 계층 결정(Grazia 2021, Borisov 2025)에 **콘텐츠 중요도**(Tüker 2024)를 ML/RL 기반으로 통합하는 **cross-layer 적응 전송 연구**다.
> 중요도 판단 방법론(heuristic → ML → RL)의 단계적 고도화가 핵심 기여점이다.

## 연관논문 3편과의 관계

### 전체 구조

```text
응용 계층                   전송-응용 교차점                  전송 계층
(콘텐츠 중요도)             (★ 본 연구 기여 ★)              (TCP/QUIC 메커니즘)

Tüker 2024                 본 연구                          Grazia 2021
Content-aware              "콘텐츠 중요도를 전송             TCP Pacing/TSQ
packet trimming             계층 결정에 ML/RL로 반영"
                                                            Borisov 2025
                                                            E2E adaptive batching
```

### 논문별 관계

#### 1. Tüker et al. (2024) — 콘텐츠 중요도 기반 적응 전송

- **논문**: "Using Packet Trimming at the Edge for In-Network Video Quality Adaption"
- **핵심**: Edge에서 H.264 SVC 기반 packet trimming으로 콘텐츠 중요도 활용
- **본 연구와의 관계**: 콘텐츠 중요도 활용이라는 동일한 축을 공유. 다만 Tüker는 고정 significance value를 사용하고 edge VNF에서 동작하는 반면, 본 연구는 **동적 ML/RL 스코어링**으로 **송신측**에서 전송 행동을 결정
- **한계**: 전송 계층(TCP/QUIC) 결정과의 결합 부재

| 항목   | Tüker 2024                      | 본 연구                                       |
| ------ | ------------------------------- | --------------------------------------------- |
| 단위   | BPP chunk (SVC layer)           | H.264 frame (I/P/B)                           |
| 중요도 | 고정 significance value         | 동적 스코어링 (heuristic → ML → RL)           |
| 위치   | 네트워크 엣지 VNF에서 드롭      | 송신측에서 전송 행동 결정                     |
| 전송   | BPP 프로토콜                    | QUIC Stream/DATAGRAM + multipath              |

#### 2. Grazia et al. (2021) — TCP 내부 latency 메커니즘

- **논문**: "The New TCP Modules on the Block: TCP Pacing & TCP Small Queues", IEEE Access, Vol.9
- **핵심**: TSQ(TCP Small Queues)가 소켓 큐 길이를 제한하여 latency 감소, TP(TCP Pacing)가 버스트를 평탄화
- **본 연구와의 관계**: TCP 전송 계층에서 배칭/패이싱이 latency에 미치는 영향의 **이론적 근거** 제공. 본 연구의 시뮬레이터에서 `ack_penalty_ms`, `nagle_penalty_factor` 등이 이 메커니즘을 근사
- **한계**: 전송할 데이터의 콘텐츠 특성(중요도)을 고려하지 않음

#### 3. Borisov, Amit, Tsafrir (2025) — 적응형 배칭

- **논문**: "Batching with End-to-End Performance Estimation", HotOS '25
- **핵심**: Little's Law 기반 E2E 성능 추정으로 Nagle 알고리즘 동적 토글. Redis에서 throughput 2x / latency 3x 개선
- **본 연구와의 관계**: "static batching의 한계 → adaptive batching 필요"라는 동기를 공유. 본 연구의 `fixed_hybrid`(고정 batch/flush)가 baseline이 되고, `frame_action_adaptive`가 이를 콘텐츠 중요도로 개선
- **한계**: E2E 추정은 하지만 콘텐츠 특성을 전혀 고려하지 않음

### 연구 공백 (Research Gap)

> 기존 연구는 TCP 전송 계층 최적화(Grazia 2021, Borisov 2025)와 콘텐츠 중요도 기반 적응 전송(Tüker 2024)을 **개별적으로** 다뤄왔으나,
> **콘텐츠 중요도를 전송 계층 결정(배칭/패이싱/경로 선택)에 ML/RL로 학습하여 반영하는 end-to-end 시스템**은 부재하다.

## 2단 아키텍처

### Stage A — 프레임 중요도 스코어링 (핵심 기여 지점)

- 입력: H.264 frame type(I/P/B), payload size, deadline slack, GOP 위치, buffer 상태, **네트워크 상태**(RTT, bandwidth, loss — Borisov 관점 흡수)
- 출력: importance score (0.0~1.0)
- **v1** (현재): HeuristicImportanceScorer — IPB type + deadline slack + keyframe bonus
- **v2** (예정): ML 기반 scorer — RandomForest/Gradient Boosting
- **v3** (예정): RL 기반 scorer — FrameSchedulingEnv에서 QoE 보상 극대화 학습

### Stage B — 전송 행동 매핑

- 입력: importance score, deadline slack, network state, 사용 가능 경로 수
- 출력: FrameAction (RELIABLE_SINGLE, RELIABLE_MULTI, UNRELIABLE, DUPLICATE, DROP)

## 논문 기여 포인트

1. **중요도 판단 방법론 고도화**: 단순 I/P/B 우선순위를 넘어, heuristic → ML → RL 단계별 중요도 스코어링과 각 방법론의 QoE 기여 비교
2. **cross-layer 통합**: 콘텐츠 중요도(Tüker)와 전송 계층 결정(Grazia, Borisov)을 동시에 고려하는 프레임 단위 행동 정책
3. **부분 신뢰성+멀티패스 결합 스케줄링**: QUIC Stream/DATAGRAM + multipath 환경에서의 프레임 단위 전송 행동 결정
4. **재현 가능한 검증 프로토콜**: 시뮬레이터 → 에뮬레이터 → 실환경의 계층형 검증

## 실험 비교 구조 (3그룹)

| 비교군                                     | 대응 논문      | 코드 매핑                                              | 의미                                                       |
| ------------------------------------------ | -------------- | ------------------------------------------------------ | ---------------------------------------------------------- |
| **Baseline 1**: Content-unaware 배칭       | Borisov 2025   | `fixed_hybrid` (고정 batch/flush)                      | 콘텐츠를 모르는 상태에서 고정 배칭. static batching의 한계 |
| **Baseline 2**: Content-aware + 고정 규칙  | Tüker 2024     | `heuristic_frame_aware`                                | IPB 타입+deadline으로 조절하지만 학습 기반이 아님          |
| **★ 제안**: Content-aware + adaptive       | 본 연구        | `frame_action_adaptive` / `frame_action_ml_adaptive`   | ML/RL 기반 동적 중요도 → 전송 행동 결정                    |

## 3계층 실험 체계

1. **시뮬레이터 (현재 리포)**: 대규모 정책 탐색/어블레이션
2. **에뮬레이션**:
   - **Windows**: `scripts/network_emulator.py` — asyncio 기반 실제 TCP 소켓 통신 + 지연/손실 시뮬레이션
   - **Linux**: Mininet + tc/netem — 커널 레벨 네트워크 에뮬레이션
3. **실환경 (Wi-Fi + LTE/5G)**: 외부 요인 포함 강건성 검증

### Windows 환경 지원

- **네트워크 에뮬레이션**: `scripts/network_emulator.py` (실제 TCP 통신)
- **QUIC 스택**: aioquic 설치 시 실제 동작 (`pip install aioquic`)
- **VMAF 품질 측정**: FFmpeg GPL 빌드 설치 시 실제 동작
- 설치 가이드: `docs/windows_setup_guide.md` 참조

## 중간보고용 간소 분석 경로

- 중간보고 전용 노트북: `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`
- 입력 비디오 폴더: `dataset/videos/`
- 자동 생성 trace 폴더: `dataset/traces/`
- 공개 데이터셋 경로: 노트북 내 `PUBLIC_VIDEO_SOURCES` 목록 기반 자동 다운로드(실패 시 수동 입력 fallback)
- 중간보고 산출물(CSV/PNG): `output/jupyter-notebook/assets/midreport/`
- 분석 초점:
  - 1순위: H.264 IPB/GOP 특성 파악
  - 2순위: 최소 전송효율 지표(`late_frame_ratio`, `dropped_frame_ratio`, `useful_goodput_bytes`) 비교

## 비교군

- HeuristicImportanceScorer (v1)
- MLImportanceScorer (v2, 예정)
- RLImportanceScorer (v3, 예정)
- Content-unaware baseline (fixed_hybrid — Borisov 관점)
- Content-aware heuristic (heuristic_frame_aware — Tüker 관점)
- MPTCP 계열 신뢰 전송 기준선
- MPQUIC/관련 구현 (가능 범위 내)

## 후속 작업 로드맵

### 중요도 판단 방법론 확장 (핵심 기여 경로)

- ML 기반 importance scorer (v2): 프레임 특성 + 네트워크 상태 → 중요도 예측
- RL 기반 importance scorer (v3): FrameSchedulingEnv에서 QoE 보상 극대화 학습
- 각 방법론(heuristic/ML/RL)의 QoE 기여 비교 분석
- Feature importance 분석: 네트워크 상태 vs 콘텐츠 특성의 기여도 비교 (cross-layer 효과 정량화)

### cross-layer 통합 강화

- ~~NetworkState에 동적 추정값 반영 (estimated RTT/bw — Borisov 관점)~~ → **완료** (queue_bytes, estimated_batch_gain 추가)
- ~~select_action() 입력에 현재 큐 상태 추가 (배칭 효과와 중요도의 상호작용)~~ → **완료** (배칭 유보 로직 구현)

### 시뮬레이션 환경 확장

- QUIC 전송 모델에 실제 loss/jitter 시나리오 추가
- Mininet 에뮬레이션 연동
- video trace 다양성 확대 (1개 이상 추가)
- 실환경(Wi-Fi + LTE/5G) 검증
- 실제 SSIM/VMAF 계산 (ffmpeg 연동)

## 발표용 권장 문구

> 기존 연구는 TCP 전송 계층 최적화(Grazia 2021, Borisov 2025)와 콘텐츠 중요도 기반 적응 전송(Tüker 2024)을 개별적으로 다뤄왔으나, 두 축을 동시에 학습 가능한 형태로 통합한 연구는 부족하다.
> 본 연구는 H.264 프레임 중요도를 ML/RL로 동적 판단하고, 이를 전송 행동(배칭 크기, flush 시점, 신뢰/비신뢰 모드)에 직접 반영하는 cross-layer 적응 전송 시스템을 제안한다.
