# 스펙 001 — ai-chat-curator 하네스 구축

- **상태**: Done
- **모드**: 하네스 구축
- **개설**: 2026-11-23 · **완료**: 2026-11-23
- **관련 스펙**: 없음

## 요구 (발주 요지)

카카오톡 오픈채팅방 「직장인 AI 활용방 · ChatGPT · Claude · Gemini」에 올릴 글감을 공식·언론·커뮤니티·실무자 글 네 관점에서 병렬로 찾고, 원출처 기준으로 묶고, 커뮤니티발 이야기는 공식 출처로 교차 확인한 뒤, 카톡에 바로 붙여 넣을 짧은 문안(3~5개)과 후보 목록(10개 내외)을 만드는 하네스. 게시는 사람이 한다. Pixel Agents에서 단계가 캐릭터로 보이도록 단계마다 서브에이전트(Agent 도구)로 나눈다.

발주 문서: `C:\pe\prompts\ai-chat-curator.md.txt`

## 범위 / 비범위

- **범위**: 에이전트 5종, 스킬 6종(진입 1 + 단계 5), 보조 스크립트(문안 형식 점검·게시 기록 관리), 하네스 홈 `CLAUDE.md`, `.claude/settings.json`(WebSearch·WebFetch 허용만), `posted.md` 초기 파일, `feedback.md` 양식, 스펙 대장
- **비범위**: 카카오톡 게시·자동 전송, 로그인이 필요한 출처 수집, 오픈채팅방 홍보(`ax-channel-scout` 담당), 실제 글감 탐색 실행(첫 실행은 후속 스펙), Workflow 스크립트(Pixel Agents 가시성을 위해 쓰지 않음)

## 입력 스냅샷

| 입력 | 경로 | 기준 시점 |
|------|------|----------|
| 발주 문서 | `C:\pe\prompts\ai-chat-curator.md.txt` | 2026-11-23 |
| 참고 하네스 | `$HARNESS_ROOT/ax-channel-scout/` | 2026-11-23 |

## 계획 (Phase 매핑)

| Phase | 담당 | 산출물 |
|-------|------|--------|
| 설계 | 메인 | 실행 모드(서브에이전트 위임)·에이전트 구성 |
| 에이전트·스킬 작성 | 메인 | `.claude/agents/`, `.claude/skills/` |
| 스크립트 | 메인 | `ai-chat-curator/scripts/curator.py` |
| 검증 | 메인 | 구조 점검·스크립트 자체 테스트·모의 실행 |

## 수용 기준

- 에이전트 파일 이름과 프론트매터 `name`이 같고 `ai-chat-curator_` 접두사를 쓴다
- 스킬 정의 파일은 모두 `SKILL.md`이고 `name`·`description`이 있다
- 출처 관점 a~d 수집, 교차 확인, 문안 작성, 문안 검증이 각각 짧은 한국어 `description`의 Agent 호출로 분리돼 있다
- 검증 체크리스트 9항목이 검증 스킬에 모두 있다
- 최종 문안 검토에서 사람 응답을 기다리는 지점이 있다
- `posted.md` 중복 제외·`feedback.md` 반영 절차가 있다
- `.claude/settings.json`의 허용 목록은 WebSearch·WebFetch뿐이다
- 오케스트레이터에 스펙 훅·출력 폴더 `CLAUDE.md` 훅·오류 처리·테스트 시나리오가 있다
- `curator.py` 자체 테스트 통과

## 결정 기록

| 날짜 | 결정 | 사유 |
|------|------|------|
| 2026-11-23 | 발주 문서를 합의된 범위로 보고 In Progress로 개설 | 범위·산출물·검증 기준이 문서에 구체적으로 정해져 있음 |
| 2026-11-23 | 실행 모드는 서브에이전트 위임(Workflow 미사용) | Pixel Agents는 Agent 호출만 캐릭터로 보여 준다는 요구. 단계 사이에 사람 확인 지점도 있음 |
| 2026-11-23 | 하네스 폴더 `$HARNESS_ROOT/ai-chat-curator/`를 원본 겸 실행 프로젝트로 둔다 | 발주의 `posted.md` 경로와 settings.json 위치가 이 폴더. 기존 하네스(ax-channel-scout)와 같은 방식 |
| 2026-11-23 | 수집 에이전트는 정의 1개를 관점별로 4번 호출 | 관점마다 다른 것은 출처 목록뿐이라 스킬 참조 문서로 나누는 편이 중복이 적음 |
| 2026-11-23 | 게시 기록은 문안을 사람에게 보여 줄 때 `제안` 상태로 적고, 사람이 게시했다고 하면 `게시`로 바꾼다 | "제안했던 글도 다시 제안하지 않는다"는 요구 |

## 실행 로그

| 날짜 | 이벤트 | 결과 |
|------|--------|------|
| 2026-11-23 | 0단계 점검 | `$HARNESS_ROOT/ai-chat-curator/` 없음 → 새로 구축. 기존 하네스와 이름 충돌 없음 |
| 2026-11-23 | 에이전트 5·스킬 6 작성 | `.claude/agents/ai-chat-curator_*.md`, `.claude/skills/ai-chat-curator*/` |
| 2026-11-23 | 보조 스크립트 | `scripts/curator.py` — selftest 13항목 통과 |
| 2026-11-23 | 구조 점검 | 이름=파일 5/5, SKILL.md 6/6, 상호 참조 누락 0, v1 잔재·commands 없음, settings 허용 2개 |
| 2026-11-23 | 모의 실행 | 샘플 문안 형식 점검·`posted-add --only` 통과. 수정 라운드에서 자기 제안 링크를 중복으로 잡는 결함 발견 → `--ignore-proposed-on` 추가 |

## 완료 기록

- 산출물: `CLAUDE.md`, `posted.md`, `.claude/settings.json`, `.claude/agents/`(5), `.claude/skills/`(6, 참조 문서 3, 스크립트 1), `$HARNESS_ROOT/inputs/ai-chat-curator/feedback.md` 양식, `$HARNESS_ROOT/outputs/ai-chat-curator/`
- 검증: 수용 기준 9개 충족(구조·스크립트 자체 테스트·모의 실행)
- 남긴 것: 실제 웹 탐색을 포함한 실행 테스트(스킬 적용 vs 기준 비교)와 호출 조건 경계 테스트는 하지 않았다 — 첫 실행("오늘 글감 찾아줘")을 스펙 002로 열어 실제 결과로 확인할 것. 출처 목록(`sources.md`)의 robots.txt 허용 여부는 수집 시점에 확인하도록 해 두었고 미리 전수 확인하지 않았다
