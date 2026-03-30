---
name: ignore
description: >-
  Audits the repository for generated, cache, and local-only files that should not be tracked, then appends
  safe patterns to .gitignore without removing existing rules. Use when the user types /ignore, asks to update
  gitignore, or wants unnecessary files excluded from git.
---

# Gitignore 점검 및 보강 (/ignore)

## 트리거

- 사용자가 `/ignore`, "gitignore 점검", "불필요한 파일 무시" 등을 요청할 때 이 스킬을 따른다.

## 핵심 규칙

- **기존 `.gitignore` 줄은 임의로 삭제하지 않는다.** 충돌이 있으면 사용자에게만 질문한다.
- **프로젝트가 의도적으로 추적하는 경로**(`!` 예외, `data/`, `output/...assets` 등)은 깨뜨리지 않는다. 추가 전에 현재 `.gitignore` 전체를 읽는다.
- **추가는 보통 파일 끝에 주석 블록으로 append** 한다. 중복 패턴은 넣지 않는다.
- **소스 코드·실험에 필요한 데이터·문서**를 무작정 무시 규칙에 넣지 않는다.

## 점검 절차

1. **`.gitignore` 읽기**: 현재 패턴과 `!` 예외를 파악한다.
2. **작업 트리 스캔** (저장소 루트 기준):
   - `git status --short`, 필요 시 `git ls-files --others --exclude-standard`
   - 존재하는 디렉터리/파일: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage`, `*.egg-info/`, `dist/`, `build/`, `.tox/`, `.hypothesis/`, `*.log`, `.env.local` 등
3. **`.cursor/` 처리**: 이미 `.cursor/` 아래 파일을 커밋하는 저장소면 **전체 `.cursor/` 무시를 추가하지 않는다.** 로컬 전용만 무시할 경우 팀 규칙에 맞는 하위 경로만 제안한다.
4. **제안 목록 작성**: “무엇을 왜 무시할지” 한글로 짧게 정리한다.
5. **`.gitignore` 갱신**: 아래 **권장 패턴** 중 아직 없는 것만 복사해 append한다. 이미 있으면 스킵한다.

## 권장 패턴 (Python·실험 저장소, 없을 때만 추가)

```gitignore
# --- /ignore skill: Python tooling caches ---
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
.hypothesis/
htmlcov/
.coverage
.coverage.*
coverage.xml
*.cover

# --- /ignore skill: build artifacts ---
*.egg-info/
dist/
build/
pip-wheel-metadata/

# --- /ignore skill: logs / temp ---
*.log
*.tmp
```

프로젝트에 맞게 **로컬 대용량 입력만** 임시로 두는 폴더가 있으면(예: `tmp/video-traces/`만 무시) **구체 경로**로 추가하고, 루트 `tmp/`가 이미 있으면 중복 추가하지 않는다.

## 피해야 할 것

- 추적 중인 파일을 무시 규칙만으로 제거하려는 시도(필요하면 `git rm --cached`는 **별도 사용자 동의** 후)
- `*.md`, `*.py`, `docs/`, `data/video-traces/` 등 **연구·재현에 필요한 경로**를 광범위하게 무시
- 기존 `!` 예외와 모순되는 와일드카드 추가

## 완료 보고

- 추가한 패턴 요약
- 건드리지 않은 이유(이미 존재 / 추적 파일과 충돌 등)
- 원격에 반영하려면 사용자가 직접 `git add .gitignore` 후 커밋·푸시
