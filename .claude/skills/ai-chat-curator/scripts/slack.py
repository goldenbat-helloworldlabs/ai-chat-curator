#!/usr/bin/env python3
"""ai-chat-curator 슬랙 알림 스크립트 (표준 라이브러리만 사용).

사용자 개인 슬랙 DM으로 보낸다. 오픈채팅방에는 보내지 않는다. 사람이 문안을 복사해 방에 올린다.

하위 명령
  send-draft DRAFTS.md --no N [--date YYYY-MM-DD] [--dry-run]
                               메모 한 통 + 카톡에 붙일 문안 전체 한 통
  send-text TEXT [--dry-run]   짧은 알림 한 통(쉼·실패)
  selftest                     메시지 만들기 자체 테스트

환경 변수 (클라우드 환경 비밀값)
  SLACK_WEBHOOK_URL   Incoming Webhook 주소. 값 자체가 비밀이므로 파일·커밋·로그에 쓰지 않는다
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def read_draft(path, no):
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r"^### \[(\d+)\]\s*(.*?)\n(.*?)(?=^### \[|\Z)", text, flags=re.M | re.S):
        if int(m.group(1)) != no:
            continue
        body = m.group(3)
        meta = dict(re.findall(r"^- ([^:\n]+):\s*(.*)$", body, flags=re.M))
        km = re.search(r"```kakao\s*\n(.*?)\n```", body, flags=re.S)
        if not km:
            out({"ok": False, "error": f"{no}번 문안에 kakao 블록 없음"}, 2)
        return m.group(2).strip(), meta, km.group(1).strip()
    out({"ok": False, "error": f"{no}번 문안 없음"}, 2)


def escape(text):
    """슬랙 제어 문자만 이스케이프한다. 복사하면 원래 글자로 돌아온다."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_draft_messages(title, meta, kakao, date=""):
    head = f"[글감 봇] {date + ' ' if date else ''}오늘의 글감 — {title}\n" \
           f"유형 {meta.get('유형', '?')} · 도구 {meta.get('도구', '?')} · 검증 {meta.get('검증', '?')}\n" \
           "아래 메시지를 길게 눌러 복사해 오픈채팅방에 붙여 넣으세요."
    return [head, kakao]


def send(texts, dry):
    if dry:
        return {"ok": True, "dry_run": True, "messages": texts}
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return {"ok": False, "error": "환경 변수 SLACK_WEBHOOK_URL 없음"}
    for t in texts:
        payload = json.dumps({"text": escape(t), "mrkdwn": False, "unfurl_links": False}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                resp = r.read().decode("utf-8", "replace")
            if resp.strip() != "ok":
                return {"ok": False, "error": f"슬랙 응답 이상: {resp[:200]}"}
        except urllib.error.HTTPError as e:
            # 응답 본문(예: invalid_token, channel_not_found)만 남기고 주소는 남기지 않는다
            return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}"}
        except urllib.error.URLError as e:
            return {"ok": False, "error": f"연결 실패: {e.reason} (클라우드 환경 네트워크 허용 목록에 hooks.slack.com이 있는지 확인)"}
    return {"ok": True, "sent": len(texts)}


def cmd_send_draft(a):
    title, meta, kakao = read_draft(a.drafts, a.no)
    res = send(build_draft_messages(title, meta, kakao, a.date or ""), a.dry_run)
    res["title"] = title
    out(res, 0 if res["ok"] else 1)


def cmd_send_text(a):
    res = send([a.text], a.dry_run)
    out(res, 0 if res["ok"] else 1)


def cmd_selftest(_a):
    fails = []
    msgs = build_draft_messages("제목", {"유형": "소식", "도구": "Claude", "검증": "확인됨"},
                                "첫 줄\n둘째 줄\nhttps://example.com/a", "2026-11-24")
    if len(msgs) != 2:
        fails.append("메모 + 문안 2통이어야 함")
    if msgs[1] != "첫 줄\n둘째 줄\nhttps://example.com/a":
        fails.append("문안은 kakao 블록 그대로여야 함")
    if "확인됨" not in msgs[0] or "2026-11-24" not in msgs[0]:
        fails.append("메모에 날짜·검증 상태")
    if escape("A & <B>") != "A &amp; &lt;B&gt;":
        fails.append("이스케이프")
    out({"ok": not fails, "fails": fails}, 0 if not fails else 1)


def main():
    p = argparse.ArgumentParser(description="슬랙 개인 DM 알림")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send-draft"); s.add_argument("drafts"); s.add_argument("--no", type=int, required=True)
    s.add_argument("--date"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_send_draft)
    s = sub.add_parser("send-text"); s.add_argument("text"); s.add_argument("--dry-run", action="store_true")
    s.set_defaults(f=cmd_send_text)
    sub.add_parser("selftest").set_defaults(f=cmd_selftest)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
