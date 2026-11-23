# 데이터 형식 — 단계 사이에 주고받는 파일

모든 중간 파일은 실행 폴더 `.ai-chat-curator/runs/{YYYY-MM-DD}_{n}/`에 둔다. 파일 이름은 `{단계}_{에이전트}_{내용}.{확장자}`.

| 파일 | 쓰는 쪽 | 읽는 쪽 |
| --- | --- | --- |
| `00_main_options.json` | 메인 | 모두 |
| `00_main_feedback.md` | 메인 | 정리자·작성자 |
| `01_collector_{a,b,c,d}.json` | 수집자 | 정리자 |
| `02_curator_candidates.json` | 정리자 | 교차 확인자·작성자·검증자 |
| `03_fact-checker_{1,2}.json` | 교차 확인자 | 작성자·검증자 |
| `04_writer_candidates.md` · `04_writer_drafts.md` | 작성자 | 검증자·메인 |
| `05_reviewer_round{r}.json` | 메인(검증자 응답 저장) | 작성자·메인 |
| `06_main_autopick.json` | 메인(`curator.py auto-pick` 결과, 자동 실행만) | 메인 |
| `99_main_failure.md` | 메인(실패 기록) | 사람 |

공통 값
- 유형: `소식` · `업무 팁` · `질문거리` · `팩트체크` · `주의할 점`
- 관련 도구: `ChatGPT` · `Claude` · `Gemini` · `공통`(세 도구 모두, 또는 특정 도구와 무관)
- 출처 유형: `공식` · `언론` · `커뮤니티` · `실무자`
- 날짜: `YYYY-MM-DD`, 모르면 `unknown`

## 실행 옵션 (`00_main_options.json`)

```json
{
  "run_id": "2026-11-23_1",
  "request": "사용자 요청 원문",
  "period": {"from": "2026-11-16", "to": "2026-11-23", "label": "최근 7일"},
  "draft_count": {"min": 3, "max": 5},
  "type_focus": null,
  "tool_focus": null,
  "perspectives": ["a", "b", "c", "d"],
  "output_dir": "outputs/2026-11-23",
  "mode": "manual"
}
```
- `mode`: `manual`(사람이 부름) · `auto`(클라우드 예약 실행, `references/auto-mode.md`)
- `type_focus`: 예 `"업무 팁"`(팁 위주). `null`이면 섞는다
- `tool_focus`: 예 `"Claude"`(Claude 소식만). 지정되면 공정성 항목은 "사용자 지정으로 예외"로 판정한다

## 수집 결과 (`01_collector_{관점}.json`)

```json
{
  "perspective": "c",
  "period": {"from": "2026-11-16", "to": "2026-11-23"},
  "queries": ["실제로 쓴 검색어"],
  "items": [
    {
      "id": "c-01",
      "title": "직접 붙인 짧은 제목",
      "summary": "직접 쓴 요약 2~3문장. 원문 문장 복사 금지",
      "type_guess": "팩트체크",
      "tools": ["ChatGPT"],
      "url": "https://...",
      "source_name": "매체명·사이트명 (커뮤니티는 사이트명까지만)",
      "source_type": "커뮤니티",
      "published": "2026-11-20",
      "original_source_url": "글이 인용한 원출처 URL, 없으면 null",
      "claims": ["확인이 필요한 사실 주장 한 문장씩"],
      "work_use": "어떤 업무 장면에 닿는지 한 줄"
    }
  ],
  "skipped": [{"url": "https://...", "reason": "로그인 필요"}],
  "notes": ""
}
```

## 후보 목록 (`02_curator_candidates.json`)

```json
{
  "run_id": "2026-11-23_1",
  "feedback_applied": "반응 기록을 어떻게 반영했는지 한 줄",
  "candidates": [
    {
      "cid": "C01",
      "title": "후보 제목",
      "type": "소식",
      "tools": ["Claude"],
      "primary": {"url": "원출처 URL", "source_type": "공식", "name": "Anthropic 블로그", "published": "2026-11-20"},
      "secondary": [{"url": "...", "source_type": "언론", "name": "...", "published": "..."}],
      "summary": "통합 요약",
      "claims": ["확인할 주장"],
      "community_origin": false,
      "needs_verification": true,
      "relevance": "상",
      "relevance_reason": "어떤 업무에 영향이 있는지",
      "recommend": true,
      "recommend_reason": "추천·비추천 이유",
      "from_items": ["a-02", "b-05"]
    }
  ],
  "dropped": [{"title": "...", "url": "...", "reason": "posted.md 중복 (2026-11-10 제안)"}],
  "distribution": {"type": {"소식": 3}, "tools": {"ChatGPT": 3, "Claude": 3, "Gemini": 3, "공통": 2}},
  "notes": ""
}
```
- `needs_verification`: 유형이 `소식`·`팩트체크`이거나 `community_origin`이 참이면 반드시 `true`

## 교차 확인 결과 (`03_fact-checker_{n}.json`)

```json
{
  "results": [
    {
      "cid": "C01",
      "status": "확인됨",
      "evidence": [{"url": "...", "source_type": "공식", "published": "2026-11-20", "what": "무엇을 확인했는지"}],
      "freshness_ok": true,
      "caveats": "한국 미출시, 유료 요금제만 등",
      "corrected_claim": "주장이 일부 틀렸으면 바로잡은 내용, 없으면 null",
      "note": ""
    }
  ]
}
```
- `status`: `확인됨` · `부분 확인` · `아직 공식 확인 안 됨` · `사실 아님` · `철회·변경됨`

## 게시용 문안 (`04_writer_drafts.md`)

`curator.py check-drafts`가 이 형식을 읽는다. 형식을 바꾸면 스크립트도 고친다.

````markdown
# 게시용 문안 — 2026-11-23

### [1] 문안 제목
- 후보: C01
- 유형: 소식
- 도구: Claude
- 원문: https://...
- 검증: 확인됨

```kakao
첫 줄에 핵심 🔔
둘째 줄
셋째 줄
https://...
```
````
- `kakao` 블록 안이 사람이 그대로 복사해 붙일 글이다. 마지막 줄은 원문 링크 한 줄
- `도구`가 여럿이면 `ChatGPT, Gemini`처럼 쉼표로 쓴다

## 검증 판정 (`05_reviewer_round{r}.json`)

```json
{
  "round": 1,
  "drafts": [
    {"no": 1, "verdict": "통과", "failed": [], "reasons": "", "fix_hint": ""},
    {"no": 2, "verdict": "반려", "failed": ["저작권", "표현"], "reasons": "둘째 줄이 원문 문장과 같음", "fix_hint": "직접 요약으로 바꿀 것"}
  ],
  "run_level": {
    "fairness": "통과",
    "fairness_note": "ChatGPT 2·Claude 1·Gemini 1·공통 1",
    "candidates_doc": "통과",
    "candidates_note": ""
  },
  "notes": ""
}
```
- `failed`의 항목 이름: `사실 확인` · `최신성` · `저작권` · `개인정보` · `광고 배제` · `공정성` · `안전` · `표현` · `중복` · `형식`
