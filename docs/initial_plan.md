# after-mid 초기 실험 스냅샷

작성일: 2026-04-09

## 목적

- 중간보고 이후 브랜치를 실제 실험 중심으로 재구성한다.
- 실제 비디오 파일 기반 Mininet 실험으로 `late_frame_ratio = 0`처럼 보이던 구간의 미세 변화를 드러낸다.

## 기준 파이프라인

1. 원본 MP4 입력
2. ffprobe/PyAV 기반 프레임 메타데이터 및 payload 추출
3. Stage A 중요도 계산
4. Stage B 전송 행동 결정
5. Mininet 단일 병목 토폴로지에서 실제 TCP/UDP 전송
6. 실제 송수신 시간 기반 지표 계산
7. 노트북 시각화

## 기본 실험 범위

- 비디오:
  - `archive_popeye_512kb.mp4`
  - `echo_mediaelement.mp4`
  - `w3c_movie_300.mp4`
- 정책:
  - `heuristic_frame_aware`
  - `frame_action_single_path`
- 네트워크:
  - `3 Mbps`, `2 Mbps`, `1 Mbps`
  - `RTT 10 ms`
  - `loss 0%`

## 측정 지표

- `late_frame_ratio`
- `late_frame_count / frame_count`
- `late_frames_per_1000`
- `mean_deadline_miss_ms_on_late`
- `max_deadline_miss_ms`

## 금지 사항

- mock 데이터
- synthetic payload
- fallback 실행 경로
- 실제 실험 없이 수식만으로 생성한 결과값
