# Windows 환경 설치 가이드

이 문서는 Windows에서 프로젝트의 모든 기능을 **실제로 동작**하도록 설정하는 방법을 설명합니다.

## 목차

1. [Python 환경 설정](#1-python-환경-설정)
2. [기본 패키지 설치](#2-기본-패키지-설치)
3. [QUIC 스택 설치](#3-quic-스택-설치)
4. [VMAF/품질 측정 도구 설치](#4-vmaf품질-측정-도구-설치)
5. [네트워크 에뮬레이션](#5-네트워크-에뮬레이션)
6. [설치 확인](#6-설치-확인)

---

## 1. Python 환경 설정

### Python 설치 확인

```powershell
# PowerShell에서 실행
py -3 --version
# 또는
python --version
```

Python 3.9 이상이 필요합니다.

### 가상환경 생성 (권장)

```powershell
cd C:\git\network
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
```

Git Bash에서는:
```bash
cd /c/git/network
py -3 -m venv .venv
source .venv/Scripts/activate
```

---

## 2. 기본 패키지 설치

```powershell
pip install -r requirements.txt
```

`requirements.txt`에 포함된 주요 패키지:
- `numpy`, `pandas`: 데이터 처리
- `scikit-learn`: ML 모델 학습
- `matplotlib`, `seaborn`: 시각화
- `torch`: 딥러닝 (선택)

---

## 3. QUIC 스택 설치

### aioquic 설치

```powershell
pip install aioquic
```

### 자체 서명 인증서 생성

QUIC 통신에는 TLS 인증서가 필요합니다:

```powershell
# certs 폴더 생성
mkdir certs

# OpenSSL 설치 (Git Bash에 포함되어 있음)
# Git Bash에서 실행:
openssl req -x509 -newkey rsa:4096 -keyout certs/server.key -out certs/server.crt -days 365 -nodes -subj "/CN=localhost"
```

Windows에서 OpenSSL이 없다면:
1. https://slproweb.com/products/Win32OpenSSL.html 에서 다운로드
2. 또는 아래 PowerShell 스크립트 사용:

```powershell
# PowerShell에서 자체 서명 인증서 생성
$cert = New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "Cert:\CurrentUser\My"

# PEM 형식으로 내보내기 (추가 도구 필요)
```

### QUIC 테스트

```powershell
# 터미널 1: 서버 실행
py -3 scripts/quic_server.py --cert certs/server.crt --key certs/server.key --port 4433

# 터미널 2: 클라이언트 실행
py -3 scripts/quic_client.py --server localhost:4433 --frames 100
```

---

## 4. VMAF/품질 측정 도구 설치

### FFmpeg 설치 (libvmaf 포함)

**방법 1: 사전 빌드 다운로드 (권장)**

1. https://github.com/BtbN/FFmpeg-Builds/releases 접속
2. `ffmpeg-master-latest-win64-gpl.zip` 다운로드
3. 압축 해제 (예: `C:\ffmpeg`)
4. 환경 변수 PATH에 추가:
   ```powershell
   # PowerShell (관리자 권한)
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\ffmpeg\bin", "User")
   ```

**방법 2: winget 사용**

```powershell
winget install Gyan.FFmpeg
```

### VMAF 지원 확인

```powershell
ffmpeg -filters | findstr vmaf
# 출력: libvmaf ... Calculate the VMAF
```

### VMAF 라벨 생성 테스트

```powershell
py -3 scripts/build_vmaf_labels.py --input data/videos/sample.mp4 --output tmp/vmaf_test.csv
```

---

## 5. 네트워크 에뮬레이션

### Windows에서 사용 가능한 방법

Mininet은 Linux 전용이므로, Windows에서는 다음 방법을 사용합니다:

#### 방법 1: Python 네트워크 에뮬레이터 (권장)

본 프로젝트에 포함된 `scripts/network_emulator.py`를 사용합니다.
실제 TCP 소켓 통신 + 지연/손실 시뮬레이션으로 동작합니다.

```powershell
# 터미널 1: 에뮬레이션 서버 실행
py -3 scripts/network_emulator.py server --port 8080 --profile wifi_congested

# 터미널 2: 클라이언트 실험 실행
py -3 scripts/network_emulator.py client --server localhost:8080 --frames 300 --output tmp/emulation_result.json
```

사용 가능한 네트워크 프로필:
- `wifi_good`: 50Mbps, 10ms RTT, 0.1% 손실
- `wifi_normal`: 20Mbps, 30ms RTT, 0.5% 손실
- `wifi_congested`: 5Mbps, 80ms RTT, 2% 손실
- `lte_good`: 30Mbps, 40ms RTT, 0.2% 손실
- `lte_normal`: 10Mbps, 60ms RTT, 1% 손실
- `lte_poor`: 2Mbps, 150ms RTT, 5% 손실
- `3g`: 1Mbps, 300ms RTT, 3% 손실

프로필 목록 확인:
```powershell
py -3 scripts/network_emulator.py list-profiles
```

#### 방법 2: Clumsy (GUI 네트워크 손상 도구)

1. https://jagt.github.io/clumsy/ 에서 다운로드
2. 실행 후 필터 설정: `outbound and ip.DstAddr == 127.0.0.1`
3. Lag, Drop, Throttle 등 파라미터 조정

#### 방법 3: WSL2 (Linux 환경 사용)

```powershell
# WSL2 설치
wsl --install

# Ubuntu에서 Mininet 설치
sudo apt update
sudo apt install mininet

# Mininet 테스트
sudo mn --test pingall
```

---

## 6. 설치 확인

### 전체 환경 점검 스크립트

```powershell
py -3 scripts/check_installation.py
```

### 수동 확인

```powershell
# Python 패키지
py -3 -c "import numpy, pandas, sklearn, torch; print('Core packages OK')"

# aioquic
py -3 -c "import aioquic; print('QUIC OK')"

# FFmpeg
ffmpeg -version | findstr version

# 네트워크 에뮬레이터
py -3 scripts/network_emulator.py list-profiles
```

---

## 문제 해결

### "Python was not found" 오류

Git Bash에서 발생 시:
```bash
# python 대신 py -3 사용
py -3 scripts/train_importance_model.py ...
```

### aioquic 설치 실패

```powershell
# Visual C++ Build Tools 필요
# https://visualstudio.microsoft.com/visual-cpp-build-tools/ 에서 설치
pip install aioquic
```

### FFmpeg VMAF 미지원

GPL 빌드가 필요합니다. BtbN 빌드에서 `gpl` 버전을 다운로드하세요.

### 포트 충돌

다른 프로세스가 포트를 사용 중일 때:
```powershell
# 포트 사용 확인
netstat -ano | findstr :8080

# 프로세스 종료
taskkill /PID <PID> /F
```

---

## 다음 단계

1. [ML 모델 학습](./training_guide.md)
2. [시뮬레이션 실행](./simulation_guide.md)
3. [실험 결과 분석](./analysis_guide.md)
