# .gitignore에 추가할 줄 (**내용만 붙여넣는** 조각)

> **사용 방법**
> 1. 저장소 루트의 `.gitignore`를 엽니다. 없으면 정리 담당이 새로 만듭니다.
> 2. 아래 **공통**은 모든 팀이 넣습니다. **스택별**은 우리 팀 것만 골라 넣습니다.
> 3. 정리 담당 한 명이 PR로 올립니다. 다른 사람은 PR에 댓글을 남깁니다.
> 4. 넣은 뒤 `git status`로 확인합니다. `CLAUDE.local.md`와 `.env`가 **보이면 안 됩니다.**
> 5. **이미 커밋된 파일은 `.gitignore`를 추가해도 계속 추적됩니다.** 아래 '이미 올라간 경우'를 보세요.
> 6. 이 파일 자체는 저장소에 올리지 않습니다.

## 공통 (모든 팀)

```
# 개인 설정 (저장소에 올리지 않음)
CLAUDE.local.md
.claude/settings.local.json

# 비밀 값 — 절대 올리지 않음
.env
.env.*
!.env.example

# 운영체제
.DS_Store
Thumbs.db

# 편집기
.vscode/
.idea/
*.swp
```

`!.env.example`은 **예시 파일은 올린다**는 뜻입니다. 환경변수 **이름만** 적힌 파일이라 공유해도 됩니다. 값은 절대 넣지 마세요.

## 스택별 (우리 팀 것만)

### Node.js / React / Next.js

```
node_modules/
dist/
build/
.next/
out/
coverage/
npm-debug.log*
```

### Python / FastAPI / Django / Flask

```
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
htmlcov/
```

### 데이터베이스 파일 (SQLite 등)

```
*.sqlite3
*.db
```

> 샘플 데이터를 일부러 공유할 거면 그 파일만 예외로 두세요. 예: `!sample.sqlite3`

## 확인

- [ ] `git status`에 `CLAUDE.local.md`가 **안 보인다**
- [ ] `git status`에 `.env`가 **안 보인다**
- [ ] `git status`에 `node_modules/`나 `__pycache__/`가 **안 보인다**
- [ ] PR의 변경 파일 수가 수백 개가 아니다

마지막 줄이 중요합니다. PR에 파일이 수백 개면 설치 파일이 섞여 들어간 것입니다.

## 이미 올라간 경우

`.gitignore`는 **아직 추적하지 않는 파일**에만 적용됩니다. 이미 커밋했으면 추적을 먼저 끊어야 합니다.

```bash
# 추적만 끊고 내 컴퓨터의 파일은 남김
git rm -r --cached node_modules
git rm --cached .env

git commit -m "chore: 추적에서 제외"
```

> **`.env`를 이미 올렸다면 추적을 끊는 것으로 끝나지 않습니다.** 과거 커밋에 값이 그대로 남아 있습니다. 그 키는 **못 쓰게 되었다고 보고 새로 발급**하세요. 선생님께 바로 알리세요.

## 왜 `.env`를 막는가

`docs/decisions/permissions.md`에 이 규칙을 넣었을 겁니다.

```
deny: Read(./.env)
```

Claude가 못 읽게 막은 파일을 **git에는 올리면** 아무 의미가 없습니다. 저장소를 보는 사람은 다 보니까요.

**두 군데를 같이 막아야 합니다.**
