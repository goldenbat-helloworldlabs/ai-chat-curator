# 클라우드 자동 실행 설정 안내

매일 오전 10시(KST) PC가 꺼져 있어도 글감 1건을 골라 본인 카카오톡으로 보내기 위한 준비 절차다. 한 번만 하면 된다. 토큰 재발급은 약 한 달에 한 번 필요하다.

## 1. GitHub 비공개 저장소

1. github.com에서 **Private** 저장소를 새로 만든다(예: `ai-chat-curator`). README 없이 빈 저장소로 만든다
2. 이 폴더에서:
   ```
   git remote add origin https://github.com/{계정}/ai-chat-curator.git
   git push -u origin main
   ```
3. claude.ai/code에서 GitHub 연결(Claude GitHub 앱 설치)이 되어 있어야 클라우드 실행이 저장소를 받을 수 있다

## 2. 카카오 개발자 앱

1. developers.kakao.com → 내 애플리케이션 → 애플리케이션 추가
2. **카카오 로그인** 활성화, Redirect URI 등록(예: `https://localhost:3000/oauth`. 실제 서버가 없어도 된다. 로그인 후 주소창의 `code=` 값만 쓴다)
3. **동의항목**에서 `카카오톡 메시지 전송(talk_message)` 사용 설정
4. **제품 링크 관리 > 웹 도메인**에 메시지 link용 주소 하나 등록(예: 본인 블로그나 회사 홈페이지). 이 주소가 `KAKAO_LINK_URL`이다
5. 앱 키에서 **REST API 키**, 보안에서 **Client Secret**(켜져 있으면) 확인

## 3. 첫 토큰 발급 (PC에서)

PowerShell에서 키를 잠시 환경 변수로 두고 실행한다(파일에 저장하지 않는다).

```
$env:KAKAO_REST_API_KEY="..." ; $env:KAKAO_CLIENT_SECRET="..." ; $env:KAKAO_REDIRECT_URI="https://localhost:3000/oauth"
python -I .claude/skills/ai-chat-curator/scripts/kakao.py auth-url
# 출력된 주소로 로그인·동의 → 이동한 주소의 code= 값 복사
python -I .claude/skills/ai-chat-curator/scripts/kakao.py exchange {code}
```

출력된 `KAKAO_REFRESH_TOKEN`·`KAKAO_TOKEN_ISSUED`를 다음 단계에서 쓴다. 이 값은 채팅이나 파일에 붙여 넣지 않는다.

## 4. 클라우드 환경

claude.ai/code → 환경(Environment) 설정에서:

- **환경 변수(비밀값)**: `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`(있으면), `KAKAO_REFRESH_TOKEN`, `KAKAO_TOKEN_ISSUED`, `KAKAO_LINK_URL`
- **네트워크 접근**: 사용자 지정 허용 목록에 `kauth.kakao.com`, `kapi.kakao.com` 추가
- 예약 실행(routine) 설정에서 **main 브랜치에 push 허용**(제한 없는 브랜치 push). 막혀 있으면 게시 기록이 다음 날로 이어지지 않아 같은 글이 다시 나올 수 있다

## 5. 예약 실행 등록

Claude Code에서 `/schedule`로 등록한다(이 대화에서 대신 등록할 수 있다).

- 저장소: 위 비공개 저장소
- 시간: 매일 10:00 Asia/Seoul (cron `0 1 * * *` UTC)
- 지시문: `ai-chat-curator 자동 실행`

## 6. 매일 할 일

- 10시쯤 카톡 '나와의 채팅'에 온 본문·링크 메시지를 길게 눌러 오픈채팅방으로 전달
- 올렸으면 Claude Code에서 "오늘 거 올렸어"
- "[글감 봇] 카카오 토큰 재발급이 필요해요"가 오면 3단계를 다시 하고 4단계의 두 값을 바꾼다

## 토큰 주기가 2달이 아니라 약 한 달인 이유

카카오 리프레시 토큰은 2달 유효하지만, 만료 1달 전부터는 갱신 요청 때 새 토큰이 나오고 기존 토큰은 폐기된다. 클라우드 비밀값은 실행 중에 바꿀 수 없으므로 30일째 무렵부터 저장된 토큰이 쓸모없어진다. 그래서 발급 23일째부터 경고를 보낸다.
