# 2026-04-02 중간보고용 노트북 간소화 리팩토링

## 변경 배경

- 기존 `output/jupyter-notebook/tcp-content-aware-batching.ipynb`는 연구 전체 실험을 포함해 중간보고에서 설명하기에 복잡도가 높았다.
- 중간보고 목적에 맞춰 **IPB 특성 분석 중심**으로 빠르게 실행/해석 가능한 별도 노트북이 필요했다.
- 사용자가 직접 넣는 비디오(`dataset/videos/`)를 대상으로 유사 계열 분석을 수행할 수 있도록 입력 경로를 단순화했다.
- 추가로, 수동 파일 배치 의존성을 줄이기 위해 **공개 데이터셋 자동 다운로드 기반 재현성 경로**를 포함하도록 보강했다.

## 구현 내역

1. 데이터셋 스캐폴드 추가
   - `dataset/videos/` (원본 비디오 입력)
   - `dataset/traces/` (추출 trace CSV)
   - `dataset/README.md` (파일명/메타 규칙)

2. 중간보고 전용 노트북 신규 생성
   - 파일: `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`
   - 구성 원칙:
     - 셀 수 최소화
     - 각 코드 셀 상단 `# cell N : 목적` 주석
     - IPB/GOP 특성 + 최소 효율 지표만 유지

3. 자동 trace 생성 파이프라인 연결
   - `scripts/extract_video_trace.py`를 노트북 내부에서 호출
   - `dataset/traces/*_trace.csv`가 없을 때만 생성(캐시 재사용)

4. 중간보고 산출물 경로 통일
   - `output/jupyter-notebook/assets/midreport/`
   - 생성 파일:
     - `midreport_ipb_summary.csv`
     - `midreport_transport_efficiency.csv`
     - `midreport_ipb_ratio.png`
     - `midreport_late_frame_ratio.png`

5. 연구 목표 문서 동기화
   - `docs/research_goal.md`에 `중간보고용 간소 분석 경로` 섹션 추가
   - `최종 갱신` 날짜 업데이트

6. 재현성/설명성 개선 (보강)
   - 공개 데이터셋 소스 목록(`PUBLIC_VIDEO_SOURCES`) 기반 자동 다운로드 셀 추가
   - 다운로드 실패 시 수동 입력(`dataset/videos`) fallback 유지
   - 상단 설명 셀에 아래 항목을 상세 추가:
     - `dataset/videos` vs `dataset/traces` 역할
     - `late_frame_ratio` 의미(낮을수록 우수)
     - `frame_action_adaptive` 정책 정의(행동 매핑 기반)
   - 정책 비교 차트 제목/축/해석 문구를 중간보고 친화적으로 보강

## 변경/생성 파일 목록

- 생성
  - `dataset/README.md`
  - `output/jupyter-notebook/midreport_ipb_transport_summary.ipynb`
  - `docs/changelog/20260402_midreport_simplified_notebook.md`
- 수정
  - `docs/research_goal.md`

## 검증 계획

- `dataset/videos/`에 샘플 비디오 1개 이상 추가 후 노트북 전체 실행
- `dataset/traces/`에 trace CSV 자동 생성 확인
- `output/jupyter-notebook/assets/midreport/`에 CSV/PNG 산출물 생성 확인
- IPB 비율 그래프와 정책별 late frame 그래프가 정상 표시되는지 확인
- 공개 데이터셋 URL이 실패하더라도 수동 입력 비디오가 있으면 분석이 계속되는지 확인
