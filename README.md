# TCP Content-Aware Adaptive Batching

TCP 환경에서 콘텐츠 유형에 따라 batching 정책이 어떻게 달라져야 하는지를 비교하기 위한 실험 저장소다. 현재 저장소는 연구 계획 문서와 baseline Jupyter 노트북을 포함하며, 이후 full sweep과 학습 기반 적응형 정책 실험으로 확장하는 것을 목표로 한다.

## 현재 포함된 내용

- `init_plan.md`
  - 실험 목적, 가설, 워크로드, 정책, 시뮬레이터 모델, 평가 지표, Mermaid 흐름도를 담은 기준 문서다.
- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`
  - `static_file`과 `dynamic_stream` 대표 시나리오에서 `immediate`, `fixed_batch`, `heuristic_adaptive`를 비교하는 baseline 노트북이다.
- `output/jupyter-notebook/assets/reference_policy_overview.png`
  - 현재 baseline 노트북 실행으로 생성된 기준 그래프다.
- `progress_notes.md`
  - 연구 방향(Heuristic→ML→RL), 문제 정의, 논문/구현 로드맵, 후속 TODO를 기록한 진행 메모다.

## 실험 범위

### 워크로드

- `static_file`
  - 정적 파일 chunk 전송
  - throughput과 goodput 중심으로 해석
- `dynamic_stream`
  - 시간에 따라 계속 갱신되는 메시지 전송
  - latency와 staleness 중심으로 해석

### 정책

- `immediate`
  - 메시지 생성 즉시 flush
- `fixed_batch`
  - 고정 batch size와 flush interval 사용
- `heuristic_adaptive`
  - 콘텐츠 유형과 freshness/RTT를 반영한 규칙 기반 적응
- `ml_regression_adaptive`
  - 계획 문서에는 정의되어 있고, 노트북 다음 단계에서 확장 예정

## 실행 방법

1. Jupyter에서 `output/jupyter-notebook/tcp-content-aware-batching.ipynb`를 연다.
2. 셀을 위에서 아래로 순서대로 실행한다.
3. 필요한 경우 노트북이 `numpy`, `pandas`, `matplotlib`, `seaborn`을 설치한다.
4. 실행이 끝나면 `output/jupyter-notebook/assets/` 아래에 기준 그래프가 저장된다.

## 작업 원칙

- 실험 축이 바뀌면 먼저 `init_plan.md`를 수정한다.
- 그 다음 노트북 상단의 설정과 시나리오를 계획 문서와 맞춘다.
- 노트북 결과물은 발표 자료 재사용을 염두에 두고 `assets/`로 export한다.

## 다음 단계

- [x] `fixed_batch` 전체 sweep 셀 추가
- [x] scenario별 oracle 설정 추출
- [x] `RandomForestRegressor` 기반 `ml_regression_adaptive` 셀 추가
- [x] heatmap, Pareto scatter, CSV export 추가
- [ ] RL 실험용 환경(`rl/env.py`) 설계 초안 작성

## 비공개 저장소 메모

이 저장소는 현재 로컬 Git 저장소만 존재하고 원격이 설정되어 있지 않다. 저장소를 비공개로 운영하려면 GitHub, GitLab 같은 원격 호스팅 서비스에 private repository를 만든 뒤 그 원격으로 push해야 한다.
