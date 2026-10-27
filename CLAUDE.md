# 팀 지침 (CLAUDE.md)

> **저장 위치:** 저장소 맨 위(루트)의 `CLAUDE.md`

> Claude Code가 **매 세션 시작할 때 읽는** 우리 팀 공통 지침입니다. 저장소를 받은 모든 팀원에게 같이 적용됩니다.
> **짧게** 씁니다 (200줄 이하). 길면 지키지 않습니다. 자세한 내용은 문서로 두고 `@`로 가져옵니다.
> **내 취향**(응답 언어, 들여쓰기)은 여기가 아니라 `~/.claude/CLAUDE.md`에, **내 컴퓨터 경로·키**는 `CLAUDE.local.md`에 씁니다. **API 키·비밀번호는 어디에도 적지 않습니다.**
> 서로 모순되는 규칙을 쓰지 않습니다. `>`로 시작하는 안내 문장은 지워도 됩니다.

## 프로젝트
- 서비스: 전운시(전지적 운동 시점) — 맨몸 운동을 폰 카메라가 세어 AI가 바로 판정하고, 그 기록을 캐릭터 성장과 전투 리플레이로 이어 주는 인증형 RPG
- 사용자: 맨몸 운동을 꾸준히 하려는 10~20대 (보조: 애매한 건을 확인하는 지인·길드장, 운영자)
- 지금 단계: 요구사항 정리 중 (코드 없음)

## 프로젝트 문서 (필요할 때 읽는다)
> `@문서경로` 줄은 코드 블록이나 백틱 밖에 씁니다. 가져온 문서도 컨텍스트를 차지하니 꼭 필요한 것만 둡니다.

- 기술 스택: @docs/STACK.md
- 무엇을, 왜 만드는지: @docs/PRD.md
- 스토리와 인수 조건: @docs/requirements/backlog.md
- MVP 포함·제외: @docs/decisions/mvp-scope.md

아래는 매번 가져오지 않고, 관련 작업을 할 때만 열어 읽는다.
- 첫 데모 사용자 흐름: `docs/requirements/user-flows.md`
- 규칙·상태 전이·LLM 자리: `docs/domain/03-rules-states-llm.md`
- 제안서 (고치지 않음): `docs/proposal/draft.md`
- 고객 미팅 결정 (D1~D15): `docs/interview/client-meeting-1.md`
- 팀 경험·조건 (스택 비교용): `docs/decisions/stack-inputs.md`
- 팀 작업 규칙: `docs/team/working-agreement.md`

## 기술 스택
> `docs/STACK.md`에서 결정한 것을 한 줄씩. 실행·테스트 명령은 오늘 뼈대를 세우고 실제로 돌려 본 것만 적습니다. 안 돌아갔으면 비워 둡니다. 지어서 적으면 팀원 전체가 틀린 명령을 쓰게 됩니다.
- 프론트엔드: React Native + Expo (TypeScript), 개발 빌드 사용, Android 우선. 웹은 만들지 않음
- 백엔드: FastAPI + SQLAlchemy (Python)
- DB: PostgreSQL
- UI 도구: NativeWind (React Native용 Tailwind)
- 카메라·자세 인식: react-native-vision-camera + react-native-fast-tflite (TFLite 자세 모델)
- LLM: 제공사·모델 미정. 백엔드에서만 호출
- 테스트 방식: 백엔드 pytest + PostgreSQL(Docker Compose), 앱 Jest + React Native Testing Library, CI는 GitHub Actions
- 시연·배포 환경: Android APK 직접 설치, 백엔드 Render Free, DB Neon Free
- 실행 명령: (뼈대 이후)
- 테스트 명령: (뼈대 이후)

## 팀 규칙
> 팀이 합의한 것만 씁니다. 예시를 그대로 두지 마세요.

- `main`에 바로 커밋하거나 force push하지 않는다. 브랜치 → PR → 병합.
- 브랜치 이름은 `종류/내용` 형식으로 쓴다. 문서는 `docs/주제`. (예: `docs/stack-decision`)
- 커밋 메시지는 `종류: 내용` 형식으로 한국어로 쓴다. (예: `docs: STACK.md 결정 기록 추가`)
- 한 PR은 한 블록의 산출물만 담는다. 파일 이동·이름 변경은 내용 수정과 다른 PR로 올린다.
- PR 본문에 그 블록의 정리 담당을 적는다. 다른 사람이 정리 담당이 있는 파일을 고칠 때는 담당에게 먼저 말한다.
- 병합 전에 팀원 1명이 GitHub에서 Approve를 누른다. 작성자가 혼자 병합하지 않는다. 제안서 PR은 작성자 제외 4명이 승인한다.
- 결정은 `docs/decisions/`에 기록한다. 고객 미팅에서 나온 결정은 `docs/interview/client-meeting-N.md`에 D번호로 적는다.
- 작업 기록은 `logs/daily/YYYY-MM-DD-GitHub아이디.md`에 남긴다.

## Claude에게 맡기지 않는 것
- **인수 조건을 고치거나 새로 쓰기.** `backlog.md`의 인수 조건은 사람이 쓴다.
- **MVP 범위 바꾸기.** `mvp-scope.md`에 없는 기능을 새로 넣지 않는다.
- **기술 스택 바꾸기.** `docs/STACK.md`와 다르면 바꾸지 말고 먼저 알려 준다.
- **이미 낸 제안서(`docs/proposal/`) 고치기.**
- **기술 스택 고르기.** 후보 2안을 비교해 줄 수는 있지만, 선택과 이유는 팀이 `docs/STACK.md`에 쓴다.
- **팀 결정 기록 고치기.** 고객 미팅의 D번호 결정(`client-meeting-N.md`)과 `docs/decisions/`의 결정 내용은 바꾸지 않는다. 다른 문서와 다르면 알려 준다.
- **실행하지 않은 명령을 '확인된 명령'으로 적기.** 직접 돌려 성공한 것만 적고, 아니면 `확인 필요`로 쓴다.
- **PR 승인과 병합.** Approve와 병합은 팀원이 GitHub에서 한다.
- **다른 팀원의 작업 기록(`logs/`) 고치기.** 요청한 사람 본인의 파일만 고친다.

## 작업 방식
- 코드를 쓰기 전에 읽은 파일과 계획을 먼저 보여 준다. 승인을 받은 뒤 고친다.
- 근거가 없으면 지어내지 않고 `[근거 없음]`이나 `미정`으로 표시한다.
- 고치는 범위는 요청받은 파일과 폴더만. 그 밖은 고치지 않는다.
- 문서에 내용을 옮기거나 쓸 때는 문장 끝에 바탕이 된 파일과 절을 `(출처: 02 2-2)`처럼 붙인다.
- 조사 내용에는 `[사실]`·`[추정]`·`[가정]` 태그를 붙인다 (`docs/domain/README.md` 태그 규칙). Claude가 알려 준 내용은 출처를 직접 확인하기 전까지 `[추정]`이다.
- 문서끼리 내용이 다르면 한쪽에 맞춰 고치지 않고, 다른 곳을 짚어 알려 준다.
- 상태 이름·기능 ID·스토리 번호(`SUBMITTED`, `F-xx`, `US-xx`)는 기존 문서에 있는 것만 쓴다. 새로 만들지 않는다.
