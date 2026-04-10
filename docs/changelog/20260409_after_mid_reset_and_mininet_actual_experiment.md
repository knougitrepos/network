# 20260409 after_mid_reset_and_mininet_actual_experiment

## 배경

- `after-mid` 브랜치를 중간보고 이후의 새 기준 브랜치로 재정의했다.
- 기존 시뮬레이터/중간보고 중심 구조 대신 실제 비디오 기반 Mininet 실험 파이프라인으로 정리했다.

## 구현 내용

- `docs/`를 최소 구조로 초기화했다.
- `AGENTS.md`, `README.md`, `dataset/README.md`, `.gitignore`를 after-mid 기준으로 재작성했다.
- 실제 비디오 프레임 추출, 실제 Mininet 전송, 실제 측정 기반 요약을 위한 공통 모듈과 스크립트를 추가했다.
- 노트북은 오케스트레이션과 분석만 남기도록 분리했다.
- 오래된 중간보고 문서와 산출물을 제거했다.

## 주요 파일

- `AGENTS.md`
- `README.md`
- `core/video_assets.py`
- `core/mininet_actual_experiment.py`
- `scripts/video_trace_prepare.py`
- `scripts/mininet_frame_endpoint.py`
- `scripts/mininet_actual_experiment.py`
- `output/notebooks/mininet_actual_experiment.ipynb`

## 검증

- Python 구문 검사를 수행한다.
- 실제 Mininet 실행은 WSL2 Ubuntu의 `ffprobe`, `PyAV`, `Mininet`, `sudo` 환경을 요구한다.
- 환경이 없으면 스크립트는 명시적으로 실패하도록 설계한다.
