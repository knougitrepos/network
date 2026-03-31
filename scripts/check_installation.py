"""Windows 환경 설치 점검 스크립트.

모든 필수 의존성이 올바르게 설치되었는지 확인한다.

사용 예시:
    python scripts/check_installation.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def check_python() -> Tuple[bool, str]:
    """Python 버전 확인."""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python 3.9+ 필요 (현재: {version.major}.{version.minor})"


def check_core_packages() -> Tuple[bool, str]:
    """핵심 패키지 확인."""
    required = ["numpy", "pandas", "sklearn", "matplotlib", "seaborn"]
    missing = []
    
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        return False, f"누락: {', '.join(missing)}"
    return True, "numpy, pandas, sklearn, matplotlib, seaborn"


def check_torch() -> Tuple[bool, str]:
    """PyTorch 확인 (선택)."""
    try:
        import torch
        cuda = "CUDA 사용 가능" if torch.cuda.is_available() else "CPU 전용"
        return True, f"PyTorch {torch.__version__} ({cuda})"
    except ImportError:
        return None, "미설치 (선택 사항)"


def check_aioquic() -> Tuple[bool, str]:
    """aioquic (QUIC 스택) 확인."""
    try:
        import aioquic
        return True, f"aioquic {aioquic.__version__}"
    except ImportError:
        return False, "미설치 - pip install aioquic"


def check_ffmpeg() -> Tuple[bool, str]:
    """FFmpeg 확인."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False, "미설치 - PATH에 ffmpeg 추가 필요"
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
        version_line = result.stdout.split("\n")[0]
        return True, version_line.replace("ffmpeg version ", "")
    except Exception as e:
        return False, f"실행 오류: {e}"


def check_vmaf() -> Tuple[bool, str]:
    """FFmpeg VMAF 지원 확인."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True,
            text=True,
            check=False,
        )
        if "libvmaf" in result.stdout:
            return True, "libvmaf 필터 사용 가능"
        return False, "libvmaf 미포함 - GPL 빌드 필요"
    except Exception:
        return None, "FFmpeg 설치 필요"


def check_certificates() -> Tuple[bool, str]:
    """QUIC 인증서 확인."""
    cert_path = Path(__file__).parent.parent / "certs" / "server.crt"
    key_path = Path(__file__).parent.parent / "certs" / "server.key"
    
    if cert_path.exists() and key_path.exists():
        return True, f"인증서 존재: {cert_path.parent}"
    return False, "certs/server.crt, certs/server.key 생성 필요"


def check_data_files() -> Tuple[bool, str]:
    """필수 데이터 파일 확인."""
    data_dir = Path(__file__).parent.parent / "data"
    traces_dir = data_dir / "video-traces"
    
    if not traces_dir.exists():
        return False, "data/video-traces/ 디렉토리 없음"
    
    csv_files = list(traces_dir.glob("*.csv"))
    if not csv_files:
        return False, "video-traces 디렉토리에 CSV 파일 없음"
    
    return True, f"{len(csv_files)}개 trace 파일"


def check_network_emulator() -> Tuple[bool, str]:
    """네트워크 에뮬레이터 확인."""
    emulator_path = Path(__file__).parent / "network_emulator.py"
    if emulator_path.exists():
        return True, "scripts/network_emulator.py"
    return False, "network_emulator.py 미존재"


def main() -> int:
    """설치 상태 점검."""
    print("=" * 60)
    print("Windows 환경 설치 점검")
    print("=" * 60)
    print()
    
    checks = [
        ("Python 버전", check_python),
        ("핵심 패키지", check_core_packages),
        ("PyTorch (선택)", check_torch),
        ("QUIC 스택 (aioquic)", check_aioquic),
        ("FFmpeg", check_ffmpeg),
        ("VMAF 지원", check_vmaf),
        ("QUIC 인증서", check_certificates),
        ("데이터 파일", check_data_files),
        ("네트워크 에뮬레이터", check_network_emulator),
    ]
    
    results = []
    
    for name, check_func in checks:
        status, detail = check_func()
        results.append((name, status, detail))
        
        if status is True:
            icon = "✓"
            color = "\033[92m"  # 녹색
        elif status is False:
            icon = "✗"
            color = "\033[91m"  # 빨강
        else:
            icon = "○"
            color = "\033[93m"  # 노랑
        
        reset = "\033[0m"
        print(f"  {color}{icon}{reset} {name}: {detail}")
    
    print()
    print("-" * 60)
    
    # 요약
    required = [r for r in results if r[0] not in ("PyTorch (선택)",)]
    failed = [r for r in required if r[1] is False]
    
    if not failed:
        print("\033[92m✓ 모든 필수 항목 설치 완료!\033[0m")
        print()
        print("다음 단계:")
        print("  1. 네트워크 에뮬레이터 테스트:")
        print("     py -3 scripts/network_emulator.py server --port 8080")
        print()
        print("  2. ML 모델 학습:")
        print("     py -3 scripts/train_importance_model.py \\")
        print("       --trace data/video-traces/bbb_720p_trace.csv \\")
        print("       --output tmp/models/importance_rf.pkl")
        return 0
    else:
        print("\033[91m✗ 설치 필요 항목:\033[0m")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        print()
        print("설치 가이드: docs/windows_setup_guide.md 참조")
        return 1


if __name__ == "__main__":
    sys.exit(main())
