# AGENTS.md — 프로젝트 지침

## 연구 정체성

- 본 연구는 **단순 TCP batching 최적화가 아니다**.
- TCP/QUIC 전송 계층 결정(Grazia 2021, Borisov 2025)에 **콘텐츠 중요도**(Tüker 2024)를 ML/RL 기반으로 통합하는 **cross-layer 적응 전송 연구**다.
- 중요도 판단 방법론(heuristic → ML → RL) 고도화가 핵심 기여점이다.
- 연관논문 3편의 역할:
  - **Tüker et al. (2024)**: 콘텐츠 중요도(content-aware) 축의 선행 연구
  - **Grazia et al. (2021)**: TCP 전송 계층 latency 메커니즘(TCP Pacing/TSQ)의 근거
  - **Borisov et al. (2025)**: adaptive batching 필요성의 근거(E2E 성능 추정)
- 문서/코드/커밋 메시지에서 "단순 TCP batching 연구"로 표현하지 않는다. "cross-layer 적응 전송" 또는 "콘텐츠 중요도 기반 적응 전송"으로 표현한다.

## 문서 구조 규칙 (docs/)

모든 프로젝트 문서는 `docs/` 아래 4개 카테고리로 관리한다. 루트에 md 파일을 생성하지 않는다 (README.md 제외).

```text
docs/
  initial_plan.md              # 카테고리 1
  research_goal.md             # 카테고리 3
  changelog/                   # 카테고리 2
    YYYYMMDD_제목.md
  analyze/                     # 카테고리 4
    YYYYMMDD_제목.md
```

### 카테고리 1: 초기 구상 플랜 (`docs/initial_plan.md`)

- 파일 수: 1개 (고정)
- 프로젝트 시작 시점의 실험 설계 기준 문서
- **이후 수정하지 않는다** — 초기 설계 스냅샷 역할

### 카테고리 2: 코드 변경사항 (`docs/changelog/YYYYMMDD_제목.md`)

- 파일 수: 다수 (시간순 누적)
- 코드 변경이 발생할 때마다 해당 날짜로 신규 파일을 생성한다.
- 파일명 형식: `YYYYMMDD_영문_snake_case_제목.md`
- 내용: 변경 배경, 구현 내역, 생성/변경 파일 목록, 검증 결과
- 기존 changelog 파일은 수정하지 않는다 (append-only)

### 카테고리 3: 연구 목표 (`docs/research_goal.md`)

- 파일 수: 1개 (수시 갱신)
- 현재 연구 방향, 아키텍처, 기여 포인트, 후속 작업 로드맵
- 연구 방향이 변경되면 이 파일을 갱신하고, 상단의 `최종 갱신` 날짜를 업데이트한다.

### 카테고리 4: 분석 요청 기록 (`docs/analyze/YYYYMMDD_제목.md`)

- 파일 수: 다수 (시간순 누적)
- 사용자가 "분석해줘", "점검해줘" 등 수동 분석을 요청할 때 생성한다.
- 파일명 형식: `YYYYMMDD_영문_snake_case_제목.md`
- 기존 analyze 파일은 수정하지 않는다 (append-only)

## 코드 규칙

- 응답은 항상 한국어로 작성한다.
- 추가된 라이브러리는 반드시 `requirements.txt`에 추가한다.
- `logging` 모듈을 사용하여 에러 파악이 쉽도록 한다.
- 폴더 이름은 기능 의미를 따른다 (`core/`, `policy/`, `eval/` 등).
- 추상화를 통한 계층적 정리 및 유지보수성을 고려한다.
- 노트북(.ipynb) 셀 상단에 `# cell N : 목적` 형식의 주석을 표기한다.
- Windows에서 `num_workers > 0` 멀티프로세싱 문제에 유의한다.
- **`git add`**: 스테이징은 **`git add -A`**로 저장소 전체 변경분을 포함한다(일부 파일만 선택하지 않는다).
- **`git commit`**: **한글** 메시지(제목·본문)로 에이전트가 실행한다. `/commit` 등 요청 시 **별도 동의 절차 없이** `git add -A` 후 바로 커밋한다.
- **범위**: 에이전트는 **`git add -A` 후 `git commit`까지** 수행하고, **`git push` 직전**에서 멈춘다. 원격 반영(`git push`)은 사용자가 로컬에서 직접 한다.

## 보고서 작성 규칙

- "상세한 보고서 작성" 요청 시 별도 md 파일로 작성한다.
- 파일명 형식: `보고서이름_YYYYMMDD_v버전.md` (예: `중간보고서_보완내용_20260115_v1.md`)
- 실험 방법, 평가 방법 등에 참고 논문과 간략한 설명을 포함한다.
