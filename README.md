# after-mid: 실제 비디오 기반 Cross-Layer 적응 전송 실험

이 저장소는 `after-mid` 브랜치 기준으로 다시 정리된 실험 저장소다.  
목표는 실제 MP4 비디오를 입력으로 사용하고, Stage A/B 정책을 거쳐 Mininet 상의 실제 TCP/UDP 전송 결과로 지표를 계산하는 것이다.

## 핵심 원칙

- mock, synthetic, fallback, dummy 로직을 두지 않는다.
- 실험 입력은 실제 비디오 파일이다.
- trace CSV는 원본 비디오에서 생성한 캐시다.
- 실험 결과는 실제 송수신 시각과 실제 전송 바이트로부터 계산한다.
- Mininet, ffprobe, PyAV가 없으면 대체 경로 없이 실패한다.

## 저장소 구조

```text
core/
  video_assets.py                # 실제 비디오에서 프레임 메타데이터/전송 바이트 추출
  mininet_actual_experiment.py   # 이벤트 기록, 요약 집계, CSV 저장

policy/
  importance.py                  # Stage A: 중요도 계산
  action.py                      # Stage B: 전송 행동 결정
  legacy.py                      # heuristic_frame_aware용 배치/flush 규칙

scripts/
  video_trace_prepare.py         # 실제 비디오 -> trace CSV 생성
  mininet_frame_endpoint.py      # Mininet client/server 전송 엔드포인트
  mininet_actual_experiment.py   # 실제 Mininet 실험 러너

dataset/
  videos/                        # 실제 MP4 입력
  traces/                        # 원본 비디오 기반 캐시 CSV

output/
  notebooks/                     # 실험 오케스트레이션/분석 노트북
  mininet_actual_experiment/     # 실제 실험 산출물

docs/
  initial_plan.md
  research_goal.md
  changelog/
  analyze/
  plan/
```

## 실험 흐름

1. `dataset/videos/`의 실제 MP4를 준비한다.
2. `scripts/video_trace_prepare.py`로 프레임 메타데이터와 trace CSV를 생성한다.
3. 정책은 `heuristic_frame_aware`, `frame_action_single_path`, `deadline_feasible_frame_action`을 사용한다.
4. `scripts/mininet_actual_experiment.py`가 WSL2 Ubuntu의 Mininet에서 실제 전송을 수행한다.
5. 결과는 `late_frame_ratio`, `late_frame_count / frame_count`, `late_frames_per_1000`, byte/action 기반 지표 등으로 저장한다.
6. 노트북은 결과 CSV를 읽어 표와 그래프만 만든다.

## 현재 기본 실험 범위

- 비디오:
  - `archive_popeye_512kb`
  - `echo_mediaelement`
  - `w3c_movie_300`
- 네트워크:
  - single-path
  - `1 Mbps`, `2 Mbps`, `3 Mbps`, `5 Mbps`
  - `RTT 10 ms`, `50 ms`, `100 ms`
  - `loss 0%`, `1%`, `3%`
- 정책:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - `deadline_feasible_frame_action`

`RTT 10 ms / loss 0%`가 아닌 조건은 출력 경로 충돌을 피하기 위해
`<bandwidth>mbps_rtt<RTT>ms_loss<loss>pct` 형식의 조건 디렉터리에 저장한다.

## 실행 전 요구사항

- Windows + WSL2 Ubuntu
- WSL2 내부 `python3`
- WSL2 내부 `ffprobe`
- WSL2 내부 `PyAV`
- WSL2 내부 `Mininet`
- `sudo` 권한

환경이 충족되지 않으면 실험 스크립트는 명시적으로 실패한다.
