# API 약속 (화면과 서버가 주고받는 것)

> **저장 위치:** `docs/API.md`

> **사용 방법**
> 1. 화면(개발자2)과 서버(개발자1)가 **구현하기 전에 같이 읽고 약속**하는 문서입니다.
> 2. 기준은 노션 `전운시 API 명세서`입니다. 요청·응답 본문과 Error Code 전체는 저장소의 내보내기 파일 [`docs/notion-export/jeonunsi_api_spec.json`](notion-export/jeonunsi_api_spec.json)에 있습니다. 이 문서에는 공통 규칙, 목록, 노션과 실제 구현이 다른 곳만 씁니다.
> 3. 필드 이름·상태값은 `DATA-MODEL.md`와 **똑같이** 씁니다. 인수 조건에 없는 응답을 새로 만들지 않습니다.
> 4. 이 문서는 **공유 파일**입니다. PM만 고치고, 바꿀 일이 있으면 PR 댓글로 요청합니다.
> 5. 모르는 것은 `미정`으로 씁니다. 임의로 정하지 않습니다.

- 최종 수정일: 2026-11-10
- 근거: 노션 `전운시 API 명세서` (내보낸 시각 2026-11-10T05:12:16Z, `docs/notion-export/`), `backlog.md`, `DATA-MODEL.md`, 실제 코드(`backend/app/modules/*/router.py`, 2026-11-10 `main`)
- 노션 명세는 참고 자료다. 실제 구현과 다른 곳은 아래 [노션 명세와 구현이 다른 곳](#노션-명세와-구현이-다른-곳)에 적고 한쪽에 맞추지 않는다 (CLAUDE.md 팀 규칙)

## 공통 규칙

| 항목 | 내용 |
| --- | --- |
| 응답 형식 | JSON. 데이터를 감싸지 않고 바로 준다. 필드 이름은 camelCase (서버 코드 안은 snake_case) (출처: 노션 API 명세서 각 API 응답 예시) |
| 시간 | ISO-8601(UTC). 일일 상한 날짜만 KST (출처: 노션 API 명세서 공통 규칙) |
| 인증 | 공개 API(권한 NONE) 외에는 `Authorization: Bearer <access_token>`. access 토큰은 JWT 30분, refresh 토큰은 14일이고 재발급할 때마다 새로 바꾼다(rotation) (출처: 노션 API-002·003 가안. PRD 미정 표의 '로그인 방식'은 이 가안으로 구현됨) |
| 서버 내부 호출 | `/internal/...`은 서버끼리만 부른다. `X-Internal-Token` 헤더가 서버 환경 변수 `INTERNAL_API_TOKEN`과 같아야 하고, 없으면 401 (출처: 노션 공통 규칙, `snapshot/internal.py`) |
| 목록 | `?cursor=&limit=` (기본 20, 최대 50). 응답의 `nextCursor`를 그대로 다음 요청에 넣는다. 더 없으면 `null` (출처: 노션 공통 규칙) |
| 동시 수정 검사 | 제출건 상태를 바꾸는 요청(취소·확인 요청·승인·반려)은 `If-Match`에 제출건 `version`을 넣는다. 조회 응답의 `ETag`가 그 값이다. 다르면 412 `CONCURRENT_UPDATE` (출처: 노션 공통 규칙, API-028·030·035·037~039) |
| 같은 요청 다시 보내기 | 제출(API-026)·스냅샷(API-031)·지급(API-041)은 `Idempotency-Key`를 받는다. 같은 키로 다시 보내면 첫 결과를 돌려준다 (출처: 노션 API-026·031·041, backlog US-04) |
| 오류 응답 형식 | `{ "code": "...", "message": "...", "details": {...} 또는 null }`. 입력 형식 오류도 422가 아니라 400 `VALIDATION_FAILED` (출처: 노션 공통 규칙, `app/core/errors.py`) |

### 권한 이름

| 권한 | 뜻 |
| --- | --- |
| `NONE` | 로그인 없이 부를 수 있음 |
| `PLAYER` | 로그인한 사용자 |
| `OWNER` | 그 자원(세션·제출건)을 만든 본인. 남의 것이면 403 |
| `GUILD_MEMBER` / `GUILD_LEADER` | 그 길드 소속원 / 길드장 |
| `REVIEWER` | 그 확인 요청을 받은 확인자 (backlog US-07·08) |
| `OPERATOR` | 운영자. 저장 방식 미정 (노션 DB '아직 정하지 못한 것'), MVP 밖 API만 씀 |
| `SYSTEM` | 서버 내부 호출 (`/internal`) |

### 오류 코드

| 코드 | 상태 | 언제 |
| --- | --- | --- |
| `VALIDATION_FAILED` | 400 | 입력 형식 오류, 규칙 위반(14세 미만, 본인을 확인자로 지정 등). `details.reason`에 이유 |
| `UNAUTHENTICATED` | 401 | 토큰이 없거나 틀림, 내부 토큰이 틀림 |
| `FORBIDDEN` | 403 | 본인·요청받은 확인자·길드원이 아님 |
| `NOT_FOUND` | 404 | 대상이 없음 |
| `INVALID_STATE` | 409 | 지금 상태에서 할 수 없는 요청 (예: `APPROVED` 건 취소) |
| `DUPLICATE_SUBMISSION` | 409 | 같은 시간대에 활성 제출건이 있음 (03 R3) |
| `ALREADY_REWARDED` | 409 | 다른 지급 요청으로 이미 지급됨 |
| `CONCURRENT_UPDATE` | 412 | `If-Match` version이 다름 (다른 요청이 먼저 처리됨) |
| `SERVER_RECOUNT_MISMATCH` | 422 | 앱의 렙 수가 서버 재계산 값보다 큼 (backlog US-01) |
| `LIVENESS_FAILED` | 422 | 무작위 동작을 확인하지 못함 |
| `DAILY_CAP_EXCEEDED` | 422 | 노션에만 있음. 세션을 막을지 미정이라 구현하지 않음 |
| `RATE_LIMITED` | 429 | LLM 호출 한도 초과 (기본 문구는 저장됨) |
| `NOT_IMPLEMENTED` | 501 | 경로만 있고 기능이 없음 |

(출처: 노션 API 명세서 각 API의 Error Code, `app/core/errors.py`)

## API 목록

- 범위: 노션 명세 70개 중 `MVP 필수` 51개, `범위 확인`·`후순위·제외` 19개
- 구현 상태는 2026-11-10 `main`의 코드에서 확인했다. `구현`은 501이 아닌 기능 코드가 있다는 뜻이다. 앱 화면에서 확인했다는 뜻은 아니다
- 서버 코드의 경로 변수 이름은 snake_case(`{guild_id}`)다. URL 모양은 같다 (CODE-STYLE 1번)

### MVP 필수 — 51개 (구현 50, 빈 라우터 1)

#### 계정·로그인

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-001 | 회원 가입 | `POST /auth/signup` | NONE | 구현 |
| API-002 | 로그인 | `POST /auth/login` | NONE | 구현 |
| API-003 | 토큰 재발급 | `POST /auth/refresh` | NONE | 구현 |
| API-004 | 로그아웃 | `POST /auth/logout` | PLAYER | 구현 |
| API-005 | 내 계정 조회 | `GET /me` | PLAYER | 구현 |

#### 캐릭터

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-006 | 캐릭터 생성 | `POST /characters` | PLAYER | 구현 |
| API-007 | 내 캐릭터·성장 조회 | `GET /characters/me` | PLAYER | 구현 |
| API-008 | 캐릭터 수정 | `PATCH /characters/me` | PLAYER | 구현 |

#### 길드·지인

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-009 | 길드 생성 | `POST /guilds` | PLAYER | 구현 |
| API-010 | 길드 정보 조회 | `GET /guilds/{guildId}` | GUILD_MEMBER | 구현 |
| API-011 | 길드원 목록 | `GET /guilds/{guildId}/members` | GUILD_MEMBER | 구현 |
| API-012 | 길드 초대 코드 발급 | `POST /guilds/{guildId}/invitations` | GUILD_LEADER | 구현 |
| API-013 | 초대 코드로 길드 가입 | `POST /guilds/join` | PLAYER | 구현 |
| API-014 | 길드 탈퇴 | `DELETE /guilds/{guildId}/members/me` | GUILD_MEMBER | 구현 |
| API-015 | 길드원 내보내기 | `DELETE /guilds/{guildId}/members/{userId}` | GUILD_LEADER | 구현 |
| API-016 | 길드장 위임 | `POST /guilds/{guildId}/leader` | GUILD_LEADER | 구현 |
| API-017 | 확인 요청 가능한 지인 목록 | `GET /me/acquaintances` | PLAYER | 빈 라우터 (501) |

#### 운동 세션

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-018 | 운동 목록·판정 기준·튜토리얼 | `GET /exercises` | PLAYER | 구현 |
| API-019 | 내 일일 상한 조회 | `GET /me/daily-caps` | PLAYER | 구현 |
| API-020 | 운동 세션 시작 | `POST /workout-sessions` | PLAYER | 구현 |
| API-021 | 무작위 동작 확인 결과 전송 | `POST /workout-sessions/{id}/liveness` | OWNER | 구현 |
| API-022 | 관절 좌표 청크 업로드 | `PUT /workout-sessions/{id}/pose-chunks/{seq}` | OWNER | 구현 |
| API-023 | 세션 일시중지 | `POST /workout-sessions/{id}/pause` | OWNER | 구현 |
| API-024 | 세션 재개 | `POST /workout-sessions/{id}/resume` | OWNER | 구현 |
| API-025 | 세션 상태 조회 | `GET /workout-sessions/{id}` | OWNER | 구현 |
| API-026 | 세션 종료·운동 제출 | `POST /workout-sessions/{id}/submit` | OWNER | 구현 |
| API-027 | 세션 폐기 | `DELETE /workout-sessions/{id}` | OWNER | 구현 |

#### 제출·스냅샷

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-028 | 제출 상태 조회 | `GET /submissions/{id}` | OWNER | 구현 |
| API-029 | 내 제출 목록 | `GET /me/submissions` | PLAYER | 구현 |
| API-030 | 승인 전 제출 취소 | `POST /submissions/{id}/cancel` | OWNER | 구현 |
| API-031 | 보상 스냅샷 계산·고정 | `POST /internal/submissions/{id}/snapshot` | SYSTEM | 구현 |
| API-032 | 보상·타격 수 미리보기 | `GET /submissions/{id}/reward-preview` | OWNER | 구현 |

#### 자동 승인·사람 확인

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-033 | 자동 승인 판정 | `POST /internal/submissions/{id}/auto-approval` | SYSTEM | 구현 |
| API-034 | 확인 요청 공유 내용 미리보기 | `GET /submissions/{id}/review-share-preview` | OWNER | 구현 |
| API-035 | 지인·길드장에게 확인 요청 | `POST /submissions/{id}/review-requests` | OWNER | 구현 |
| API-036 | 받은 확인 요청 목록 | `GET /me/review-requests` | REVIEWER | 구현 |
| API-037 | 확인 자료 열람 | `GET /review-requests/{id}` | REVIEWER | 구현 |
| API-038 | 확인자 승인 | `POST /review-requests/{id}/approve` | REVIEWER | 구현 |
| API-039 | 확인자 반려 | `POST /review-requests/{id}/reject` | REVIEWER | 구현 |
| API-040 | 반려 사유 코드 목록 | `GET /reject-reasons` | NONE | 구현 |

#### 지급·인벤토리

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-041 | 보상·피해 1회 반영 | `POST /internal/submissions/{id}/grant` | SYSTEM | 구현 |
| API-042 | 24시간 잠금 해제·능력치 확정 (배치) | `POST /internal/reward-locks/release` | SYSTEM | 구현 |
| API-043 | 내 지급 내역 | `GET /me/rewards` | PLAYER | 구현 |
| API-044 | 인벤토리 조회 | `GET /me/inventory` | PLAYER | 구현 |

#### 전투·결과

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-045 | 던전 상태 조회 | `GET /dungeons/{dungeonId}` | PLAYER | 구현 |
| API-046 | 길드 보스 상태 조회 | `GET /guilds/{guildId}/boss` | GUILD_MEMBER | 구현 |
| API-047 | 결과 카드·서사·교정 코멘트 조회 | `GET /submissions/{id}/result` | OWNER | 구현 |
| API-048 | 전투 리플레이 조회 | `GET /submissions/{id}/replay` | OWNER | 구현 |

#### LLM (서버 내부)

| ID | 이름 | 방식·경로 | 권한 | 구현 |
| --- | --- | --- | --- | --- |
| API-049 | L3 전투 서사 생성 | `POST /internal/llm/narratives` | SYSTEM | 구현 |
| API-050 | L4 자세 교정 코멘트 생성 | `POST /internal/llm/form-comments` | SYSTEM | 구현 |
| API-051 | L1 기록 요약·L2 이상치 설명 생성 | `POST /internal/llm/review-summaries` | SYSTEM | 구현 |

### MVP 밖 (범위 확인 · 후순위·제외) — 19개, 경로 없음

| ID | 이름 | 방식·경로 | 권한 | 범위 |
| --- | --- | --- | --- | --- |
| API-052 | 유지율 집계 | `GET /admin/metrics/retention` | OPERATOR | 범위 확인 |
| API-053 | 제출·레이드 참여 집계 | `GET /admin/metrics/submissions` | OPERATOR | 범위 확인 |
| API-054 | 내 주간 운동 이력 | `GET /me/stats/weekly` | PLAYER | 범위 확인 |
| API-055 | AI 판정 문의 등록 | `POST /submissions/{id}/inquiries` | OWNER | 범위 확인 |
| API-056 | 문의 목록 | `GET /admin/inquiries` | OPERATOR | 범위 확인 |
| API-057 | 문의 답변 | `POST /admin/inquiries/{id}/answer` | OPERATOR | 범위 확인 |
| API-058 | 카탈로그 버전 목록 | `GET /admin/catalogs` | OPERATOR | 범위 확인 |
| API-059 | 카탈로그 새 버전 작성 | `POST /admin/catalogs` | OPERATOR | 범위 확인 |
| API-060 | 카탈로그 버전 활성화 | `POST /admin/catalogs/{version}/activate` | OPERATOR | 범위 확인 |
| API-061 | 신고 접수 | `POST /submissions/{id}/reports` | PLAYER | 후순위·제외 |
| API-062 | 운영자 신고 판정·보상 회수 | `POST /admin/reports/{id}/decide` | OPERATOR | 후순위·제외 |
| API-063 | 건강 앱 러닝 세션 제출 | `POST /integrations/health/{provider}/runs/{runId}/submit` | PLAYER | 후순위·제외 |
| API-064 | 연동 세션 재제출 | `POST /submissions/{id}/resubmit` | OWNER | 후순위·제외 |
| API-065 | 걸음 수 동기화 | `POST /integrations/health/{provider}/steps/sync` | PLAYER | 후순위·제외 |
| API-066 | 체력·자연 회복 조회 | `GET /characters/me/stamina` | PLAYER | 후순위·제외 |
| API-067 | 오각형 성장 리포트 | `GET /me/reports/growth` | PLAYER | 후순위·제외 |
| API-068 | 주간 플랜 | `GET /me/weekly-plans` | PLAYER | 후순위·제외 |
| API-069 | 주간 레이드 결과 조회 | `GET /guilds/{guildId}/raids/{week}` | GUILD_MEMBER | 범위 확인 |
| API-070 | 주간 랭킹 조회 | `GET /raids/{week}/rankings` | PLAYER | 범위 확인 |

## 항목 1: 보상·타격 수 미리보기 (기능 ID: F-03 / 스토리: US-02)

> 첫 기능(`first-feature.md`)의 약속. 2026-11-02에는 경로·키가 `미정`이었고, 노션 명세 API-031·032로 정해졌다.

| 항목 | 내용 |
| --- | --- |
| 요청 | ① 보상 계산: `POST /internal/submissions/{id}/snapshot` (SYSTEM, `Idempotency-Key`) ② 미리보기: `GET /submissions/{id}/reward-preview` (OWNER) |
| 출력 (성공) | ① `{ submissionId, catalogVersion, hitCount, exp, totalDamage, weaknessMultiplier, dropCount }` ② `{ status, snapshot: {...①과 같은 수치}, narrative: { level: "L3", text, isFallback } }`. 인정 렙 30회 스쿼트 → `hitCount` 30 |
| 실패 응답 | ① 계산 실패 시 500, 제출건은 `SUBMITTED`에 남고 다시 호출해 성공했을 때만 `PREPARED` (first-feature.md 2절 #3). `SUBMITTED`가 아니면 409 ② 아직 계산 전이면 202 `{ status, retryAfterSec }`, 남의 건 403 |
| 바뀌는 상태 | `SUBMITTED` → `PREPARED` (①에서만. ② 조회는 상태를 바꾸지 않음) |
| 화면이 쓰는 곳 | `DESIGN.md` '제출 상세·보상 미리보기' |

(출처: 노션 API-031·032, `snapshot/router.py`)

## 노션 명세와 구현이 다른 곳

> 한쪽에 맞추지 않고 적어 둔다. 노션을 고칠지 코드를 고칠지는 팀이 정한다.

| 곳 | 노션 명세 | 실제 구현 | 이유·출처 |
| --- | --- | --- | --- |
| `catalogVersion` 값 (API-018·020·031) | `"2026.11-1"` (예시) | `"cat_2026-11-01"` | 서버 재계산이 ai/ 엔진 카탈로그 파일 이름으로 기준값을 찾음 (`workout_session/catalog.py`) |
| 운동 종류·반려 사유 | `EXERCISE_TYPE`·`REJECT_REASON` 테이블 | 코드 상수 | 값을 바꾸는 API가 없어서 [제안·팀 확인 필요] (`workout_session/catalog.py`, `review/rules.py`) |
| API-017 지인 목록 | 정의됨 | 빈 라우터(501) | '지인' 정의가 미정 (PRD 미정 표). 그래서 확인자는 지금 '내 길드의 길드장'만 고를 수 있음 (API-035) |
| API-020 `DAILY_CAP_EXCEEDED` | 422 (경고용, 차단 여부 미정) | 없음. 상한이 다 차도 세션을 막지 않음 | 차단 여부 미정 |
| API-026 확신도 | 서버 재계산 | 앱이 보낸 `aiConfidence`를 저장 (임시) | ai/ 엔진 연결 전. **API-033 자동 승인이 이 값을 그대로 믿는다** → backlog US-03 (권한) 미충족 (PR #141) |
| API-034·037 확인 자료 | 관절 선 리플레이·통증 안내 문구 | `skeletonReplayUrl`·`painNotice`는 `null` | 리플레이 기능 없음, 통증 문구 미정 |
| API-049~051 LLM | 제공사·모델 미정 | 모의 응답(`LLM_PROVIDER=mock`) | STACK.md '제공사 확정 전 모의 응답'. 실제 LLM 연동 완료가 아님 |
| API-032 서사 예시 | `"너의 30번의 타격이..."` (숫자 있음) | 숫자가 있으면 저장하지 않음 | backlog US-05 '서사 후보에 숫자가 있으면 다시 만든다'와 노션 예시가 다름 |
| 응답에 없는 필드 | — | 여러 곳 | 각 라우터의 Swagger(`/docs`) 설명에 `[제안]`으로 적음 |

## 아직 정하지 않은 것

| 항목 | 누가 언제 |
| --- | --- |
| 노션 명세와 구현이 다른 곳(위 표)을 어느 쪽에 맞출지 | 팀, 다음 회의 |
| 시스템이 `/internal` API(031 → 033 → 041, 049~051)를 언제 어떤 순서로 부를지 (지금은 부르는 곳이 없음) | 테크리더·개발자1 |
| `DATA-MODEL.md` '아직 정하지 못한 것'에 남은 필드 결정 | 팀 |
