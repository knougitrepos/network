# 2026-03-31 노트북 import 경로 순서 수정

## 변경 배경

`output/jupyter-notebook/tcp-content-aware-batching.ipynb`의 첫 번째 코드 셀에서
`from policy.importance import NetworkState, build_importance_features`가
저장소 루트를 `sys.path`에 추가하기 전에 실행되고 있었다.

이 순서 때문에 Jupyter 환경에 따라 `ModuleNotFoundError: No module named 'policy'`가 발생했다.

## 구현 내역

- 첫 번째 코드 셀에서 `resolve_repo_root()`와 `sys.path.insert()`를 먼저 수행하도록 순서 조정
- `policy.importance` import를 저장소 루트 등록 이후로 이동

## 생성/변경 파일 목록

- `output/jupyter-notebook/tcp-content-aware-batching.ipynb`
- `docs/changelog/20260331_notebook_import_path_fix.md`

## 검증 결과

1. 첫 번째 코드 셀 단독 실행 성공
- `policy.importance` import 통과
- `CELL1_OK` 확인

2. 영향 범위
- 노트북 첫 셀의 import 순서만 수정
- 시뮬레이션 로직이나 모델 학습 로직의 동작 자체는 변경하지 않음
