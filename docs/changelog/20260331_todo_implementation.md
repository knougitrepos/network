# 2026-03-31: TODO 항목 구현

## 변경 배경

`deep-research-report (3).md`에서 식별된 4가지 TODO 항목을 구현:

1. 실측 VMAF/SSIM 기반 ΔQoE 라벨 생성
2. Mininet 에뮬레이션 실행 코드/자동화
3. 실환경(Wi-Fi+LTE) 측정 하네스
4. 실제 QUIC 스택 기반 구현

## 구현 내역

### 1. 실측 VMAF/SSIM 라벨 생성 (`scripts/build_vmaf_labels.py`)

- FFmpeg libvmaf를 활용한 실제 품질 측정
- 프레임 drop 시나리오: 해당 프레임을 이전 프레임으로 대체("freeze frame")
- `delta_qoe_norm` 계산: `(100 - VMAF_score) / 100`
- 샘플링 기능 (`--sample-ratio`)으로 대용량 비디오 효율 처리

### 2. Mininet 에뮬레이션 (`scripts/emulation_topology.py`, `scripts/emulation_runner.py`)

**토폴로지 정의:**
- `VideoStreamingTopology`: 클라이언트 → 스위치 → 서버
- `DumbbellTopology`: 병목 테스트용 양방향 토폴로지

**네트워크 프로필:**
- `wifi_good`: 50 Mbps, RTT 10ms, 손실 0.1%
- `wifi_congested`: 10 Mbps, RTT 50ms, 손실 1%
- `lte_normal`: 20 Mbps, RTT 30ms, 손실 0.5%
- `lte_poor`: 2 Mbps, RTT 100ms, 손실 3%

**실험 자동화:**
- `ExperimentRunner`: Mininet 기반 반복 실험
- `MockRunner`: Linux 외 환경용 합성 데이터 생성

### 3. 실환경 측정 하네스 (`scripts/realworld_harness.py`)

**시간 동기화:**
- `TimestampSync`: NTP 서버 기반 클라이언트-서버 오프셋 계산

**네트워크 모니터링:**
- `NetworkMonitor`: RTT, 패킷 손실, 인터페이스 통계 주기적 측정

**로깅:**
- `TransmissionLogger`: 송신/ACK/손실/재전송 이벤트
- `PlaybackLogger`: 버퍼 상태, 스톨 이벤트, 프레임 지연

**통합 관리:**
- `RealworldExperiment`: 모든 로거 통합, CSV/JSON 결과 저장

### 4. QUIC 스택 (`scripts/quic_server.py`, `scripts/quic_client.py`)

**서버:**
- aioquic 기반 HTTP/3 + DATAGRAM 지원
- 중요도 기반 전송 방식 결정:
  - I-프레임, 높은 중요도 → STREAM (신뢰 전송)
  - B-프레임, 낮은 중요도 → DATAGRAM (저지연)
- 더미 프레임 생성기 (GOP 패턴 시뮬레이션)

**클라이언트:**
- 프레임 요청 및 수신 (STREAM/DATAGRAM)
- `FrameBuffer`: 재생 시뮬레이션용 버퍼
- 지연 시간 통계 (avg, p95, p99)

**Fallback:**
- `MockQuicServer`, `MockQuicClient`: aioquic 미설치 시 합성 데이터 생성

### 5. 의존성 업데이트 (`requirements.txt`)

추가된 패키지:
- `av>=13.0.0`: PyAV (FFmpeg 바인딩)
- `ntplib>=0.4.0`: NTP 시간 동기화
- `aioquic>=1.0.0`: QUIC/HTTP3 구현

## 생성/변경 파일 목록

| 파일 | 상태 | 설명 |
|------|------|------|
| `scripts/build_vmaf_labels.py` | 신규 | VMAF/SSIM 기반 ΔQoE 라벨 생성 |
| `scripts/init_project_structure.py` | 신규 | 디렉토리 구조 초기화 헬퍼 |
| `scripts/emulation_topology.py` | 신규 | Mininet 토폴로지 정의 |
| `scripts/emulation_runner.py` | 신규 | 에뮬레이션 실험 자동화 |
| `scripts/realworld_harness.py` | 신규 | 실환경 측정 하네스 |
| `scripts/quic_server.py` | 신규 | QUIC 비디오 스트리밍 서버 |
| `scripts/quic_client.py` | 신규 | QUIC 비디오 스트리밍 클라이언트 |
| `requirements.txt` | 변경 | 신규 의존성 추가 |
| `docs/analyze/20260331_deep_research_report3_validation.md` | 신규 | 보고서 검증 분석 |

## 검증 결과

### 코드 구조 확인

- 모든 스크립트가 독립 실행 가능 (`python scripts/xxx.py --help`)
- 모든 클래스/함수에 docstring 포함
- `logging` 모듈 사용으로 디버그 용이

### 의존성 체인

```
vmaf-ssim-labels (완료)
    ├── mininet-topology (완료)
    │       └── realworld-harness (완료)
    └── quic-stack (완료)
```

### Mock/Fallback 지원

- `MockRunner`: Mininet 미설치 환경에서 합성 데이터 생성
- `MockQuicServer/Client`: aioquic 미설치 환경에서 시뮬레이션

## 후속 작업

1. **FFmpeg libvmaf 설치 확인**: `ffmpeg -filters | grep vmaf`
2. **QUIC 인증서 생성**:
   ```bash
   mkdir -p certs
   openssl req -x509 -newkey rsa:2048 -keyout certs/server.key \
       -out certs/server.crt -days 365 -nodes
   ```
3. **Mininet 테스트** (Linux 환경):
   ```bash
   sudo python scripts/emulation_runner.py --profile wifi_good
   ```
4. **실환경 테스트**:
   ```bash
   python scripts/realworld_harness.py --server 8.8.8.8 --duration 60
   ```

## 연구 정체성 준수

모든 구현이 **cross-layer 적응 전송** 연구의 일부임:
- QUIC 서버의 `decide_transport_mode()`: 콘텐츠 중요도 기반 전송 결정
- 실환경 하네스: 네트워크 상태와 QoE 동시 측정으로 cross-layer 분석 지원
- Mininet 프로필: 다양한 네트워크 조건에서의 적응 전송 평가
