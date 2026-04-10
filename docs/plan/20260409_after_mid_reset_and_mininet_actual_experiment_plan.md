# after-mid 브랜치 초기화 및 실제 Mininet 실험 중심 재구성 계획

## 요약

- `after-mid` 브랜치는 기존 누적 산출물을 이어받는 브랜치가 아니라, 중간보고 이후를 새로 시작하는 기준 브랜치로 재정의한다.
- 기존 `docs/`는 과거 이력 보존보다 현재 기준의 최소 문서 세트만 남기는 방향으로 전체 초기화한다.
- `AGENTS.md`는 after-mid 전용 운영 규칙으로 전면 재작성한다. 핵심 원칙은 `실제 데이터 우선`, `mock 금지`, `실제 비디오/실제 전송/실제 수치만 허용`, `문서 최소화`, `현재 실험 흐름 중심 정리`다.
- 저장소 구조도 이 원칙에 맞게 실험 파이프라인 중심으로 재배열한다. 즉 `비디오 준비 → 프레임 메타데이터 생성 → Mininet 실제 전송 실험 → 결과 집계 → 노트북 시각화`의 단일 흐름으로 정리한다.

## 문서와 AGENTS 재구성

- `docs/` 전체를 초기화한다.
  - 기존 `docs/analyze/*`, `docs/changelog/*`, 부가 보고서, 설치 가이드, 상세 보고서는 모두 제거한다.
  - 남길 문서는 새 기준으로 다시 작성한 최소 세트만 둔다.
    - `docs/initial_plan.md`: after-mid 시작 시점의 새 실험 스냅샷
    - `docs/research_goal.md`: 현재 연구 방향과 즉시 실행할 단계
    - `docs/changelog/`: after-mid 이후 변경 이력만 새로 누적
    - `docs/analyze/`: after-mid 이후 새 분석 요청만 기록
    - `docs/plan/`: after-mid 이후 계획 문서 누적
- `AGENTS.md`를 after-mid 전용으로 재작성한다.
  - 본 브랜치는 중간보고 이후 새 출발 브랜치다.
  - mock, synthetic, fallback, dummy 데이터 금지
  - 모든 실험은 실제 비디오 파일과 실제 네트워크 전송 기반이어야 함
  - trace/CSV는 원본 비디오에서 생성된 캐시만 허용
  - docs는 최소 유지, 과거 브랜치 문서 관행 승계하지 않음
  - after-mid 이후부터만 changelog/analyze append-only 적용
  - plan으로 수립한 계획은 `docs/plan/YYYYMMDD_플랜제목.md`로 남김
  - 코드 구조는 `읽기 쉬운 흐름, 축약 없는 변수명, 짧은 함수, dataclass 중심`을 기본 원칙으로 함

## 저장소 구조 재정리

- 프로젝트 흐름을 실제 Mininet 실험 중심으로 재구성한다.
  1. 원본 비디오 입력
  2. 프레임 메타데이터/전송 단위 준비
  3. Stage A/B 정책 적용
  4. Mininet에서 실제 TCP/UDP 전송
  5. 실제 송수신 시간으로 지표 계산
  6. 노트북 시각화 및 보고서용 표 생성
- 디렉토리 역할을 명확히 다시 정리한다.
  - `core/`: 공통 실험 엔진, 메트릭, 전송 추상
  - `policy/`: Stage A/B 정책
  - `scripts/`: 실제 실행 스크립트만 유지
  - `output/`: after-mid 산출물 전용 경로로 재정의
  - `dataset/`: 원본 비디오와 원본 기반 캐시만 보관
- 불필요하거나 혼란을 주는 산출 중심/구상 중심 구조는 제거한다.
  - 문서에만 있고 코드에 없는 가상 실행 경로
  - mock 전제 설명
  - Windows-only 대체 실험 흐름
  - 현재 계획과 맞지 않는 오래된 중간보고 전용 설명
- 노트북 역할을 제한한다.
  - 노트북은 실험 오케스트레이션과 분석만 담당
  - 정책 판단, Mininet 실행, 전송 이벤트 기록, 요약 계산은 모두 Python 스크립트가 담당
- 이름과 흐름을 단순화한다.
  - 스크립트/노트북/출력 이름은 `midreport`, `todo`, `mock`, `bootstrap` 같은 과거 맥락 대신 `mininet_actual_experiment`, `video_trace_prepare`, `experiment_summary`처럼 현재 목적이 드러나게 정리한다.

## 실제 Mininet 실험 구현 기준

- 실험은 반드시 실제 비디오 파일로 수행한다.
  - 입력 비디오는 현재 movie 그룹 3개로 고정
  - 프레임 정보는 실험 전에 실제 MP4에서 추출
  - 전송 payload 역시 실제 프레임 또는 실제 프레임 기반 전송 단위에서 생성
- Mininet 실험은 WSL2 Ubuntu 기준으로 고정한다.
  - Windows 노트북이 `wsl`로 실험 스크립트를 호출
  - WSL2/Mininet/ffprobe/PyAV/sudo가 없으면 즉시 실패
  - 대체 실행 경로는 만들지 않음
- 이번 범위는 single-path 실제 전송으로 고정한다.
  - `heuristic_frame_aware`
  - `frame_action_single_path`
  - 네트워크 조건: `3/2/1 Mbps`, `RTT 10 ms`, `loss 0%`
- 출력은 민감도 강조 형식으로 고정한다.
  - `late_frame_ratio` 소수점 8자리
  - `late_frame_count / frame_count` 병기
  - `late_frames_per_1000`
  - `mean_deadline_miss_ms_on_late`
  - `max_deadline_miss_ms`

## 테스트와 검증

- 초기화 검증
  - `docs/`는 새 기준 최소 파일 세트만 남아야 한다.
  - `AGENTS.md`는 after-mid 규칙만 담고 과거 브랜치 운영 관행을 제거해야 한다.
- 구조 검증
  - 저장소 루트에서 `실제 비디오 준비 → 실제 Mininet 실험 → 요약 CSV → 노트북 시각화` 경로가 한 번에 추적 가능해야 한다.
  - mock/fallback 관련 코드, 문구, 옵션이 남아 있지 않아야 한다.
- 실험 검증
  - Mininet 단일 조합 실행이 실제 이벤트 CSV와 실제 요약 CSV를 모두 생성해야 한다.
  - `late_frame_ratio == late_frame_count / frame_count`를 항상 만족해야 한다.
  - movie 그룹 최소 1개 이상에서 `1~3 Mbps` 구간에서 `late_frame_count > 0`가 관찰되어야 한다.
- 회귀 경계
  - 기존 브랜치 역사 보존은 이번 범위가 아니다.
  - `after-mid` 안에서는 현재 계획과 직접 관련 없는 과거 산출물 호환성을 유지 목표로 두지 않는다.

## 가정과 기본값

- `after-mid`는 독립적인 새 출발 브랜치로 간주한다.
- 과거 문서 이력은 유지 대상이 아니다.
- docs append-only 규칙은 after-mid에서 새로 생성되는 문서부터 적용한다.
- 실제 실험 불가능한 환경에서는 기능 축소가 아니라 명시적 실패를 선택한다.
- 저장소 전반 정리는 보기 좋은 정리보다 현재 실제 실험 계획과 정확히 맞는 구조를 우선한다.
