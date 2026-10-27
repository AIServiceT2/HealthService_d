# 권한 설정 기록

> **저장 위치:** `docs/decisions/permissions.md`

> **사용 방법**
> 1. `.claude/settings.json`에는 **주석을 쓸 수 없어서** 규칙의 이유와 시험 결과는 이 파일에 적습니다. `settings.json`과 **같은 내용**이어야 합니다.
> 2. 규칙을 `settings.json`에 넣을 때마다 아래 표에 한 줄을 추가합니다. **이유 없는 규칙은 넣지 않습니다.**
> 3. 쓴 규칙은 새 Claude Code 대화에서 **직접 시험**하고 '실제'를 눈으로 본 대로 적습니다. `/permissions`로 규칙과 출처를 확인합니다.
> 4. 판정 순서는 **deny → ask → allow**입니다. deny가 이깁니다.
> 5. 규칙 이름은 `Edit(경로)`로 씁니다 (`Write(경로)`가 아닙니다). 경로는 `./`로 시작합니다. `*`는 `/`를 넘지 않고 `**`는 하위 폴더까지 포함합니다.
> 6. **명령을 막는 규칙은 모든 실행 경로를 막는 격리가 아닙니다.** (예: `curl`만 막는다고 모든 네트워크 접근이 막히지 않습니다.)
> 7. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 작성일: 2026-10-27
- 위치: `.claude/settings.json` (팀 공유, 커밋됨). 내 컴퓨터에서만 쓸 허용은 `.claude/settings.local.json`

## 규칙과 이유

| 구분 (allow / ask / deny) | 규칙 | 왜 필요한가 | 어느 원칙에서 왔나 |
| --- | --- | --- | --- |
| allow | `Bash(git status)` | 읽기만 하는 명령이다 | 자주 쓰는 확인 명령은 묻지 않는다 |
| allow | `Bash(git diff *)` | 읽기만 하는 명령이다 | 자주 쓰는 확인 명령은 묻지 않는다 |
| allow | `Bash(git log *)` | 읽기만 하는 명령이다 | 자주 쓰는 확인 명령은 묻지 않는다 |
| ask | `Edit(./docs/requirements/backlog.md)` | 인수 조건은 사람이 쓴다 | CLAUDE.md 'Claude에게 맡기지 않는 것' |
| ask | `Edit(./docs/decisions/mvp-scope.md)` | MVP 범위는 팀이 정한다. 정리 담당이 고칠 때는 확인하고 고친다 | CLAUDE.md 'Claude에게 맡기지 않는 것' |
| ask | `Edit(./docs/STACK.md)` | 기술 스택은 팀이 결정한다. Claude는 후보 비교만 한다 | CLAUDE.md 'Claude에게 맡기지 않는 것', STACK.md 안내 |
| ask | `Edit(./.claude/settings.json)` | Claude가 자기 권한 규칙을 스스로 풀지 못하게 한다 | 권한은 B조가 정하고 이 문서와 같이 고친다 |
| ask | `Bash(git push *)` | 올리기 전에 사람이 본다 | working-agreement: 모든 변경은 PR로 |
| deny | `Read(./.env)`, `Read(./.env.*)` | 비밀 값을 읽지 못하게 한다 | CLAUDE.md 'API 키·비밀번호는 어디에도 적지 않는다'. `.gitignore`에서도 같이 막음 |
| deny | `Edit(./docs/proposal/**)` | 이미 낸 제안서는 수업 중에 고치지 않는다 | 제안서(v2) 처리는 교사가 정한다 |
| deny | `Edit(./docs/domain/README.md)` | 조사 규칙 문서라 고치지 않는다 | `docs/domain/README.md` '이 파일은 고치지 않습니다' |
| deny | `Edit(./docs/decisions/stack-inputs.md)` | 팀원 경험은 각자 직접 쓴다. Claude가 채우면 그럴듯한 기술로 빈칸이 채워진다 | `stack-inputs.md` 'Claude를 쓰지 않습니다' |
| deny | `Bash(git push --force *)`, `Bash(git push -f *)` | 남의 커밋을 지울 수 있다. ask(`git push *`)보다 deny가 먼저라 묻지 않고 막힌다 | working-agreement 'force push 금지' |
| deny | `Bash(git push origin main)` | main에 바로 올리지 않는다 | working-agreement 'main 직접 커밋 금지' |

## 시험 결과

> 새 대화에서 요청하고, 나온 그대로 적습니다. 기대와 다르면 규칙 이름과 경로를 다시 봅니다.

- 시험일: 2026-10-27
- 방법: 시험마다 새 Claude Code 세션을 열었다 (`claude -p "<시킬 말>" --setting-sources project --permission-mode default`). 개인 설정은 빼고 이 저장소의 `.claude/settings.json`만 적용했다. 우회(`sed` 등)는 하지 말라고 지시했다.
- 읽는 법: deny는 `denied`(거부됨)로 바로 막힌다. ask는 `-p` 모드에서 물어볼 화면이 없어 `haven't granted it yet`(아직 허락 안 됨)으로 멈춘다. 대화형 화면에서는 이 자리에 확인 창이 뜬다.
- push 시험은 실수로 실행돼도 아무것도 올라가지 않게 없는 브랜치 이름(`ptest-no-such-branch`)을 썼다. 시험 뒤 `git status`와 원격 브랜치를 확인했고 바뀐 것은 없었다.

| 시험 (Claude에게 시킨 말) | 기대 | 실제 | 맞나 | 고친 것 |
| --- | --- | --- | --- | --- |
| `docs/proposal/` 아래 파일을 고쳐 달라고 한다 | 차단됨 | `File is in a directory that is denied by your permission settings.` (뜻: 권한 설정에서 막아 둔 폴더의 파일이라 고칠 수 없음) 파일 안 바뀜 | 맞음 | 없음 |
| `backlog.md`를 고쳐 달라고 한다 | 실행 전에 확인을 물음 | `Claude requested permissions to write to ...backlog.md, but you haven't granted it yet.` (뜻: 이 파일을 고치려고 허락을 요청했지만 아직 허락받지 못함) 파일 안 바뀜 | 맞음 | 없음 |
| `git status`를 실행해 달라고 한다 | 묻지 않고 실행됨 | 묻지 않고 실행됨. 첫 줄 `On branch docs/permissions-gitignore` (뜻: 지금 docs/permissions-gitignore 브랜치에 있음) | 맞음 | 없음 |
| `docs/domain/README.md`를 고쳐 달라고 한다 | 차단됨 | `File is in a directory that is denied by your permission settings.` (뜻: 권한 설정에서 막아 둔 폴더의 파일이라 고칠 수 없음) 파일 안 바뀜 | 맞음 | 없음 |
| `docs/decisions/stack-inputs.md`의 빈칸을 채워 달라고 한다 | 차단됨 | `File is in a directory that is denied by your permission settings.` (뜻: 권한 설정에서 막아 둔 폴더의 파일이라 고칠 수 없음) 파일 안 바뀜 | 맞음 | 없음 |
| `docs/STACK.md`에 최종 선택을 적어 달라고 한다 | 실행 전에 확인을 물음 | `Claude requested permissions to write to ...STACK.md, but you haven't granted it yet.` (뜻: 이 파일을 고치려고 허락을 요청했지만 아직 허락받지 못함) 파일 안 바뀜 | 맞음 | 없음 |
| `.claude/settings.json`에서 deny 한 줄을 지워 달라고 한다 | 실행 전에 확인을 물음 | `Claude requested permissions to write to ...settings.json, but you haven't granted it yet.` (뜻: 이 파일을 고치려고 허락을 요청했지만 아직 허락받지 못함) 파일 안 바뀜 | 맞음 | 없음 |
| `git push --force origin <브랜치>`를 실행해 달라고 한다 | 차단됨 (묻지도 않음) | `Permission to use Bash with command git push --force origin ptest-no-such-branch has been denied.` (뜻: 이 명령은 권한 설정에서 막혀 실행할 수 없음) | 맞음 | 없음 |
| `git push origin main`을 실행해 달라고 한다 | 차단됨 | `Permission to use Bash with command git push origin main has been denied.` (뜻: 이 명령은 권한 설정에서 막혀 실행할 수 없음) | 맞음 | 없음 |
| `git push origin <브랜치>`를 실행해 달라고 한다 | 실행 전에 확인을 물음 | `Claude requested permissions to use Bash, but you haven't granted it yet.` (뜻: 명령을 실행하려고 허락을 요청했지만 아직 허락받지 못함) | 맞음 | 없음 |

## 막지 않은 것과 이유
> 막을 수 있었지만 **일부러 막지 않은 것**도 적습니다. 나중에 왜 열려 있는지 알 수 있습니다.
- `git commit`, `git switch`, `git add`: 브랜치에서 작업할 때 매번 쓴다. 올리기(`git push`)에서 사람이 한 번 보므로 커밋은 열어 둔다.
- `logs/`, `docs/domain/`(README 제외), `docs/interview/` 수정: 정리 담당이 Claude와 함께 표를 채우는 곳이다. 막으면 매 블록 작업이 멈춘다.
- `CLAUDE.md`, `docs/PRD.md` 수정: 오늘 Claude와 같이 쓰는 문서다. 내용 확인은 PR 리뷰에서 한다.
- `curl` 같은 네트워크 명령: 오늘 쓸 일이 없고, 명령 하나를 막아도 다른 경로가 남아 막는 의미가 적다.

## 알고 있는 한계
- `Bash(git push origin main)`은 그 문장 그대로만 막는다. main 브랜치에서 `git push`만 치면 이 규칙에 안 걸리고 ask로 넘어간다. 진짜 방어는 GitHub의 main 브랜치 보호 규칙이다 (working-agreement: 테크 리드가 켬).
- `Edit(...)` 규칙은 Claude의 파일 편집 도구만 막는다. Bash로 `sed`나 `echo >>`를 쓰면 이 규칙에 걸리지 않는다. 이번 시험에서는 우회하지 말라고 지시했으므로, 이 경로는 시험하지 않았다.
- `Read(./.env.*)` 때문에 공유용 `.env.example`도 Claude가 읽지 못한다. deny가 이기므로 allow로 예외를 둘 수 없다. 필요하면 사람이 열어 내용을 붙여 준다.

## 확인할 것
- [x] `settings.json`이 유효한 JSON이다 (쉼표, 따옴표)
- [x] `CLAUDE.md`의 "Claude에게 맡기지 않는 것" 중 **파일로 막을 수 있는 것**이 여기에도 있다
- [x] 키·비밀번호가 `settings.json`과 이 문서 어디에도 없다
