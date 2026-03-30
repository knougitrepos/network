# 2026-03-30 — ΔQoE proxy 라벨 생성 스크립트 추가

## 변경 배경

Stage A v2 학습을 위해 frame-level 라벨이 필요하지만,
현재는 실측 VMAF 기반 ΔQoE 라벨 파이프라인이 준비되지 않았다.

이번 변경에서는 학습 실험을 시작할 수 있도록
proxy 방식의 ΔQoE 라벨 생성 스크립트를 추가했다.

## 구현 내역

1. 라벨 생성 스크립트 추가
- `scripts/build_delta_qoe_labels.py`
- 처리 흐름:
  - trace CSV 로드
  - baseline 전송 완료/마감(on_time) 레코드 생성
  - 프레임별 drop 시나리오 적용
  - `compute_all_video_metrics()` 기반 지표 계산
  - proxy QoE 점수 차이(`delta_qoe`) 계산
  - 정규화 라벨(`delta_qoe_norm`) 생성
- key frame drop 시 동일 GOP를 디코딩 실패로 처리하는 초안 규칙을 포함

2. 산출 포맷
- 출력 CSV 기본 경로: `data/video-traces/bbb_720p_delta_qoe_labels.csv`
- 주요 컬럼:
  - `event_idx`, `frame_type`, `key_frame`, `gop_id`
  - `baseline_qoe`, `drop_qoe`, `delta_qoe`, `delta_qoe_norm`
  - `label_mode=delta_qoe_proxy_v1`

3. 문서 반영
- `README.md`
- scripts 목록에 라벨 스크립트 추가
- 재현 명령 예시에 실행 커맨드 추가

## 생성/변경 파일 목록

### 생성
- `docs/changelog/20260330_delta_qoe_label_bootstrap.md`
- `scripts/build_delta_qoe_labels.py`

### 변경
- `README.md`

## 검증 결과

1. 문법 검증
- `py -3 -m compileall scripts` 통과

2. 런타임 검증
- `py -3 scripts/build_delta_qoe_labels.py --trace data/video-traces/bbb_720p_trace.csv --output data/video-traces/bbb_720p_delta_qoe_labels.csv`
- 라벨 CSV 생성 및 frame type별 요약 로그 출력 확인

## 영향 범위

- 기존 시뮬레이터/정책 로직은 변경하지 않는다.
- v2 학습용 라벨 파이프라인 초안을 제공해 다음 단계(실측 라벨 대체)로 연결한다.
