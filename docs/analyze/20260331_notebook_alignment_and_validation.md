# 2026-03-31 노트북 정체성 및 구성 점검

## 요청 내용

- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`의 첫 번째 마크다운 셀이 연구 정체성과 맞는지 점검
- 노트북 전체 구성이 올바른지 확인하고 필요한 교정 수행

## 주요 점검 결과

1. 첫 번째 마크다운 셀의 기존 문구는 부적절했다.
- `TCP Video-Aware Adaptive Batching`
- `shared TCP batching simulator`
- `Keep the research scope TCP-centric`

위 표현들은 본 연구를 단순 TCP batching 최적화처럼 보이게 만들어 AGENTS 지침의 연구 정체성과 충돌했다.

2. 노트북 후반부 산출물 점검 셀이 현재 서사와 맞지 않았다.
- 앞부분에서 생성하는 산출물과 후반부 자동 로드 대상이 서로 달랐다.
- 따라서 노트북을 읽는 입장에서 “무엇을 만들고 무엇을 검증하는지” 흐름이 끊겼다.

3. 코드 셀 주석과 실행 상태가 정리되어 있지 않았다.
- 일부 코드 셀은 `# cell N : 목적` 형식을 따르지 않았다.
- 실행 카운트와 출력 상태가 일부만 남아 있어 재현성 관점에서 깔끔하지 않았다.

4. 외부 importance 모델 검증은 겉보기와 달리 정확하지 않았다.
- `importance_rf.pkl`, `importance_rf_delta_qoe.pkl` 메타데이터의 `dataset_features`는 `11`이었다.
- 현재 `policy.importance.build_importance_features()`는 `13`개 feature를 생성한다.
- 이 불일치 때문에 ML scorer가 반복적으로 heuristic fallback으로 내려가고 있었고, 비교 셀은 정상 실행되더라도 실제로는 ML 비교가 왜곡될 수 있었다.

## 수행한 교정

- 첫 마크다운 셀을 `content-aware cross-layer adaptive transport` 관점으로 재서술했다.
- `Experiment Scope`, validation 문구를 “고정 batching 정책은 baseline이고, 연구 초점은 콘텐츠 중요도 기반 적응 전송”이라는 구조로 정리했다.
- 후반부 artifact review 셀이 실제 생성 산출물(`reference_summary.csv`, `ml_eval_results.csv`, `oracle_selection.csv`, 주요 PNG)만 읽도록 수정했다.
- 모든 코드 셀 헤더를 ASCII 기반 `# cell N : ...` 형식으로 통일했다.
- 노트북의 `execution_count`와 `outputs`를 정리해 저장 상태를 일관되게 맞췄다.
- 외부 모델 준비 셀에서 현재 feature schema를 계산하고, 모델/메타가 없거나 schema가 stale하면 자동 재학습하도록 보강했다.

## 판단

- 1번 질문의 답은 **아니오**였다. 기존 첫 번째 마크다운 셀은 연구 정체성과 맞지 않았다.
- 현재 노트북은 연구 서술, 셀 구성, 산출물 검증 흐름, 외부 모델 정합성 측면에서 교정되었다.
- 파일명 `tcp-content-aware-batching.ipynb` 자체는 구식 표현이지만, `README.md`와 기존 changelog/analyze 문서에서 이미 참조 중이어서 이번 수정에서는 내부 내용 정합성 교정에 우선순위를 두고 파일명은 유지했다.

## 검증 결과

- JSON 파싱 성공
- 모든 코드 셀 컴파일 성공
- 노트북 top-to-bottom 실행 성공
- 외부 importance 모델 2종을 현재 13-feature schema에 맞춰 자동 재학습함
- 재실행 시 ML scorer fallback warning 없이 비교 셀이 통과함
