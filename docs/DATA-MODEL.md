# 데이터 구조

> **저장 위치:** `docs/DATA-MODEL.md`

> **사용 방법**
> 1. PRD의 '데이터 구조'를 **확정**하는 문서입니다. PRD와 다르게 쓰지 않고, 확정한 내용을 PRD에도 옮깁니다.
> 2. **상태값은 `docs/domain/03-rules-states-llm.md`의 상태와 똑같이** 씁니다. 이름이 다르면 나중에 테스트가 어긋납니다.
> 3. Claude는 빠진 필드와 모순을 **찾아 주기만** 합니다. 어떤 필드를 둘지는 팀이 정합니다.
> 4. **개발자1이 씁니다.** 결정은 팀이 하고, 파일에 적는 것은 개발자1(공유 파일이라 PM이 PR로 올림)입니다.
> 5. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 확정일: (미확정 — 2026-11-02 초안, 2026-11-10 노션 ERD·구현에 맞춰 갱신, 팀 확인 전)
- 근거: 노션 `DB (ERD)` (내보낸 시각 2026-11-10T05:12:16Z, [`docs/notion-export/jeonunsi_db.json`](notion-export/jeonunsi_db.json)), 실제 코드(`backend/app/modules/*/models.py`, 2026-11-10 `main`), `PRD.md` v1.0 6·7절, `03-rules-states-llm.md` 3-2·3-4, `backlog.md` US-01~08
- 2026-11-02 초안과 달라진 점: 노션 ERD가 3NF로 표를 나눴다(예: 제출건의 `snapshot` JSON → `submission_snapshot` 테이블, `rewardable_reps` → 예약 `amount`). 바꾼 곳과 이유는 노션 ERD의 '바꾼 것' 표(`jeonunsi_db.json`의 `changes_from_DATA_MODEL_md`)에 있다

> **읽는 법:** 테이블 이름은 실제 DB 이름(snake_case). `[ERD]` = 노션 ERD에 있음. `[코드에만]` = 노션 ERD에는 없고 구현하면서 넣음 (팀 확인 필요). `[ERD에만]` = ERD에는 있지만 코드는 테이블 대신 상수로 둠. 타입은 PostgreSQL 기준.

## 테이블과 칼럼

### 1. 사용자 `app_user` (ERD: USER)

| 칼럼 | 타입 | 제약 | 설명 | 구분 |
| --- | --- | --- | --- | --- |
| `id` | UUID | PK | 사용자. 본인만 제출·조회하는 권한의 기준 (backlog US-01~06 (권한)) | [ERD] |
| `nickname` | VARCHAR(12) | NOT NULL | 2~12자. LLM·확인자 화면에 보내지 않음 (PRD 7절). 단, 확인자 화면(API-036·037)에는 신청자 닉네임이 나옴 | [ERD] |
| `birth_date` | DATE | NOT NULL | 14세 미만 가입 불가 (PRD 1절, 03 R16 `[가정]`) | [ERD] |
| `guild_id` | UUID | FK → guild (SET NULL), NULL | 소속 길드 0~1개 | [ERD] |
| `provider` | VARCHAR(16) | NOT NULL | 로그인 방식. 지금은 `EMAIL`만 (노션 API-001 가안) | [코드에만] |
| `email` | VARCHAR(254) | UNIQUE, NOT NULL | 소문자로 저장 | [코드에만] |
| `password_hash` | VARCHAR(255) | NOT NULL | scrypt 해시. 원문은 저장하지 않음 | [코드에만] |
| `created_at` | TIMESTAMPTZ | NOT NULL | 가입 시각 | [코드에만] |

### 2. 리프레시 토큰 `refresh_token` [코드에만]

노션 ERD '아직 정하지 못한 것'의 "로그인 방식 → 리프레시 토큰 등 테이블"을 노션 API-002·003 가안대로 구현한 것.

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `id` | UUID | PK | |
| `user_id` | UUID | FK → app_user (CASCADE) | |
| `token_hash` | VARCHAR(64) | UNIQUE | 토큰 원문이 아니라 SHA-256만 저장 |
| `expires_at` | TIMESTAMPTZ | NOT NULL | 발급 + 14일 |
| `revoked_at` | TIMESTAMPTZ | NULL | 재발급(rotation)·로그아웃 때 채움 |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

### 3. 길드 `guild` · 4. 길드 초대 코드 `guild_invitation` [ERD]

| 테이블 | 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `guild` | `id` | UUID | PK | |
| `guild` | `name` | VARCHAR(20) | NOT NULL | 2~20자. LLM·확인자 화면에 보내지 않음 (backlog US-07 (권한)) |
| `guild` | `leader_user_id` | UUID | FK → app_user | 길드장. 확인자 후보 (US-07). '길드장은 그 길드 소속원' 제약은 서버 코드에서 검사 |
| `guild_invitation` | `code` | VARCHAR(6) | PK | 영문 대문자·숫자 6자 `[제안]` |
| `guild_invitation` | `guild_id` | UUID | FK → guild (CASCADE) | |
| `guild_invitation` | `created_by` | UUID | FK → app_user | 발급한 길드장 |
| `guild_invitation` | `expires_at` | TIMESTAMPTZ | NOT NULL | 기본 72시간, 1시간~7일 `[제안]` |

### 5. 캐릭터 `character` [ERD]

| 칼럼 | 타입 | 제약 | 설명 | 구분 |
| --- | --- | --- | --- | --- |
| `user_id` | UUID | FK → app_user (CASCADE), UNIQUE | 사용자 1명당 1개 | [ERD]는 PK, 코드는 UNIQUE |
| `exp` | INT | NOT NULL, 기본 0 | 지급 때 늚 (backlog US-04) | [ERD] |
| `avatar_id` | VARCHAR(32) | NULL | 선택 범위 미정 | [ERD] |
| `id` | UUID | PK | | [코드에만] |
| `level` | INT | NOT NULL, 기본 1 | ERD는 '레벨은 경험치로 계산'이라 칼럼이 없음. 성장 공식이 미정이라 코드는 저장값을 씀 | [코드에만] |

### 6. 운동 종류 `EXERCISE_TYPE` [ERD에만]

ERD는 테이블(code, name, daily_cap)이지만 코드는 상수로 둔다 (`workout_session/catalog.py`). MVP 운동은 스쿼트 1종: `SQUAT` / 스쿼트 / 일일 상한 200 (client-meeting-1 질의응답 3, mvp-scope.md 제외 표). 다른 테이블의 `exercise_code`는 FK 없이 문자열.

### 7. 운동 세션 `workout_session` [ERD]

| 칼럼 | 타입 | 제약 | 설명 | 구분 |
| --- | --- | --- | --- | --- |
| `id` | UUID | PK | | [ERD] |
| `user_id` | UUID | FK → app_user (CASCADE) | 세션을 시작한 본인 | [ERD] |
| `exercise_code` | VARCHAR(32) | NOT NULL | `SQUAT` | [ERD] |
| `status` | VARCHAR(16) | NOT NULL | 아래 '세션 상태값' | [ERD] |
| `goal_reps`, `goal_sets` | INT | NULL | 목표 횟수·세트 | [ERD] |
| `target_type`, `target_id` | VARCHAR, UUID | NULL | 공략 대상 `DUNGEON` / `BOSS`. 데모 대상 미정 (PRD 미정 표) | [ERD] |
| `liveness_passed` | BOOLEAN | NULL | 무작위 동작 확인 결과. 확인 전 NULL. false·NULL이면 자동 승인 안 됨 (backlog US-03) | [ERD] |
| `started_at` | TIMESTAMPTZ | NOT NULL | | [ERD] |
| `liveness_challenge_id`, `liveness_action`, `liveness_issued_at` | UUID, VARCHAR, TIMESTAMPTZ | NOT NULL | 세션 시작 때 발급한 무작위 동작. API-021에서 같은 동작·제한 시간 안인지 검사 | [코드에만] |

### 8. 관절 좌표 청크 `pose_chunk` [ERD]

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `session_id` | UUID | PK, FK → workout_session (CASCADE) | |
| `seq` | INT | PK | 청크 순번. 같은 seq는 덮어씀 |
| `frames` | JSONB | NOT NULL | `[{ t, kp: [[x, y, visibility] 또는 null, ...] }]`. 얼굴 랜드마크 자리는 null이어야 함 (backlog US-01 (정상) 3번째, 03 R11) |
| `received_at` | TIMESTAMPTZ | NOT NULL | |

### 9. 운동 제출건 `workout_submission` [ERD]

| 칼럼 | 타입 | 제약 | 설명 | 구분 |
| --- | --- | --- | --- | --- |
| `id` | UUID | PK | 지급 멱등 키로도 씀 (STACK.md '한 번만 지급') | [ERD] |
| `user_id` | UUID | FK → app_user (CASCADE) | 신청자. 로그인한 본인으로만 생성 (US-01 (권한)) | [ERD] |
| `session_id` | UUID | FK → workout_session, UNIQUE | 세션당 제출 1건 | [ERD] |
| `exercise_code` | VARCHAR(32) | NOT NULL | 1건에 1종류 (03 R2) | [ERD] |
| `status` | VARCHAR(32) | NOT NULL | 아래 '제출건 상태값' | [ERD] |
| `started_at`, `ended_at` | TIMESTAMPTZ | NOT NULL | 같은 시간대 활성 건 거부, 일일 상한 날짜(시작 시각 KST) (03 R1·R3) | [ERD] |
| `counted_reps` | INT | NOT NULL | 인정량. 서버 재계산 값 (STACK.md '렙 수 일관성 검사') — 지금은 앱이 보낸 렙 중 인정된 수 (ai/ 엔진 연결 전, 임시) | [ERD] |
| `version` | INT | NOT NULL, 기본 0 | 상태가 바뀔 때마다 1 증가. `If-Match` 동시 수정 검사 | [ERD] |
| `confidence` | FLOAT | NOT NULL | AI 판정 확신도 0~1. 기준 0.90과 계산 방법 미확정 (PRD 미정 표). **지금은 앱이 보낸 값 (임시)** | [ERD] |
| `approval_path` | VARCHAR(16) | NULL | `AI_AUTO` / `REVIEWER`. ERD는 NOT NULL이지만 승인 전에는 값이 없어 NULL 허용 | [ERD] |
| `ai_story`, `ai_form_tip` | TEXT | NULL | L3 서사, L4 교정 코멘트. LLM 실패 시 기본 문구 (US-02·05) | [ERD] |
| `ai_summary`, `ai_flags` | TEXT | NULL | L1 요약, L2 이상치 설명(JSON 배열 `[{type, repNos, description}]`). 확인 화면에 표시만 (US-07 (LLM)) | [ERD] |
| `idempotency_key` | UUID | NOT NULL | 제출(API-026)의 `Idempotency-Key`. 같은 요청인지 가림 | [코드에만] |

### 10. 렙 기록 `rep_event` [ERD]

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `submission_id` | UUID | PK, FK → workout_submission (CASCADE) | |
| `rep_no` | INT | PK | |
| `ts` | TIMESTAMPTZ | NOT NULL | 렙 시각. 렙 간격 통계(L1·L2 입력)에 씀 |
| `counted` | BOOLEAN | NOT NULL | 인정 여부 |
| `keypoints` | JSONB | NULL | 렙의 관절 좌표 묶음(얼굴 제외). 서버 재계산이 생기면 채움 |

### 11. 일일 상한 예약 `daily_cap_reservation` [ERD]

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `submission_id` | UUID | PK, FK → workout_submission (CASCADE) | 날짜·운동 종류는 제출건의 `started_at`(KST)·`exercise_code`에서 구함 |
| `amount` | INT | NOT NULL | 보상 대상 인정량. 상한이 일부만 남으면 남은 만큼만 예약 `[가정]` (ERD '부분 예약' 미정) |
| `released_at` | TIMESTAMPTZ | NULL | 취소(US-06)·반려(US-08) 때 채움. 해제된 행은 합계에서 뺌 |

### 12. 보상 스냅샷 `submission_snapshot` [ERD]

`PREPARED`가 될 때 한 번 만들고 바꾸지 않는다 (backlog US-02 (정상) 2번째, 03 R9).

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `submission_id` | UUID | PK, FK → workout_submission (CASCADE) | |
| `catalog_version` | VARCHAR(32) | NOT NULL | 지금은 `cat_2026-11-01` (ai/ 엔진 카탈로그 이름) |
| `hit_count` | INT | NOT NULL | 타격 수. 스쿼트 1회 = 1타, 예약량 기준 (상한 초과면 0) |
| `exp`, `total_damage`, `drop_count` | INT | NOT NULL | 공식 미정, 명세 예시 비율의 가안 (`snapshot/rules.py`) |
| `weakness_multiplier` | FLOAT | NOT NULL | 약점은 MVP 제외라 1.0 |

### 13. 확인 요청 `review_request` [ERD]

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `submission_id` | UUID | PK, FK → workout_submission (CASCADE) | 제출건 1건당 최대 1개 (03 R4) |
| `reviewer_user_id` | UUID | FK → app_user (CASCADE) | 신청자 본인 불가. 지금은 '내 길드의 길드장'만 고를 수 있음 ('지인' 미정) |
| `requested_at` | TIMESTAMPTZ | NOT NULL | |
| `reason_code`, `reason_text` | VARCHAR(32), TEXT | NULL | 반려 때 둘 다 필수 (US-08). ERD는 REJECT_REASON FK, 코드는 FK 없음 |

### 14. 반려 사유 `REJECT_REASON` [ERD에만]

코드 상수 (`review/rules.py`): `RECORD_ANOMALY` 기록 이상 / `IDENTITY_FAILED` 본인 확인 실패 / `SUSPECTED_THEFT` 도용 의심 (backlog US-08의 `기록이상` / `본인확인실패` / `도용의심`, 코드 값은 노션 예시).

### 15. 지급 내역 `reward_ledger` · 16. 아이템 `item` [ERD]

| 테이블 | 칼럼 | 타입 | 제약 | 설명 | 구분 |
| --- | --- | --- | --- | --- | --- |
| `reward_ledger` | `submission_id` | UUID | PK, FK → workout_submission (CASCADE) | 한 제출건에 지급은 한 번 (US-04) | [ERD] |
| `reward_ledger` | `rewarded_at` | TIMESTAMPTZ | NOT NULL | 보호 기간 끝 = +24시간 (계산값이라 저장 안 함) | [ERD] |
| `reward_ledger` | `idempotency_key` | UUID | NOT NULL | 지급(API-041)의 `Idempotency-Key` | [코드에만] |
| `item` | `id` | UUID | PK | | [ERD] |
| `item` | `user_id` | UUID | FK → app_user (CASCADE) | | [ERD] |
| `item` | `submission_id` | UUID | FK → workout_submission (CASCADE) | 어느 제출건으로 얻었나 | [ERD] |
| `item` | `status` | VARCHAR(16) | NOT NULL | 지급 직후 `LOCKED` (US-04). 해제 뒤 이름은 미정 → 코드는 `UNLOCKED` `[제안]` | [ERD] |

### 17. 길드 주간 보스 `guild_boss` [코드에만]

ERD에 보스 모델이 없어(공략 대상 모델 미정) 전투 API(API-046)를 만들며 가안으로 넣었다 (`battle/models.py`).

| 칼럼 | 타입 | 제약 | 설명 |
| --- | --- | --- | --- |
| `id` | UUID | PK | |
| `guild_id` | UUID | FK → guild (CASCADE) | |
| `week_start` | DATE | (guild_id, week_start) UNIQUE | 그 주 월요일 (KST) |
| `hp_max` | INT | NOT NULL | 남은 체력은 저장하지 않고 '최대 체력 − 피해 합계'로 계산 |

## 관계

- 사용자 → 길드: 0~1개 소속. 길드는 길드장 사용자 1명
- 캐릭터 → 사용자: 1:1
- 운동 세션 → 사용자: N:1. 운동 세션 → 좌표 청크: 1:N
- 운동 제출건 → 운동 세션: 1:1 (세션당 제출 최대 1건)
- 운동 제출건 → 렙 기록: 1:N
- 운동 제출건 → 보상 스냅샷 / 일일 상한 예약 / 확인 요청 / 지급 내역: 각각 최대 1개
- 확인 요청 → 사용자: 확인자 1명 (신청자와 다른 사람)
- 아이템 → 운동 제출건, 사용자
- 길드 주간 보스 → 길드: 한 주에 1마리

(출처: 노션 ERD 관계 18개, `jeonunsi_db.json`의 `relationships`)

## 상태값

### 제출건 상태값 (`workout_submission.status`)

> 이름은 `03` 3-2와 같다.

| 상태값 | `03` 문서의 상태 이름 | 누가 바꿀 수 있나 | 어떤 경우에 바뀌나 |
| --- | --- | --- | --- |
| `SUBMITTED` | 제출됨 | 시스템 (세션 제출 API-026) | 같은 운동·시간대의 활성 건이 없고 일일 상한을 예약했을 때 생성. 계산 실패 시 여기 남아 재시도 (출처: 03 3-2 1·2행) |
| `PREPARED` | 계산 완료 | 규칙 엔진 (API-031) | 보상·타격 수 계산과 스냅샷 고정이 끝났을 때. LLM이 실패해도 기본 문구로 진행 (출처: 03 3-2 2행, backlog US-02) |
| `PENDING_REVIEW` | 사람 확인 중 | 신청자 (API-035) | 자동 승인 대상이 아닌 `PREPARED` 건을 확인자 1명에게 보냈을 때 (출처: 03 3-2 4행, backlog US-07) |
| `APPROVED` | 승인 | 시스템 (API-033) / 확인자 (API-038) | `PREPARED`에서 확신도 기준 이상 + 무작위 동작 확인 통과, 또는 `PENDING_REVIEW`에서 확인자 승인. 지급 실패 시 여기 남아 지급만 재시도 (출처: 03 3-2 3·5·6행) |
| `REWARDED` | 지급 완료 | 시스템 (API-041) | 보상을 한 번 반영하고 24시간 보호 기간을 시작했을 때 (출처: 03 3-2 6행, backlog US-04) |
| `REJECTED` | 반려 | 확인자 (API-039, 요청받은 사람만) | `PENDING_REVIEW`에서 사유 코드·설명과 함께 반려. 카메라 세션은 같은 요청에서 바로 `CLOSED`로 감 (출처: 03 3-2 7행, backlog US-08) |
| `CLOSED` | 종료 | 시스템 / 운영자 | 카메라 세션의 `REJECTED`(재제출 불가) 또는 도용 확정. 상한 예약 해제 (출처: 03 3-2 9행) |
| `CANCELED` | 취소 | 신청자 (API-030) | 승인 전(`SUBMITTED` / `PREPARED` / `PENDING_REVIEW`) 취소. 상한 예약 해제, 승인과 동시면 먼저 성공한 하나만 (출처: 03 3-2 10행, backlog US-06) |
| `REVOKED` | 회수 | 시스템 (운영자 확정 후) | **MVP에서 쓰지 않음** (F-07 제외, PRD v1.0 6절·mvp-scope). 값은 `03`과 맞추려고 목록에만 남김 |

- 허용하지 않는 전이: `SUBMITTED → APPROVED`, `PREPARED → REWARDED`, `PENDING_REVIEW → REWARDED`, `CLOSED` / `CANCELED` / `REVOKED`에서 나가는 전이, 카메라 세션의 `REJECTED → SUBMITTED` (출처: 03 3-2 표 아래, PRD 7절)
- 상태가 바뀔 때마다 `version`이 1 오른다. 반려는 `REJECTED`·`CLOSED` 두 번 바뀌어 2 오른다 (노션 API-039 예시 4 → 6)
- LLM이 상태를 **직접 바꾸지 않고**, 사람이나 규칙이 최종 결정하는 곳:
  - `PREPARED → APPROVED`: 확신도·판정 기준·무작위 동작 확인(규칙)이 결정. `ai_*` 필드는 쓰지 않음 (출처: 03 3-2 3행)
  - `PENDING_REVIEW → APPROVED / REJECTED`: 확인자(사람)만 결정. `ai_flags`만으로 반려되지 않음 (출처: backlog US-07·08)
  - 스냅샷의 수치: 규칙 엔진만 계산. LLM 출력이 달라져도 같음 (출처: backlog US-02 (LLM), 03 R5)

### 세션 상태값 (`workout_session.status`)

| 상태값 | 어떤 경우에 바뀌나 |
| --- | --- |
| `ACTIVE` | 세션 시작(API-020), 재개(API-024) |
| `PAUSED` | 일시중지(API-023, 카메라 끊김·앱 백그라운드). 중단 중 불완전 기록을 자동 제출하지 않음 |
| `SUBMITTED` | 제출(API-026). 이후 바뀌지 않음 |
| `DISCARDED` | 폐기(API-027). 좌표 청크를 지움. 이후 바뀌지 않음 |

(출처: 노션 API-020~027, ERD WORKOUT_SESSION)

## LLM에 보내지 않을 정보

> 제안서 Ⅳ-13과 `03` 3-4에서 가져옵니다. 이 필드는 LLM 호출 입력에 넣지 않습니다. 레벨별로 실제 보내는 필드는 `backend/app/modules/llm/service.py`의 `_l1_input`~`_l4_input`에 있습니다.

| 테이블 | 칼럼 | 보내지 않는 이유 |
| --- | --- | --- |
| `app_user` | `id`, `nickname`, `birth_date`, `email` | 사용자 식별 정보. L3는 2인칭이라 이름이 필요 없음 (출처: PRD 7절, 03 3-4 L2·L3) |
| `guild` | `name` | 식별 정보 (출처: PRD 7절) |
| `pose_chunk`, `rep_event` | `frames`, `keypoints` | 관절 좌표 원본. L1·L2는 렙 간격 통계, L4는 관절 각도 요약 통계로만, L3에는 보내지 않음 (출처: PRD 7절, 03 3-4) |
| `submission_snapshot` | `exp`, `total_damage`, `hit_count` 등 수치 | L3·L4에 수치를 넣지 않음. 서사와 결과 카드 숫자가 어긋나지 않게 (출처: backlog US-02 (LLM), 03 R10) |
| (저장하지 않음) | 영상, 얼굴 랜드마크 | 서버로 아예 받지 않음 (출처: 03 R11) |

## 시드(예시) 데이터

> 화면 확인과 테스트 입력에 쓸 데이터입니다. 실제 개인정보를 쓰지 않습니다.
> 날짜는 2026-11-03 KST. 경험치·피해량은 가안 비율(1타 = exp 5, 피해 30, `snapshot/rules.py`).

| # | 테이블 | 값 (칼럼=값) | 용도 (어느 스토리·화면) |
| --- | --- | --- | --- |
| 1 | app_user ×3, guild ×1 | `u1` nickname=테스트플레이어, guild_id=`g1` / `u2` nickname=테스트길드장, guild_id=`g1` / `u3` nickname=테스트타인 / `g1` name=테스트길드, leader_user_id=`u2` | 본인·확인자·다른 사용자 권한 확인 (US-01~08 (권한)) |
| 2 | workout_session + workout_submission + daily_cap_reservation + submission_snapshot | `u1` 세션 liveness_passed=true / `s1` exercise_code=SQUAT, counted_reps=30, confidence=0.95, status=`PREPARED` / 예약 amount=30 / 스냅샷 hit_count=30 | 첫 데모 정상 경로: 미리보기 "충격파 스톰프 ×30" → 자동 승인 → 지급 (US-02·03·04) |
| 3 | workout_submission + reward_ledger | `s2` user_id=`u1`, counted_reps=30, status=`REWARDED`, approval_path=`AI_AUTO` / 지급 내역 submission_id=`s2`, rewarded_at=지급 시각 | 리플레이 30 COMBO·결과 카드 (US-05), 같은 지급 요청 두 번 (US-04) |
| 4 | daily_cap_reservation + workout_submission | `u1` 그날 스쿼트 예약 합계=200 상태에서 `s3` counted_reps=30, 예약 amount=0, 스냅샷 hit_count=0 | 일일 상한 초과: 보상 0, "일일 상한 초과" 카드 (US-01·05 (실패·거절)) |
| 5 | workout_submission | `s4` user_id=`u1`, counted_reps=30, 세션 liveness_passed=true, confidence=0.70, status=`PREPARED` | 확신도 기준 미만: 자동 승인 안 됨 (US-03 (실패·거절)) → 길드장 `u2`에게 확인 요청 (US-07·08) |

## 아직 정하지 못한 것

| 항목 | 누가 언제 정하나 |
| --- | --- |
| `[코드에만]` 칼럼·테이블(인증 필드, `refresh_token`, `idempotency_key`, 무작위 동작 발급 칼럼, `guild_boss`, `character.level`)을 ERD에 넣을지 | 팀, 다음 회의 (ERD 반영은 노션 담당) |
| `EXERCISE_TYPE`·`REJECT_REASON`을 테이블로 둘지 코드 상수로 둘지 | 테크리더 |
| 로그인 방식: 노션 API-001~003 가안(이메일·JWT 30분·refresh 14일)으로 구현됨 → 확정 여부 | 팀 (PRD 미정 표) |
| 확신도 기준 0.90과 계산 방법, 서버 재계산(ai/ 엔진) 연결 → 지금은 앱이 보낸 `confidence`·렙 수를 씀 | 강준석·김지은, 테크리더 (PRD 미정 표) |
| 보상 대상 인정량을 부분만 예약할 수 있는지 (지금은 남은 만큼만 예약 `[가정]`) | 팀 (노션 ERD 미정) |
| 캐릭터 레벨이 경험치로만 정해지는지, 확정 능력치의 축 (정해지면 `SNAPSHOT_STAT` 테이블) | 팀 회의 (노션 ERD 미정) |
| 아이템 카탈로그, `LOCKED` 해제 뒤 상태 이름, 공략 대상(던전 적 / 주간 보스) 모델 | 팀 회의, US-04 (노션 ERD 미정) |
| "지인"을 어떻게 정할지 → 친구 목록 모델 (지금 확인자는 길드장만) | 팀 회의, US-07 (PRD 미정 표) |
| `pose_chunk` 원본 좌표의 보관·삭제 기간 (제출 후 `rep_event`로 옮기고 지울지) | 팀 회의, 개인정보 처리방침과 함께 (노션 ERD 미정) |
| 운영자 역할 저장 방식, 문의(INQUIRY)·카탈로그 버전(CATALOG) 테이블 | 범위 확인 기능이 MVP에 들어가면 (노션 ERD 미정) |
| 무작위 동작 확인 실패 시 처리 (지금은 재시도 없음, 자동 승인 안 됨) | 팀 회의, US-01 (PRD 미정 표) |
| L1 입력의 "메모"를 제출건 칼럼으로 둘지 (메모 입력이 아직 없음) | 팀 회의, US-07 (03 3-4 L1) |
