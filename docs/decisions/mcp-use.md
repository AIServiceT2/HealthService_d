# MCP 사용 기록

> **저장 위치:** `docs/decisions/mcp-use.md`

> **사용 방법**
> 1. 우리 팀이 **어떤 일이 필요해서 어떤 MCP를 골랐고**, **공식 문서를 보고 어떻게 설치했고**, **어떤 작업에 썼고**, **내가 직접 무엇을 확인했는지**를 적습니다. "연결했다"는 기록이 아닙니다.
> 2. MCP가 알려 준 것 중 **쓰지 않은 것**(문서 버전이 달랐다, 우리 코드와 맞지 않았다, 화면 결과를 믿지 않았다)을 적습니다. `ai-check-log.md`에도 같은 것을 줄로 남깁니다.
> 3. MCP 결과는 **참고**입니다. 근거는 직접 실행한 결과와 테스트 결과입니다.
> 4. 연결 문제는 **오류 메시지 그대로** 적습니다. 못 고쳐도 괜찮습니다.
> 5. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 작성 시작일: 2026-11-02
- 상태: 1절 "고른다 / 보류 / 고르지 않는다"는 **팀 결정** (2026-11-02, 성민규 전달). 표 작성은 Claude 초안. 공식 문서 내용은 2026-11-02 Claude가 웹 페이지를 열어 요약한 것이라, 팀원이 같은 주소를 직접 열어 확인하기 전까지 `[추정]`이다 (CLAUDE.md 작업 방식).

## 1. 팀 결정 — 우리 팀에 필요한 MCP

**필요한 일 파악** (`STACK.md`, `PRD.md`, `backlog.md`를 보고 외부 도구가 있으면 좋은 일)

| 필요한 일 | 왜 필요한가 (우리 팀 상황에서) |
| --- | --- |
| 새 버전 라이브러리의 최신 공식 문서 찾기 (Expo SDK 58, react-native-vision-camera v5, react-native-fast-tflite 3.x, NativeWind 4.x, FastAPI·SQLAlchemy 2.1) | 다섯 명 모두 React Native가 처음이고(출처: STACK.md 팀원별 새로 배워야 할 것), VisionCamera v5는 프레임 처리 방식이 `useFrameOutput`으로 바뀌었다(출처: STACK.md 외부 사실 확인 기록). Claude가 옛 버전 API로 코드를 쓰면 바로 막힌다. 패키지 호환성 검증도 남아 있다(출처: STACK.md 추가 검증 항목 — 패키지 호환성) |
| GitHub 이슈·PR 확인 | 팀 규칙이 브랜치 → PR → 팀원 Approve → 병합이고, backlog의 "관련 이슈" 칸을 채워야 한다(출처: CLAUDE.md 팀 규칙, backlog.md 각 스토리). 다만 Approve·병합은 Claude에게 맡기지 않는다(출처: CLAUDE.md Claude에게 맡기지 않는 것) |
| 화면 확인 | 첫 기능은 화면·서버·데이터를 모두 거친다(출처: first-feature.md 안내 2). 하지만 우리 앱은 웹이 없는 Android 앱이다(출처: STACK.md 최종 선택) |
| 디자인 시안을 화면 코드로 옮기기 | 화면 목록·디자인 토큰·상태별 UI를 `DESIGN.md`에 정했고, 화면 담당이 이를 React Native 화면으로 옮겨야 한다(출처: DESIGN.md 3·4절). Figma는 이시은이 써 봤다(출처: STACK.md 우리 팀 상황). 팀 Figma 파일이 있는지는 `확인 필요` |
| DB 내용 확인 | 상태 전이·한 번만 지급 테스트에서 실제 PostgreSQL 행을 봐야 한다(출처: STACK.md 확정 전 검증 계획). 다만 DB 연결은 아직 안 했다(출처: scaffold-log.md 1절 — SQLAlchemy + PostgreSQL "뺌") |

**후보 비교와 선택** (Claude가 찾아 준 것도 공식 문서·저장소로 직접 확인한 것만 적음)

| 후보 서버 | 공식 문서·저장소 (주소, 절) | 하는 일 | 내 컴퓨터에서 실행되는 명령 | 읽기만 / 쓰기도 | 키 필요 | 고른다 / 보류 / 고르지 않는다 | 이유 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Context7 | https://github.com/upstash/context7 (Installation, Available Tools › MCP Tools), https://context7.com/docs/resources/all-clients (Claude Code) | 라이브러리 이름 → ID 찾기(`resolve-library-id`), 그 ID의 문서 조회(`query-docs`) | 원격 HTTP 서버라 내 컴퓨터에서 실행되는 명령 없음. 로컬 방식을 쓰면 `npx -y @upstash/context7-mcp` | 읽기만 `[추정]` (README에 "read-only" 표현은 없고 도구가 검색·조회 2개뿐) | 필수 아님. README는 "API Key Recommended"(요청 한도를 늘리려면 무료 키) | **고른다** (팀 결정) | 위 첫 번째 필요한 일에 바로 맞음. 쓰기 도구가 없고 키 없이 `.mcp.json`에 넣을 수 있음 |
| GitHub MCP Server | https://github.com/github/github-mcp-server (Local GitHub MCP Server, Handling PATs Securely, Tool Configuration) | 저장소·이슈·PR·Actions 조회와 생성·수정 | 로컬: `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server` (Docker 필요) | 쓰기도 (`--read-only`로 쓰기 도구를 끌 수 있음) | 필요 (PAT 또는 OAuth 브라우저 로그인) | **고르지 않는다** (팀 결정) | 쓰기 도구에 PR 병합 등이 있어 "Approve·병합은 사람이" 규칙과 부딪힐 수 있음. 키가 필요해 `.mcp.json`(키 없음)에 바로 넣기 어려움. 팀원별 `gh` CLI 사용 여부를 먼저 확인 |
| Playwright MCP | https://github.com/microsoft/playwright-mcp (Requirements, Getting started) | 브라우저 열기·클릭·입력 (접근성 트리 기반) | `npx @playwright/mcp@latest` (Node.js 18 이상) | 쓰기도 (브라우저 조작) | 필요 없음 | **고르지 않는다** (팀 결정) | 웹 브라우저 자동화 도구이고 `--mobile`·`--device`도 모바일 브라우저 흉내일 뿐 네이티브 Android 앱은 다루지 않음. 우리는 웹을 만들지 않음(출처: STACK.md) |
| PostgreSQL MCP (MCP 공식 예제 서버) | https://github.com/modelcontextprotocol/servers ("Archived" 절), https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres (Components, Configuration › NPX·Docker) | 테이블 스키마 보기(리소스), SQL 실행(`query` 도구) | `npx -y @modelcontextprotocol/server-postgres <접속 문자열>` 또는 `docker run -i --rm mcp/postgres <접속 문자열>` | 읽기만 ("All queries are executed within a READ ONLY transaction") | 키는 없지만 **DB 접속 문자열**(`postgresql://사용자:비밀번호@호스트:포트/DB이름`)이 명령 인자로 들어감 | **고르지 않는다** (팀 결정) | ① 2025-05-29 보관(archive)되어 더 이상 유지보수되지 않음. npm 최신 0.6.2(2024-12-04)에 "Package no longer supported" 표시 (2026-11-02 npm 레지스트리 확인). ② 접속 문자열에 비밀번호가 들어가 키 없는 `.mcp.json`에 그대로 넣을 수 없음 (`${VAR}` 환경 변수로 빼는 방법은 있음, 출처: Claude Code MCP 문서 Environment variable expansion). ③ DB 연결 전이라 지금 볼 DB가 없음. 유지되는 다른 PostgreSQL 서버는 아직 찾지 않음 `확인 필요` |
| Expo MCP Server | https://docs.expo.dev/eas/ai/mcp/ (What does Expo MCP Server do?, Prerequisites, Installation and setup › Install Expo MCP Server · Set up local capabilities, Available MCP capabilities › Tools, Limitations) | 서버 기능: Expo 문서 읽기·검색, EAS 빌드·워크플로 조회와 실행, 스토어 리뷰·크래시 조회. 로컬 기능: 개발 서버에 붙어 앱 로그 수집·스크린샷·탭 등 화면 자동화 | 서버 기능은 원격 HTTP라 없음 (`claude mcp add --transport http expo https://mcp.expo.dev/mcp`). 로컬 기능은 `npx expo install expo-mcp --dev` 후 `EXPO_UNSTABLE_MCP_SERVER=1`로 개발 서버 실행 | 쓰기도 (`build_run`·`build_submit`·`workflow_run`·`sandbox_exec`, 스토어 리뷰 답글 `playstore_reply_review` 등) | 키는 없지만 **Expo 계정 OAuth 로그인** 필요. `search_documentation`은 유료 플랜 필요, 샌드박스·시뮬레이터는 과금 환경 | **보류** (팀 결정) | 로컬 기능의 화면 자동화가 "화면 확인"에 맞을 수 있으나 개발 빌드·개발 서버가 있어야 하고 아직 앱 뼈대가 없음(로컬 기능은 SDK 54 이상, 개발 서버 1개만 연결). 빌드 실행·스토어 답글 같은 쓰기 도구가 있고, 문서 찾기는 Context7과 겹침. 전원 Expo 계정이 필요한지 `확인 필요`. 다시 볼 조건: `mobile/` 개발 빌드가 팀원 폰에서 돌아갈 때 |
| Figma MCP Server (원격) | https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ (Enable the remote MCP server › Claude Code), https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/ (Design to code, Code to design), https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/ (Who can use the MCP server, and what are the rate limits?) | Figma 파일의 디자인 정보·변수·스크린샷 읽기(`get_design_context`, `get_variable_defs`, `get_screenshot` 등), 캔버스에 쓰기(`use_figma`, `generate_figma_design`, `create_new_file` 등) | 원격 HTTP라 없음. 서버 주소 `https://mcp.figma.com/mcp` | 쓰기도 (Code to design 도구는 Figma 파일을 바꿈) | 키 없음. 처음 연결할 때 **Figma 계정 OAuth 로그인**(브라우저에서 Allow access) | **고른다** (팀 결정) | 위 "디자인 시안을 화면 코드로 옮기기"에 맞음. 원격 HTTP·키 없음이라 `.mcp.json` 결정과 맞음. 주의: ① 읽기 도구 호출 제한이 좌석마다 다름 — View·Collab 좌석은 요금제와 관계없이 **월 20회**, Professional의 Full·Dev 좌석은 일 200회·분당 10회(교육 요금제도 같음). 우리 팀 요금제·좌석 `확인 필요` ② 쓰기 도구가 있어 팀 Figma 파일을 Claude가 바꿀 수 있음 → 쓰기 도구는 요청할 때만 쓰고 결과를 사람이 확인 |

| 항목 | 우리 결정 |
| --- | --- |
| 쓰는 서버 (팀당 1~2개부터. 없으면 "연결하지 않음"과 이유) | Context7, Figma(원격) 2개 (팀 결정) |
| 설정 위치 | 저장소 `.mcp.json` (키 없음). Context7은 추가됨(PR #98). **Figma는 아직 추가하지 않음** → `.mcp.json` PR로 따로 올리고 4절 체크를 채움 |
| 승인 방법 | 각자 프로젝트 서버를 읽고 하나씩 승인 (일괄 승인 설정 안 씀). 대화형 세션은 `.mcp.json` 서버를 쓰기 전에 승인을 묻고, 선택을 되돌리려면 `claude mcp reset-project-choices` (출처: Claude Code MCP 문서 Project server approvals and workspace trust) |
| 버전 고정 여부 🔧 | 원격 HTTP 서버라 서버 버전을 우리가 고정할 수 없음 `[추정]`. 로컬(`npx`) 방식으로 바꾸면 `@upstash/context7-mcp@버전`으로 고정 가능 — 고정할 버전 `확인 필요` |
| 설치에 쓴 공식 문서 (주소, 절) | https://code.claude.com/docs/en/mcp (MCP installation scopes › Project scope, Managing your servers), https://context7.com/docs/resources/all-clients (Claude Code). Context7 설치 명령 `claude mcp add --scope project --transport http context7 https://mcp.context7.com/mcp` — 실행 성공 (PR #98). Figma: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/ (Claude Code › Add the server manually). 설치 명령 초안 `claude mcp add --scope project --transport http figma https://mcp.figma.com/mcp` — 공식 예시에 `--scope project`를 붙인 것이라 **실행 전, `확인 필요`** |
| 보류한 서버와 이유 | Expo MCP Server: 앱 개발 빌드 전이고 Expo 계정·쓰기 도구가 있음. `mobile/` 개발 빌드가 돌아가면 다시 봄 (위 표) |
| 고르지 않은 서버와 이유 | GitHub MCP Server: 쓰기 도구(PR 병합 등)·PAT 필요. Playwright MCP: 웹 브라우저용이라 Android 앱에 맞지 않음. PostgreSQL MCP: 보관되어 유지보수가 끝났고 접속 문자열에 비밀번호가 들어감 (위 표) |

> **Claude가 찾았지만 쓰지 않은 것:** Context7 README가 권장하는 설치는 `npx ctx7 setup`(OAuth로 API 키를 만들어 설정)이다. 키가 생기고 사용자 범위로 설치되는 방식이라, "저장소 `.mcp.json`, 키 없음" 결정과 맞지 않아 쓰지 않았다. Context7 문서의 Claude Code 예시도 `--scope user`라 `--scope project`로 바꿨다.
> Figma 문서가 권장하는 설치는 `claude plugin install figma@claude-plugins-official`(플러그인)이다. 플러그인은 각자 설치하는 방식이라 저장소 `.mcp.json`으로 팀 설정을 맞추는 결정과 달라 쓰지 않는다. 이미 플러그인을 설치한 사람은 같은 서버가 두 번 잡힐 수 있으니 2절 연결 확인 때 `claude mcp list`에서 어느 쪽으로 잡혔는지 적는다.
> Expo MCP 도구의 읽기·쓰기 구분은 문서에 명시되지 않아 도구 설명으로 나눈 것이다 `[추정]`.

## 2. 연결 확인 (5명 전원, 구현을 시작하기 전에)

> 아래 5명 행은 모두 `.mcp.json`에 서버가 없던 상태(2026-11-02, PR #98 병합 전) 기준이다. 김지은 행은 김지은 PC에서 실제로 돌린 결과이고, 나머지 4명 행은 그 시점 저장소 상태로 적은 것이라 본인 실행 결과가 아니다. `.mcp.json` 병합 후 각자 다시 확인해 고친다.

| 이름 | 따로 설치한 것 (런타임·브라우저 등, 공식 문서 주소) | `claude mcp list` 상태 | `/mcp` 상태 | 남은 문제 (실패하면 운영체제, 명령, 오류 메시지 그대로) |
| --- | --- | --- | --- | --- |
| 김지은 | 없음 (원격 HTTP라 추가 설치 불필요 `[추정]`). Node v22.14.0은 이미 있음 | 프로젝트 서버(context7) 없음 — `.mcp.json` 미작성. 개인 계정 서버 중 `aws-mcp`가 `✘ Failed to connect — -32602: Invalid request parameters` (프로젝트와 무관) | `미실행` | `.mcp.json` 병합 후 다시 확인 |
| 강준석 | `미확인` (본인 확인 필요) | 프로젝트 서버 없음 — `.mcp.json` 미작성 (저장소 상태 기준, 본인 실행 결과 아님) | `미실행` | `.mcp.json` 병합 후 본인 확인 |
| 성민규 | `미확인` (본인 확인 필요). Node 22.16.0 (출처: scaffold-log.md 1절) | 프로젝트 서버 없음 — `.mcp.json` 미작성 (저장소 상태 기준, 본인 실행 결과 아님) | `미실행` | `.mcp.json` 병합 후 본인 확인 |
| 손범수 | `미확인` (본인 확인 필요) | 프로젝트 서버 없음 — `.mcp.json` 미작성 (저장소 상태 기준, 본인 실행 결과 아님) | `미실행` | `.mcp.json` 병합 후 본인 확인 |
| 이시은 | `미확인` (본인 확인 필요) | 프로젝트 서버 없음 — `.mcp.json` 미작성 (저장소 상태 기준, 본인 실행 결과 아님) | `미실행` | `.mcp.json` 병합 후 본인 확인 |

## 3. 사용 기록

> 아직 MCP로 한 작업이 없다. 2026-11-02 공식 문서 확인은 MCP가 아니라 Claude의 웹 조회로 했으므로 여기 적지 않는다.

| 날짜 | 누가 | MCP (서버 이름) | 어떤 작업 | 무엇을 요청했나 | 무엇을 얻었나 | 내가 직접 확인한 것 | 쓰지 않은 것과 이유 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |

## 4. `.mcp.json` PR 리뷰 체크 (병합 전에 팀이 읽기)
> 출처: 3주차 1일차 배포 `MCP-설정-조각.md`. 서버를 `.mcp.json`에 추가하는 PR마다 채웁니다.


| 확인 | 내용 | 결과 |
| --- | --- | --- |
| 출처 | 서버를 만든 곳이 **공식 문서·저장소**에서 확인되는가 (이름만 비슷한 것이 아닌가) | |
| 실행되는 명령 | `command`가 `npx`·`node`처럼 **알고 있는 것**인가? 낯선 실행 파일이 아닌가 | |
| 인수 | 낯선 주소·옵션·`--` 뒤의 명령이 없는가 | |
| 주소 | `url`이 공식 문서에 적힌 주소와 **글자까지 같은가** | |
| 접근 범위 | 읽기만 하는가, 쓰기·삭제가 되는가. 어떤 데이터에 닿는가 | |
| 키·토큰 | 설정에 키·토큰·개인 경로가 **없는가** | |
| 서버 수 | 우리가 적은 필요한 일에 쓰는 서버만 들어 있는가 | |
| 버전 | 고정할지 정했는가 🔧 | |

