# 클라우드 자동 실행 설정 안내

매일 오전 10시(KST) PC가 꺼져 있어도 글감 1건을 골라 개인 슬랙 DM으로 보내기 위한 준비 절차다. 한 번만 하면 된다.

## 1. GitHub 저장소 (완료)

`git@github.com-corp:goldenbat-helloworldlabs/ai-chat-curator.git` (main). claude.ai/code에서 이 저장소에 접근할 수 있도록 Claude GitHub 앱이 `goldenbat-helloworldlabs`에 설치돼 있어야 한다.

## 2. 슬랙 Incoming Webhook

1. api.slack.com/apps → **Create New App** → From scratch → 이름(예: 글감 봇), 워크스페이스 선택
2. 왼쪽 **Incoming Webhooks** → 켜기 → **Add New Webhook to Workspace**
3. 게시할 곳으로 **본인 DM**(목록에서 자기 이름)을 고르고 허용
   - 목록에 본인 DM이 없거나 워크스페이스 정책상 앱 설치가 막혀 있으면 본인만 있는 비공개 채널을 만들어 그 채널을 고른다
4. 생성된 `https://hooks.slack.com/services/...` 주소를 복사한다. 이 주소를 아는 사람은 누구나 그 DM에 글을 쓸 수 있으니 채팅·파일에 붙여 넣지 않는다

## 3. 클라우드 환경

claude.ai/code → 환경(Environment) 설정에서:

- **환경 변수(비밀값)**: `SLACK_WEBHOOK_URL` = 위 주소
- **네트워크 접근**: 사용자 지정 허용 목록에 `hooks.slack.com` 추가
- 예약 실행(routine) 설정에서 **main 브랜치에 push 허용**(제한 없는 브랜치 push). 막혀 있으면 게시 기록이 다음 날로 이어지지 않아 같은 글이 다시 나올 수 있다

## 4. 예약 실행 등록

Claude Code에서 `/schedule`로 등록한다(이 대화에서 대신 등록할 수 있다).

- 저장소: goldenbat-helloworldlabs/ai-chat-curator
- 시간: 매일 10:00 Asia/Seoul (cron `0 1 * * *` UTC)
- 지시문: `ai-chat-curator 자동 실행`

## 5. 매일 할 일

- 10시쯤 슬랙 DM에 메모 한 통과 문안 한 통이 온다. 문안 메시지를 길게 눌러 복사해 오픈채팅방에 붙여 넣는다
- 올렸으면 Claude Code에서 "오늘 거 올렸어"
- 쉼 알림이 오면 그날은 기준을 넘는 글감이 없던 것이다. 원하면 "오늘 글감 찾아줘"로 수동 실행해 직접 고를 수 있다

## 웹훅을 바꾸거나 끊을 때

슬랙 앱 설정에서 웹훅을 지우면 즉시 끊긴다. 새 웹훅을 만들었으면 클라우드 환경의 `SLACK_WEBHOOK_URL`만 바꾸면 된다.
