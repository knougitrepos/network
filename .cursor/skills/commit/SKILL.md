---
name: commit
description: >-
  Reviews status and diffs, drafts a Korean commit message, then runs git add -A and git commit with that
  message without asking for separate approval. Stops before git push; the user pushes manually.
  Use when the user types /commit or asks to commit.
---

# Git commit (프로젝트 규칙)

## 트리거

- 사용자가 `/commit`, "커밋해줘", "커밋 메시지 작성", "commit" 등을 요청할 때 이 스킬을 따른다.

## 핵심 규칙 (필수)

- **커밋 전 별도 동의 절차는 두지 않는다.** 요약과 한글 메시지 초안을 제시한 뒤 곧바로 **`git add -A` → 한글 메시지로 `git commit`** 을 실행한다. ([AGENTS.md](AGENTS.md) 준수)
- **에이전트 수행 범위는 푸시 직전까지다:** 로컬 커밋까지 끝낸다.
- **`git push`는 에이전트가 실행하지 않는다.** 원격 반영은 사용자가 로컬에서 직접 수행한다.
- 커밋 메시지는 **한글**로 작성한다. **완전한 문장**, **문법 정확**, **변경 요청과 직접 관련된 내용만** 포함한다.
- 스테이징은 저장소 **전체 범위**로 한다: **`git add -A`** (추적 파일 변경·삭제 + 추적되지 않은 신규 파일 모두 포함). 일부 파일만 골라 `git add`하지 않는다.

## 워크플로

1. **상태 확인**: `git status` (및 필요 시 `git diff`, `git diff --cached`) 실행해 변경 범위를 파악한다.
2. **요약**: 사용자에게 무엇이 바뀌었는지 짧게 요약한다 (파일/목적 중심).
3. **메시지 초안**: **한글**로 제안한다.
   - **한 줄 제목 + 본문(선택)**: 제목은 50자 내외 권장, 본문에는 "무엇을", "왜"를 문장으로.
   - 필요 시 타입 접두어는 한글 문장과 함께 쓸 수 있다 (예: `기능:`, `docs:` 등은 선택).
4. **한글 메시지 제시**: 제목·본문을 포함한 **한글 메시지 초안**을 응답에 적는다.
5. **스테이징·커밋 (한 번에, 동의 없이 진행)**: 곧바로 **`git add -A`** 실행 후, 위 메시지로 **`git commit`** 을 실행한다. 본문이 있으면 `-m` 두 번(또는 임시 파일·here-string)으로 본문까지 포함한다.
6. **종료 지점**: 로컬 커밋이 성공하면 에이전트 작업은 끝이다. **`git push`는 실행하지 않는다.**
7. **푸시 안내**: 사용자에게 `git push`는 직접 실행하라고 한 줄 안내한다.

## 코드/문서 변경 시

- **의미 있는 문서 변경**이 있으면 [docs/changelog/](docs/changelog/)에 **날짜별 신규 파일** append가 필요한지 사용자에게 제안한다. 기존 changelog 파일은 수정하지 않는다 ([AGENTS.md](AGENTS.md)).

## 피해야 할 것

- **`git push` 실행**(항상 사용자 몫)
- 변경과 무관한 장황한 메시지, 식별자 나열만 있는 메시지
- 사용자에게 실행을 넘기기만 하고 상태/diff를 확인하지 않는 것

## 예시 (메시지 톤, 한글)

```
문서: AGENTS.md 추가 및 docs/ 폴더 구조 규칙 정리

문서를 네 가지 카테고리로 나누고, changelog와 analyze 작성 시점을 구분하도록
기록했다.
```
