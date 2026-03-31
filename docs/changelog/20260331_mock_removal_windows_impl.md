# 20260331 Mock 제거 및 Windows 실제 구현

## 변경 배경

사용자가 Mock 구현은 실제 연구가 아니라고 지적하여, Windows 환경에서 실제로 동작하는 구현으로 전환하였다.

## 핵심 변경 사항

### 1. Python 기반 네트워크 에뮬레이터 신규 구현

**파일**: `scripts/network_emulator.py`

Mininet은 Linux 전용이므로, Windows에서도 동작하는 **asyncio 소켓 기반 실제 네트워크 에뮬레이터**를 구현했다.

주요 특징:
- **실제 TCP 소켓 통신** (Mock 아님)
- 지연(delay), 손실(loss), 대역폭 제한(bandwidth limit) 적용
- 토큰 버킷 알고리즘 기반 대역폭 제어
- 7가지 사전 정의 네트워크 프로필 (wifi_good, wifi_congested, lte_good 등)
- 서버-클라이언트 구조로 실제 네트워크 조건 테스트 가능

```python
# 서버 실행
py -3 scripts/network_emulator.py server --port 8080 --profile wifi_congested

# 클라이언트 실험
py -3 scripts/network_emulator.py client --server localhost:8080 --frames 300
```

### 2. Windows 설치 가이드 작성

**파일**: `docs/windows_setup_guide.md`

- Python 환경 설정
- aioquic 설치 방법
- FFmpeg (VMAF 포함) 설치 방법
- 네트워크 에뮬레이션 대안 설명
- 문제 해결 가이드

### 3. 설치 점검 스크립트

**파일**: `scripts/check_installation.py`

모든 필수 의존성 설치 상태를 자동 점검:
- Python 버전
- 핵심 패키지 (numpy, pandas, sklearn 등)
- aioquic (QUIC 스택)
- FFmpeg 및 VMAF 지원
- QUIC 인증서
- 데이터 파일

## 생성/변경 파일 목록

| 파일 | 상태 | 설명 |
|------|------|------|
| `scripts/network_emulator.py` | 신규 | Windows 호환 실제 네트워크 에뮬레이터 |
| `scripts/check_installation.py` | 신규 | 설치 점검 스크립트 |
| `docs/windows_setup_guide.md` | 신규 | Windows 설치 가이드 |

## Mock vs 실제 구현 현황

| 기능 | 이전 | 이후 |
|------|------|------|
| 네트워크 에뮬레이션 | MockRunner (가짜) | 실제 TCP 소켓 + 지연/손실 시뮬레이션 |
| QUIC 스택 | MockQuicClient/Server | aioquic 설치 시 실제 동작 |
| VMAF 라벨 | 미구현 | FFmpeg 설치 시 실제 동작 |

## 실제 동작 요구사항

1. **QUIC 통신**: `pip install aioquic` + TLS 인증서 생성
2. **VMAF 품질 측정**: FFmpeg GPL 빌드 설치
3. **네트워크 에뮬레이션**: `network_emulator.py` 사용 (추가 설치 불필요)

## 테스트 방법

```powershell
# 1. 설치 점검
py -3 scripts/check_installation.py

# 2. 네트워크 에뮬레이터 테스트
py -3 scripts/network_emulator.py server --port 8080 --profile wifi_normal
# 다른 터미널에서:
py -3 scripts/network_emulator.py client --server localhost:8080 --frames 100

# 3. QUIC 테스트 (aioquic 설치 후)
py -3 scripts/quic_server.py --cert certs/server.crt --key certs/server.key
# 다른 터미널에서:
py -3 scripts/quic_client.py --server localhost:4433 --frames 100
```
