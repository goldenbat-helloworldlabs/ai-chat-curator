#!/usr/bin/env python3
"""ai-chat-curator 카카오톡 '나에게 보내기' 스크립트 (표준 라이브러리만 사용).

오픈채팅방에는 보내지 않는다. 사용자 본인 카톡으로만 보내고, 방 전달은 사람이 한다.

하위 명령
  send-draft DRAFTS.md --no N [--dry-run]   문안 N번을 본문(200자 단위) + 원문 링크로 나눠 전송
  send-text TEXT [--dry-run]                짧은 알림 한 통(쉼·실패·토큰 경고)
  token-status                              재발급 경과일과 경고 여부(JSON)
  auth-url                                  (로컬) 토큰 재발급용 로그인 주소 출력
  exchange CODE                             (로컬) 인가 코드를 리프레시 토큰으로 교환
  selftest                                  메시지 나누기 자체 테스트

환경 변수 (클라우드 환경 비밀값)
  KAKAO_REST_API_KEY      앱 REST API 키 (필수)
  KAKAO_CLIENT_SECRET     클라이언트 시크릿 (앱에서 켜져 있으면 필수)
  KAKAO_REFRESH_TOKEN     리프레시 토큰 (필수)
  KAKAO_TOKEN_ISSUED      리프레시 토큰을 발급한 날짜 YYYY-MM-DD (경고 계산용)
  KAKAO_LINK_URL          앱 [제품 링크 관리 > 웹 도메인]에 등록한 주소 (메시지 link 필수값)
  KAKAO_REDIRECT_URI      (재발급 때만) 앱에 등록한 Redirect URI

리프레시 토큰은 발급 후 2달 유효하지만, 만료 1달 전부터는 갱신 요청 때 새 토큰이 나오고
기존 토큰은 폐기된다. 클라우드 비밀값은 실행 중 바꿀 수 없으므로 실질 수명을 30일로 보고
23일째부터 경고한다.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
TEXT_LIMIT = 200
EFFECTIVE_LIFE_DAYS = 30
WARN_FROM_DAY = 23
KST = dt.timezone(dt.timedelta(hours=9))


def out(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def env(name, required=True):
    v = os.environ.get(name, "").strip()
    if required and not v:
        out({"ok": False, "error": f"환경 변수 {name} 없음"}, 2)
    return v


# ---------- 문안 읽기·나누기 ----------

def read_draft(path, no):
    text = open(path, encoding="utf-8").read()
    for m in re.finditer(r"^### \[(\d+)\]\s*(.*?)\n(.*?)(?=^### \[|\Z)", text, flags=re.M | re.S):
        if int(m.group(1)) != no:
            continue
        km = re.search(r"```kakao\s*\n(.*?)\n```", m.group(3), flags=re.S)
        if not km:
            out({"ok": False, "error": f"{no}번 문안에 kakao 블록 없음"}, 2)
        return m.group(2).strip(), km.group(1)
    out({"ok": False, "error": f"{no}번 문안 없음"}, 2)


def split_line(line, limit):
    """한 줄이 limit을 넘으면 문장 끝(. ? ! 요 다)에서, 안 되면 공백에서 자른다."""
    parts = []
    while len(line) > limit:
        cut = -1
        for m in re.finditer(r"(?<=[.?!])\s|(?<=[요다])[.]?\s", line[:limit + 1]):
            cut = m.end()
        if cut <= 0:
            cut = line.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        parts.append(line[:cut].rstrip())
        line = line[cut:].lstrip()
    if line:
        parts.append(line)
    return parts


def build_messages(kakao_block, limit=TEXT_LIMIT):
    """본문은 줄 경계에서 limit 이하로 묶고, 마지막 줄(원문 링크)은 따로 한 통."""
    lines = [ln.rstrip() for ln in kakao_block.split("\n") if ln.strip()]
    link = None
    if lines and re.match(r"^https?://\S+$", lines[-1]):
        link = lines.pop()
    pieces = []
    for ln in lines:
        pieces.extend(split_line(ln, limit))
    msgs, cur = [], ""
    for p in pieces:
        cand = p if not cur else cur + "\n" + p
        if len(cand) <= limit:
            cur = cand
        else:
            msgs.append(cur)
            cur = p
    if cur:
        msgs.append(cur)
    if link:
        msgs.append(link)
    return msgs


# ---------- 카카오 API ----------

def post(url, data, token=None):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"연결 실패: {e.reason} (클라우드 환경 네트워크 허용 목록에 kauth.kakao.com·kapi.kakao.com이 있는지 확인)") from None


def access_token():
    data = {"grant_type": "refresh_token", "client_id": env("KAKAO_REST_API_KEY"),
            "refresh_token": env("KAKAO_REFRESH_TOKEN")}
    secret = env("KAKAO_CLIENT_SECRET", required=False)
    if secret:
        data["client_secret"] = secret
    r = post(TOKEN_URL, data)
    # 새 리프레시 토큰이 나왔으면 기존 비밀값은 곧 못 쓴다. 값은 출력하지 않는다.
    return r["access_token"], bool(r.get("refresh_token"))


def send_texts(texts, dry):
    link_url = env("KAKAO_LINK_URL", required=not dry) or "https://example.com"
    if dry:
        return {"ok": True, "dry_run": True, "messages": texts,
                "lengths": [len(t) for t in texts]}
    try:
        token, rotated = access_token()
        for t in texts:
            tpl = {"object_type": "text", "text": t,
                   "link": {"web_url": link_url, "mobile_web_url": link_url}}
            r = post(MEMO_URL, {"template_object": json.dumps(tpl, ensure_ascii=False)}, token)
            if r.get("result_code") != 0:
                raise RuntimeError(f"전송 응답 이상: {r}")
    except (RuntimeError, KeyError) as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "sent": len(texts), "lengths": [len(t) for t in texts],
            "refresh_rotated": rotated}


# ---------- 명령 ----------

def token_status():
    issued = env("KAKAO_TOKEN_ISSUED", required=False)
    if not issued:
        return {"known": False, "warn": True, "message": "KAKAO_TOKEN_ISSUED가 없어 만료일을 알 수 없어요."}
    try:
        d = dt.date.fromisoformat(issued)
    except ValueError:
        return {"known": False, "warn": True, "message": f"KAKAO_TOKEN_ISSUED 형식 오류: {issued}"}
    age = (dt.datetime.now(KST).date() - d).days
    left = EFFECTIVE_LIFE_DAYS - age
    warn = age >= WARN_FROM_DAY
    msg = ""
    if warn:
        msg = (f"[글감 봇] 카카오 토큰 재발급이 필요해요. 발급 {age}일째, "
               + (f"약 {left}일 남았어요." if left > 0 else "이미 기한이 지났어요.")
               + " PC에서 kakao.py auth-url → exchange 후 클라우드 비밀값을 바꿔 주세요.")
    return {"known": True, "issued": issued, "age_days": age, "days_left": left, "warn": warn, "message": msg}


def cmd_send_draft(a):
    title, block = read_draft(a.drafts, a.no)
    res = send_texts(build_messages(block), a.dry_run)
    res["title"] = title
    out(res, 0 if res["ok"] else 1)


def cmd_send_text(a):
    texts = [t for t in build_messages(a.text)]
    res = send_texts(texts, a.dry_run)
    out(res, 0 if res["ok"] else 1)


def cmd_token_status(_a):
    out(token_status())


def cmd_auth_url(_a):
    q = {"client_id": env("KAKAO_REST_API_KEY"), "redirect_uri": env("KAKAO_REDIRECT_URI"),
         "response_type": "code", "scope": "talk_message"}
    print("브라우저에서 아래 주소로 로그인·동의한 뒤, 이동한 주소의 code= 값을 복사해 exchange에 넣으세요.")
    print(AUTH_URL + "?" + urllib.parse.urlencode(q))


def cmd_exchange(a):
    data = {"grant_type": "authorization_code", "client_id": env("KAKAO_REST_API_KEY"),
            "redirect_uri": env("KAKAO_REDIRECT_URI"), "code": a.code}
    secret = env("KAKAO_CLIENT_SECRET", required=False)
    if secret:
        data["client_secret"] = secret
    try:
        r = post(TOKEN_URL, data)
    except RuntimeError as e:
        out({"ok": False, "error": str(e)}, 1)
    today = dt.datetime.now(KST).date().isoformat()
    print("클라우드 환경 비밀값을 아래 두 값으로 바꾸세요. 이 값은 다른 곳에 붙여 넣지 마세요.")
    print(f"KAKAO_REFRESH_TOKEN={r.get('refresh_token')}")
    print(f"KAKAO_TOKEN_ISSUED={today}")


def cmd_selftest(_a):
    fails = []

    def expect(c, m):
        if not c:
            fails.append(m)
    block = "\n".join(["가" * 120 + ".", "나" * 70 + ".", "다" * 50, "https://example.com/a"])
    msgs = build_messages(block)
    expect(msgs[-1] == "https://example.com/a", "마지막 통이 링크여야 함")
    expect(all(len(m) <= TEXT_LIMIT for m in msgs), "모든 통이 200자 이하")
    expect(len(msgs) == 3, f"본문 2통 + 링크 1통 기대, 실제 {len(msgs)}")
    long = "라" * 450
    expect(all(len(m) <= TEXT_LIMIT for m in build_messages(long)), "긴 한 줄도 200자 이하로")
    short = build_messages("짧은 알림")
    expect(short == ["짧은 알림"], "링크 없는 짧은 글은 한 통")
    out({"ok": not fails, "fails": fails}, 0 if not fails else 1)


def main():
    p = argparse.ArgumentParser(description="카카오톡 나에게 보내기")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("send-draft"); s.add_argument("drafts"); s.add_argument("--no", type=int, required=True)
    s.add_argument("--dry-run", action="store_true"); s.set_defaults(f=cmd_send_draft)
    s = sub.add_parser("send-text"); s.add_argument("text"); s.add_argument("--dry-run", action="store_true")
    s.set_defaults(f=cmd_send_text)
    sub.add_parser("token-status").set_defaults(f=cmd_token_status)
    sub.add_parser("auth-url").set_defaults(f=cmd_auth_url)
    s = sub.add_parser("exchange"); s.add_argument("code"); s.set_defaults(f=cmd_exchange)
    sub.add_parser("selftest").set_defaults(f=cmd_selftest)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
