#!/usr/bin/env python3
"""ai-chat-curator 보조 스크립트.

하위 명령
  check-drafts DRAFTS.md [--posted POSTED.md] [--ignore-proposed-on YYYY-MM-DD]
                                                 게시용 문안 형식 점검(JSON 출력)
  posted-list [--posted POSTED.md] [--days N]    게시 기록 목록(JSON)
  posted-check URL... [--posted POSTED.md]       링크가 이미 기록돼 있는지(JSON)
  posted-add DRAFTS.md --date YYYY-MM-DD [--status 제안] [--only 1,2] [--posted POSTED.md]
                                                 문안을 게시 기록에 추가(이미 있는 링크는 건너뜀)
  posted-status --link URL --status 게시|보류|제안 [--posted POSTED.md]
  auto-pick RUN                                  자동 실행: 발송 자격이 있는 문안 중 첫 번째(JSON)
  selftest                                       자체 테스트

판단(사실·저작권·공정성)은 하지 않는다. 셀 수 있는 것만 센다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = os.path.dirname(os.path.abspath(__file__))
# scripts → ai-chat-curator → skills → .claude → 하네스 폴더
HARNESS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DEFAULT_POSTED = os.path.join(HARNESS_DIR, "posted.md")

MAX_CHARS = 300
MIN_LINES, MAX_LINES = 3, 5
MAX_EMOJI = 2
TYPES = ["소식", "업무 팁", "질문거리", "팩트체크", "주의할 점"]
TOOLS = ["ChatGPT", "Claude", "Gemini", "공통"]
EXAGGERATIONS = [
    # 주의할 점 유형의 "절대 넣지 마세요" 같은 정당한 경고를 막지 않도록 경고 어휘는 넣지 않는다.
    "이거 하나면", "업무 끝", "무조건", "완벽 정리", "완벽하게", "역대급", "충격", "필수템",
    "모르면 손해", "끝판왕", "게임 체인저", "게임체인저", "미쳤",
]
POSTED_HEADER = "| 날짜 | 제목 | 유형 | 관련 도구 | 링크 | 상태 |"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ---------- 공통 ----------

def norm_url(url):
    """비교용 URL: 스킴·호스트 소문자, www 제거, utm·fragment 제거, 끝 슬래시 제거."""
    url = (url or "").strip().strip("<>")
    if not url:
        return ""
    p = urlsplit(url)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")
         and k.lower() not in ("fbclid", "gclid", "ref")]
    path = p.path.rstrip("/") or ""
    return urlunsplit(("https", host, path, urlencode(q), ""))


EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F900-\U0001F9FF"
    "\U00002B00-\U00002BFF\U00002300-\U000023FF]"
)


def count_emoji(text):
    # 변형 선택자·ZWJ 조합은 하나로 센다(대략치)
    text = re.sub("[️‍]", "", text)
    return len(EMOJI_RE.findall(text))


URL_RE = re.compile(r"https?://\S+")


# ---------- 문안 파싱·점검 ----------

def parse_drafts(text):
    drafts = []
    blocks = re.split(r"^### \[(\d+)\]\s*(.*)$", text, flags=re.M)
    # blocks: [머리, no, title, body, no, title, body, ...]
    for i in range(1, len(blocks), 3):
        no, title, body = int(blocks[i]), blocks[i + 1].strip(), blocks[i + 2]
        meta = {}
        for m in re.finditer(r"^- ([^:\n]+):\s*(.*)$", body, flags=re.M):
            meta[m.group(1).strip()] = m.group(2).strip()
        km = re.search(r"```kakao\s*\n(.*?)\n```", body, flags=re.S)
        kakao = km.group(1) if km else None
        drafts.append({"no": no, "title": title, "meta": meta, "kakao": kakao})
    return drafts


def check_one(d, posted_urls):
    issues = []
    meta, kakao = d["meta"], d["kakao"]
    res = {"no": d["no"], "title": d["title"]}
    for key in ("유형", "도구", "원문", "검증"):
        if not meta.get(key):
            issues.append(f"메타 '{key}' 없음")
    if meta.get("유형") and meta["유형"] not in TYPES:
        issues.append(f"유형 값 '{meta['유형']}'이 정해진 값이 아님")
    for t in [x.strip() for x in meta.get("도구", "").split(",") if x.strip()]:
        if t not in TOOLS:
            issues.append(f"도구 값 '{t}'이 정해진 값이 아님")
    if kakao is None:
        issues.append("kakao 블록 없음")
        res.update(ok=False, issues=issues)
        return res

    lines = [ln.rstrip() for ln in kakao.split("\n") if ln.strip()]
    link_line = lines[-1].strip() if lines else ""
    body = lines[:-1] if lines and URL_RE.fullmatch(link_line) else lines
    chars = sum(len(ln) for ln in body)
    emoji = count_emoji(kakao)
    res.update(chars=chars, body_lines=len(body), emoji=emoji)

    if not (lines and URL_RE.fullmatch(link_line)):
        issues.append("마지막 줄이 링크 한 줄이 아님")
    elif meta.get("원문") and norm_url(link_line) != norm_url(meta["원문"]):
        issues.append("마지막 줄 링크가 메타 '원문'과 다름")
    if chars > MAX_CHARS:
        issues.append(f"본문 {chars}자 (최대 {MAX_CHARS})")
    if not (MIN_LINES <= len(body) <= MAX_LINES):
        issues.append(f"본문 {len(body)}줄 ({MIN_LINES}~{MAX_LINES}줄)")
    if emoji > MAX_EMOJI:
        issues.append(f"이모지 {emoji}개 (최대 {MAX_EMOJI})")
    if any(URL_RE.search(ln) for ln in body):
        issues.append("본문 중간에 링크가 있음(링크는 마지막 줄 하나)")
    hits = [w.strip() for w in EXAGGERATIONS if w in kakao]
    if hits:
        issues.append("과장 표현: " + ", ".join(hits))
    if meta.get("유형") == "질문거리" and body and not body[-1].rstrip().endswith("?"):
        issues.append("질문거리인데 본문 마지막 줄이 질문(?)으로 끝나지 않음")
    if meta.get("검증") == "아직 공식 확인 안 됨" and "공식 확인" not in kakao:
        issues.append("검증 미확인인데 문안에 '아직 공식 확인 안 됨' 취지가 없음")
    if meta.get("원문") and norm_url(meta["원문"]) in posted_urls:
        issues.append("posted.md에 같은 링크가 있음")
    res.update(ok=not issues, issues=issues)
    return res


def cmd_check_drafts(a):
    with open(a.drafts, encoding="utf-8") as f:
        drafts = parse_drafts(f.read())
    rows = read_posted(a.posted)
    if a.ignore_proposed_on:
        # 같은 실행의 문안을 사람 피드백으로 고칠 때: 그 날짜에 '제안'으로 적힌 자기 자신은 중복으로 보지 않는다
        own = {norm_url(d["meta"].get("원문", "")) for d in drafts}
        rows = [r for r in rows if not (r["날짜"] == a.ignore_proposed_on and r["상태"] == "제안"
                                        and norm_url(r["링크"]) in own)]
    posted_urls = {norm_url(r["링크"]) for r in rows}
    results = [check_one(d, posted_urls) for d in drafts]
    links = [norm_url(d["meta"].get("원문", "")) for d in drafts]
    dup_in_run = sorted({u for u in links if u and links.count(u) > 1})
    tools = {}
    for d in drafts:
        for t in [x.strip() for x in d["meta"].get("도구", "").split(",") if x.strip()]:
            tools[t] = tools.get(t, 0) + 1
    out = {
        "count": len(drafts),
        "all_ok": bool(drafts) and all(r["ok"] for r in results) and not dup_in_run,
        "duplicate_links_in_run": dup_in_run,
        "tool_distribution": tools,
        "drafts": results,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out["all_ok"] else 1


# ---------- 게시 기록 ----------

def read_posted(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln.startswith("|") or ln.startswith("| 날짜") or ln.startswith("| ---"):
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) < 6:
                continue
            rows.append(dict(zip(["날짜", "제목", "유형", "관련 도구", "링크", "상태"], cells[:6])))
    return rows


def ensure_posted(path):
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write("# 게시 기록 — 직장인 AI 활용방\n\n" + POSTED_HEADER + "\n| --- | --- | --- | --- | --- | --- |\n")


def cell(s):
    return (s or "").replace("|", "／").replace("\n", " ").strip()


def cmd_posted_list(a):
    rows = read_posted(a.posted)
    if a.days:
        since = dt.date.today() - dt.timedelta(days=a.days)
        rows = [r for r in rows if r["날짜"] >= since.isoformat()]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def cmd_posted_check(a):
    rows = read_posted(a.posted)
    index = {norm_url(r["링크"]): r for r in rows}
    out = {u: index.get(norm_url(u)) for u in a.urls}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_posted_add(a):
    ensure_posted(a.posted)
    with open(a.drafts, encoding="utf-8") as f:
        drafts = parse_drafts(f.read())
    if getattr(a, "only", None):
        keep = {int(x) for x in a.only.split(",") if x.strip()}
        drafts = [d for d in drafts if d["no"] in keep]
    existing = {norm_url(r["링크"]) for r in read_posted(a.posted)}
    added, skipped = [], []
    lines = []
    for d in drafts:
        url = d["meta"].get("원문", "")
        if not url or norm_url(url) in existing:
            skipped.append(d["title"])
            continue
        existing.add(norm_url(url))
        lines.append("| " + " | ".join(cell(x) for x in [
            a.date, d["title"], d["meta"].get("유형", ""), d["meta"].get("도구", ""), url, a.status]) + " |")
        added.append(d["title"])
    if lines:
        with open(a.posted, encoding="utf-8") as f:
            text = f.read()
        with open(a.posted, "a", encoding="utf-8") as f:
            if not text.endswith("\n"):
                f.write("\n")
            f.write("\n".join(lines) + "\n")
    print(json.dumps({"added": added, "skipped_existing": skipped}, ensure_ascii=False, indent=2))
    return 0


def cmd_posted_status(a):
    with open(a.posted, encoding="utf-8") as f:
        src = f.read().split("\n")
    target, changed = norm_url(a.link), 0
    for i, ln in enumerate(src):
        if not ln.startswith("|") or ln.startswith("| 날짜") or ln.startswith("| ---"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 6 and norm_url(cells[4]) == target:
            cells[5] = a.status
            src[i] = "| " + " | ".join(cells) + " |"
            changed += 1
    with open(a.posted, "w", encoding="utf-8") as f:
        f.write("\n".join(src))
    print(json.dumps({"changed": changed}, ensure_ascii=False))
    return 0 if changed else 1


# ---------- 자체 테스트 ----------

SAMPLE = """# 게시용 문안 — 2026-11-23

### [1] 좋은 문안
- 후보: C01
- 유형: 질문거리
- 도구: ChatGPT, Claude, Gemini
- 원문: https://example.com/a?utm_source=x
- 검증: 확인됨

```kakao
회의록 요약, 다들 어떤 도구로 하세요? 📝
요즘 세 도구 모두 긴 녹취 요약을 지원해요.
저는 핵심 결정사항만 뽑아 달라고 하는 편이에요.
여러분 회사는 회의록에 AI 써도 되나요?
https://example.com/a
```

### [2] 나쁜 문안
- 후보: C02
- 유형: 소식
- 도구: Copilot
- 원문: https://example.com/b
- 검증: 아직 공식 확인 안 됨

```kakao
이거 하나면 업무 끝! 🔥🔥🔥
한 줄
```
"""


FACT_TYPES = ("소식", "팩트체크", "주의할 점")


def judge_auto(draft, fc, verdicts, failed=()):
    """자동 발송 자격. fc: 교차 확인 결과(dict|None), verdicts: 회차 순 판정 목록,
    failed: 모든 회차의 반려 항목. 사실 확인으로 한 번이라도 반려된 문안은 고쳐졌어도 보내지 않는다."""
    typ = draft["meta"].get("유형", "")
    if not verdicts:
        return False, "검증 판정 없음"
    if verdicts[-1] != "통과":
        return False, "마지막 검증 미통과"
    if "사실 확인" in failed:
        return False, "검증 중 사실 확인으로 반려된 이력 있음"
    if fc and fc.get("status") in ("사실 아님", "철회·변경됨"):
        return False, f"교차 확인 {fc.get('status')}"
    if typ in FACT_TYPES:
        if not fc or fc.get("status") != "확인됨":
            return False, f"{typ}인데 교차 확인이 '확인됨'이 아님({(fc or {}).get('status', '없음')})"
        if not any(e.get("source_type") == "공식" for e in fc.get("evidence", [])):
            return False, "공식 출처 근거 없음"
        return True, "공식 출처로 확인됨 + 검증 통과"
    if typ == "업무 팁":
        if "반려" in verdicts:
            return False, "업무 팁인데 검증 중 반려 이력 있음"
        return True, "업무 팁, 검증 1회차부터 반려 없이 통과"
    return False, f"자동 발송 대상 유형 아님({typ})"


def cmd_auto_pick(a):
    run = a.run
    drafts = parse_drafts(open(os.path.join(run, "04_writer_drafts.md"), encoding="utf-8").read())
    fcs = {}
    for name in sorted(os.listdir(run)):
        if name.startswith("03_fact-checker_") and name.endswith(".json"):
            for r in json.load(open(os.path.join(run, name), encoding="utf-8")).get("results", []):
                fcs[r.get("cid")] = r
    rounds = []
    for name in os.listdir(run):
        m = re.match(r"05_reviewer_round(\d+)\.json$", name)
        if m:
            rounds.append((int(m.group(1)), json.load(open(os.path.join(run, name), encoding="utf-8"))))
    rounds.sort()
    result, pick = [], None
    for d in drafts:
        mine = [x for _, rj in rounds for x in rj.get("drafts", []) if x.get("no") == d["no"]]
        verdicts = [x.get("verdict") for x in mine]
        failed = [f for x in mine for f in x.get("failed", [])]
        fc = fcs.get(d["meta"].get("후보"))
        ok, why = judge_auto(d, fc, verdicts, failed)
        result.append({"no": d["no"], "title": d["title"], "type": d["meta"].get("유형"),
                       "eligible": ok, "reason": why})
        if ok and pick is None:
            pick = d["no"]
    print(json.dumps({"pick": pick, "drafts": result, "rounds": len(rounds)}, ensure_ascii=False, indent=2))
    return 0


def cmd_selftest(_a):
    ok = True

    def expect(cond, msg):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + msg)
        ok = ok and cond

    expect(norm_url("https://WWW.Ex.com/a/?utm_source=x#h") == norm_url("http://ex.com/a"), "URL 정규화")
    expect(count_emoji("🔔 알림 ✅") == 2, "이모지 세기")
    ds = parse_drafts(SAMPLE)
    expect(len(ds) == 2, "문안 2개 파싱")
    r1, r2 = check_one(ds[0], set()), check_one(ds[1], set())
    expect(r1["ok"], f"좋은 문안 통과 {r1.get('issues')}")
    joined = " ".join(r2["issues"])
    for needle in ["과장", "이모지", "줄", "마지막 줄", "공식 확인", "도구 값"]:
        expect(needle in joined, f"나쁜 문안에서 '{needle}' 검출")
    expect("posted.md" in " ".join(check_one(ds[0], {norm_url("https://example.com/a")})["issues"]), "posted 중복 검출")

    with tempfile.TemporaryDirectory() as td:
        posted, drafts = os.path.join(td, "posted.md"), os.path.join(td, "d.md")
        with open(drafts, "w", encoding="utf-8") as f:
            f.write(SAMPLE)
        ns = argparse.Namespace(posted=posted, drafts=drafts, date="2026-11-23", status="제안")
        sys_stdout, sys.stdout = sys.stdout, open(os.devnull, "w", encoding="utf-8")
        try:
            cmd_posted_add(ns)
            cmd_posted_add(ns)  # 두 번째는 모두 건너뛰어야 함
            cmd_posted_status(argparse.Namespace(posted=posted, link="https://example.com/b/", status="게시"))
        finally:
            sys.stdout.close()
            sys.stdout = sys_stdout
        rows = read_posted(posted)
        expect(len(rows) == 2, f"게시 기록 2행(중복 추가 안 함) — {len(rows)}행")
        expect(rows[1]["상태"] == "게시", "상태 변경")
    print("SELFTEST " + ("OK" if ok else "FAILED"))
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("check-drafts"); s.add_argument("drafts"); s.add_argument("--posted", default=DEFAULT_POSTED)
    s.add_argument("--ignore-proposed-on", metavar="YYYY-MM-DD",
                   help="사람 피드백 수정 라운드용: 그 날짜에 '제안'으로 기록된 이 문안들의 링크는 중복으로 보지 않음")
    s.set_defaults(f=cmd_check_drafts)
    s = sub.add_parser("posted-list"); s.add_argument("--posted", default=DEFAULT_POSTED); s.add_argument("--days", type=int)
    s.set_defaults(f=cmd_posted_list)
    s = sub.add_parser("posted-check"); s.add_argument("urls", nargs="+"); s.add_argument("--posted", default=DEFAULT_POSTED)
    s.set_defaults(f=cmd_posted_check)
    s = sub.add_parser("posted-add"); s.add_argument("drafts"); s.add_argument("--date", required=True)
    s.add_argument("--status", default="제안", choices=["제안", "게시", "보류"]); s.add_argument("--posted", default=DEFAULT_POSTED)
    s.add_argument("--only", help="추가할 문안 번호(쉼표 구분). 없으면 전부")
    s.set_defaults(f=cmd_posted_add)
    s = sub.add_parser("posted-status"); s.add_argument("--link", required=True)
    s.add_argument("--status", required=True, choices=["제안", "게시", "보류"]); s.add_argument("--posted", default=DEFAULT_POSTED)
    s.set_defaults(f=cmd_posted_status)
    s = sub.add_parser("auto-pick"); s.add_argument("run", help="실행 폴더 RUN")
    s.set_defaults(f=cmd_auto_pick)
    s = sub.add_parser("selftest"); s.set_defaults(f=cmd_selftest)

    a = p.parse_args()
    sys.exit(a.f(a))


if __name__ == "__main__":
    main()
