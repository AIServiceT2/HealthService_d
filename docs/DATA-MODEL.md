# 데이터 구조

> **저장 위치:** `docs/DATA-MODEL.md`

> **사용 방법**
> 1. PRD의 '데이터 구조'를 **확정**하는 문서입니다. PRD와 다르게 쓰지 않고, 확정한 내용을 PRD에도 옮깁니다.
> 2. **상태값은 `docs/domain/03-rules-states-llm.md`의 상태와 똑같이** 씁니다. 이름이 다르면 나중에 테스트가 어긋납니다.
> 3. 모델마다 **핵심 필드 3~5개**부터 시작합니다. 필드를 많이 만들지 않습니다.
> 4. Claude는 빠진 필드와 모순을 **찾아 주기만** 합니다. 어떤 필드를 둘지는 팀이 정합니다.
> 5. 시드(예시) 데이터 3~5건은 오늘 만드는 기능의 화면 확인에 쓰고, 다음 시간 테스트 입력으로도 씁니다.
> 6. **개발자1이 씁니다.** 결정은 팀이 하고, 파일에 적는 것은 개발자1(공유 파일이라 PM이 PR로 올림)입니다.
> 7. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 확정일: (미확정 — 2026-11-02 초안, 팀 확인 전)
- 근거: `PRD.md` v1.0 3·6·7절·미정 표, `03-rules-states-llm.md` 3-1·3-2·3-4, `backlog.md` US-01~08, `STACK.md` '핵심 기능과 기술의 연결'·'입력 데이터 계약과 재시도 계획'
- 범위: `first-feature.md`가 아직 비어 있어 첫 데모 흐름(US-01~05)과 MVP 필수 스토리(US-06~08), 그 전제인 F-01(PRD v1.0 3절)을 기준으로 씀. 첫 기능이 정해지면 시드를 그 스토리에 맞춰 줄임

> **읽는 법:** ★ = 첫 데모에 꼭 필요한 핵심 필드. `[추가]` = PRD 6절에는 없지만 인수 조건·STACK.md가 요구해서 넣은 필드 (팀이 넣을지 정함). 영문 필드 이름·타입·값 표기는 모두 `[제안·팀 확인 필요]`입니다.

## 모델과 필드

| 모델 | 필드 | 타입 | 필수 | 설명 | 연결된 기능 ID |
| --- | --- | --- | --- | --- | --- |
| 사용자 (User) | ★ `id` | UUID | 예 | 로그인 계정. 본인만 제출·조회하는 권한의 기준. 로그인 방식은 미정 (출처: PRD 3절 F-01 행, backlog US-01~06 (권한)) `[추가]` | F-01 |
| 사용자 (User) | ★ `nickname` | 문자열 | 예 | 화면 표시용. LLM·확인자 화면에 보내지 않음 (출처: PRD 7절) `[추가]` | F-01 |
| 사용자 (User) | `birth_date` | 날짜 | 예 | 14세 미만 가입 불가 확인용 (출처: PRD 1절, 03 R16 `[가정]`) `[추가]` | F-01 |
| 사용자 (User) | `guild_id` | UUID → Guild | 아니오 | 소속 길드. 길드장을 확인자로 찾을 때 씀 (출처: PRD 3절 F-01 행 '길드장 찾기') `[추가]` | F-01, F-04 |
| 길드 (Guild) | ★ `id`, `name` | UUID, 문자열 | 예 | 이름은 확인자 화면·LLM 입력에 넣지 않음 (출처: backlog US-07 (권한)) `[추가]` | F-01 |
| 길드 (Guild) | ★ `leader_user_id` | UUID → User | 예 | 길드장. US-07 확인자 후보 (출처: backlog US-07) `[추가]` | F-01, F-04 |
| 캐릭터 (Character) | ★ `user_id` | UUID → User (유니크) | 예 | 사용자 1명당 1개 (출처: PRD 3절 F-01 행) `[추가]` | F-01 |
| 캐릭터 (Character) | ★ `level`, `exp` | 정수 | 예 | 지급 때 경험치가 늚 (출처: backlog US-04 (정상)) `[추가]` | F-01, F-05 |
| 운동 제출건 (WorkoutSubmission) | ★ `id` | UUID | 예 | 지급 멱등 키로도 씀 (출처: STACK.md '한 번만 지급') | F-02 |
| 운동 제출건 (WorkoutSubmission) | ★ `user_id` | UUID → User | 예 | 신청자. 로그인한 본인으로만 생성 (출처: backlog US-01 (권한)) `[추가]` | F-02 |
| 운동 제출건 (WorkoutSubmission) | `session_id` | UUID | 예 | (`user_id`, `session_id`) 유니크. 같은 세션 재전송 시 중복 접수 방지 (출처: STACK.md '입력 데이터 계약과 재시도 계획') `[추가]` | F-02 |
| 운동 제출건 (WorkoutSubmission) | ★ `status` | 문자열 | 예 | 아래 '상태값' 표의 값 (출처: PRD 6절, 03 3-2) | F-02~F-05 |
| 운동 제출건 (WorkoutSubmission) | ★ `exercise_type` | 문자열 | 예 | 운동 종류. 1건에 1종류, MVP는 스쿼트뿐 (출처: PRD 6절, 03 R2, mvp-scope 제외 표) | F-02, F-10 |
| 운동 제출건 (WorkoutSubmission) | `started_at`, `ended_at` | 시각 | 예 | 같은 시간대 활성 건 거부, 일일 상한 날짜(시작 시각 기준 KST) (출처: backlog US-01 (실패·거절), 03 R1·R3) `[추가]` | F-02 |
| 운동 제출건 (WorkoutSubmission) | ★ `counted_reps` | 정수 | 예 | 인정량. 서버가 관절 좌표로 다시 계산한 값, 앱 값이 더 크면 거부 (출처: PRD 6절, STACK.md '렙 수 일관성 검사', 03 R12) | F-02, F-11 |
| 운동 제출건 (WorkoutSubmission) | `rewardable_reps` | 정수 | 예 | 보상 대상 인정량. 일일 상한을 넘으면 0 (출처: backlog US-01 (실패·거절) 1번째, 03 R1) `[추가]` | F-02, F-03 |
| 운동 제출건 (WorkoutSubmission) | `pose_data` | JSON (`jsonb`) | 예 | 얼굴 랜드마크를 뺀 관절 좌표 + 렙 타임스탬프. 영상은 받지 않음 (출처: backlog US-01 (정상) 3번째, 03 R11) `[추가]` | F-02 |
| 운동 제출건 (WorkoutSubmission) | `liveness_passed` | 참/거짓 | 예 | 무작위 동작 확인 통과 여부. 거짓이면 자동 승인 안 됨 (출처: backlog US-03 (실패·거절) 2번째) `[추가]` | F-04 |
| 운동 제출건 (WorkoutSubmission) | ★ `confidence` | 소수 (0~1) | 예 | AI 판정 확신도. 기준 0.90과 계산 방법 모두 미확정 (출처: PRD 6절·미정 표) | F-04 |
| 운동 제출건 (WorkoutSubmission) | `approval_path` | 문자열 (`AI_AUTO` / `REVIEWER`) | 승인 때 | 승인 경로: AI 자동 승인 / 확인자 (출처: PRD 6절, backlog US-03 (정상) 2번째) | F-04 |
| 운동 제출건 (WorkoutSubmission) | ★ `snapshot` | JSON (`jsonb`) | `PREPARED`부터 | 카탈로그 버전·확정 능력치·약점 배율·타격 수·경험치·총 피해량·확신도. 카탈로그가 바뀌어도 이 값으로 지급 (출처: PRD 6절, backlog US-02 (정상) 2번째, 03 R9) | F-03 |
| 운동 제출건 (WorkoutSubmission) | `ai_story`, `ai_form_tip` | 문자열 | 아니오 | L3 서사, L4 교정 코멘트. LLM 실패 시 기본 문구 (출처: PRD 6절, backlog US-02·05) | F-03, F-06, F-13 |
| 운동 제출건 (WorkoutSubmission) | `ai_summary`, `ai_flags` | 문자열 | 아니오 | L1 요약, L2 이상치 설명. 확인 화면에 표시만 (출처: PRD 6절, backlog US-07 (LLM)) | F-04 |
| 확인 요청 (ReviewRequest) | ★ `submission_id` | UUID → WorkoutSubmission (유니크) | 예 | 제출건 1건당 확인자 1명 (출처: PRD 6절, 03 R4) | F-04 |
| 확인 요청 (ReviewRequest) | ★ `reviewer_user_id` | UUID → User | 예 | 지인 또는 길드장. 신청자 본인이면 거부 (출처: PRD 6절, backlog US-07 (실패·거절)) | F-04 |
| 확인 요청 (ReviewRequest) | `reason_code`, `reason_text` | 문자열 (`기록이상` / `본인확인실패` / `도용의심`), 문자열 | 반려 때 예 | 둘 중 하나라도 없으면 반려 거부 (출처: PRD 6절, backlog US-08) | F-04 |
| 일일 상한 예약 (DailyCapReservation) | ★ `submission_id` | UUID → WorkoutSubmission (유니크) | 예 | 취소·반려 때 그 건의 예약만 해제하려면 필요 (출처: backlog US-06·08 (정상) 2번째) `[추가]` | F-02 |
| 일일 상한 예약 (DailyCapReservation) | ★ `date`, `exercise_type`, `amount` | 날짜(KST), 문자열, 정수 | 예 | 날짜·운동 종류·예약량. 스쿼트 상한 200회 (출처: PRD 6절, client-meeting-1 질의응답 3) | F-02 |
| 일일 상한 예약 (DailyCapReservation) | `released_at` | 시각 | 아니오 | 해제 시각. 해제된 행은 합계에서 뺌 `[추가]` | F-02, F-04 |
| 지급 내역 (RewardLedger) | ★ `submission_id` | UUID → WorkoutSubmission (유니크) | 예 | 멱등 키. 같은 지급 요청엔 이 행을 그대로 돌려줌 (출처: STACK.md '한 번만 지급', backlog US-04 (실패·거절) 1번째) | F-05 |
| 지급 내역 (RewardLedger) | ★ `exp`, `stat_exp`, `damage` | 정수 | 예 | 경험치·능력치 경험치·보스(또는 던전) 피해. 스냅샷 값 그대로 (출처: PRD 6절) | F-05 |
| 지급 내역 (RewardLedger) | `protection_ends_at` | 시각 | 예 | 지급 시각 + 24시간. 그 전엔 능력치 경험치 '확정 대기' (출처: backlog US-04 (정상) 2번째, 03 R7) `[추가]` | F-05 |
| 보유 아이템 (Item) | ★ `user_id`, `submission_id` | UUID | 예 | 누가 어느 제출건으로 얻었나. PRD 6절은 아이템을 지급 내역 안에 둠 → 별도 모델로 뺄지 팀 결정 `[추가]` | F-05 |
| 보유 아이템 (Item) | ★ `status` | 문자열 (`LOCKED` / 해제 이름 미정) | 예 | 지급 직후 `LOCKED` (출처: backlog US-04 (정상) 2번째) `[추가]` | F-05 |

## 관계
- 사용자 → 길드 (사용자는 길드 0~1개에 속한다. 길드는 길드장 사용자 1명을 가진다)
- 캐릭터 → 사용자 (1:1)
- 운동 제출건 → 사용자 (제출건은 신청자 한 명에 속한다)
- 확인 요청 → 운동 제출건 (제출건 1건당 최대 1개), 확인 요청 → 사용자 (확인자 1명, 신청자와 다른 사람)
- 일일 상한 예약 → 운동 제출건 (1:1)
- 지급 내역 → 운동 제출건 (제출건 1건당 최대 1개 — 한 번만 지급)
- 보유 아이템 → 운동 제출건, 사용자

## 상태값 (핵심 대상의 `status`)

> 운동 제출건(WorkoutSubmission)의 상태. 이름은 `03` 3-2와 같다.

| 상태값 | `03` 문서의 상태 이름 | 누가 바꿀 수 있나 | 어떤 경우에 바뀌나 |
| --- | --- | --- | --- |
| `SUBMITTED` | 제출됨 | 시스템 (카메라 세션 종료 시 자동 생성) | 같은 운동·시간대의 활성 건이 없고 일일 상한을 원자적으로 예약했을 때 생성. 계산 실패 시 여기 남아 재시도 (출처: 03 3-2 1·2행) |
| `PREPARED` | 계산 완료 | 규칙 엔진 + 시스템 | 보상·타격 수 계산과 스냅샷 고정이 끝났을 때. LLM이 실패해도 기본 문구로 진행 (출처: 03 3-2 2행, backlog US-02) |
| `PENDING_REVIEW` | 사람 확인 중 | 신청자 | 확신도 기준 미만인 `PREPARED` 건을 확인자 1명에게 보냈을 때 (출처: 03 3-2 4행, backlog US-07) |
| `APPROVED` | 승인 | 시스템 (AI 판정) / 확인자 | `PREPARED`에서 확신도 기준 이상 + 무작위 동작 확인 통과, 또는 `PENDING_REVIEW`에서 확인자 승인. 지급 실패 시 여기 남아 지급만 재시도 (출처: 03 3-2 3·5·6행) |
| `REWARDED` | 지급 완료 | 시스템 (트랜잭션) | 보상을 한 번 반영하고 24시간 보호 기간을 시작했을 때 (출처: 03 3-2 6행, backlog US-04) |
| `REJECTED` | 반려 | 확인자 (요청받은 사람만) | `PENDING_REVIEW`에서 사유 코드·설명과 함께 반려 (출처: 03 3-2 7행, backlog US-08) |
| `CLOSED` | 종료 | 시스템 / 운영자 | 카메라 세션의 `REJECTED`(재제출 불가) 또는 도용 확정. 상한 예약 해제 (출처: 03 3-2 9행) |
| `CANCELED` | 취소 | 신청자 | 승인 전(`SUBMITTED` / `PREPARED` / `PENDING_REVIEW`) 취소. 상한 예약 해제, 승인과 동시면 먼저 성공한 하나만 (출처: 03 3-2 10행, backlog US-06) |
| `REVOKED` | 회수 | 시스템 (운영자 확정 후) | **MVP에서 쓰지 않음** (F-07 제외, PRD v1.0 6절·mvp-scope). 값은 `03`과 맞추려고 목록에만 남김 |

- 허용하지 않는 전이: `SUBMITTED → APPROVED`, `PREPARED → REWARDED`, `PENDING_REVIEW → REWARDED`, `CLOSED` / `CANCELED` / `REVOKED`에서 나가는 전이, 카메라 세션의 `REJECTED → SUBMITTED` (출처: 03 3-2 표 아래, PRD 7절)
- 취소·반려 경로로 가는 상태: `CANCELED` (US-06), `REJECTED` → `CLOSED` (US-08). `REJECTED → SUBMITTED` 재제출은 MVP 제외 (출처: mvp-scope 제외 표)
- LLM이 상태를 **직접 바꾸지 않고**, 사람이나 규칙이 최종 결정하는 곳:
  - `PREPARED → APPROVED`: 확신도·판정 기준·무작위 동작 확인(규칙)이 결정. `ai_*` 필드는 쓰지 않음 (출처: 03 3-2 3행)
  - `PENDING_REVIEW → APPROVED / REJECTED`: 확인자(사람)만 결정. `ai_flags`만으로 반려되지 않음 (출처: backlog US-07·08)
  - `snapshot`·지급 내역의 수치: 규칙 엔진만 계산. LLM 출력이 달라져도 같음 (출처: backlog US-02 (LLM), 03 R5)

## LLM에 보내지 않을 정보
> 제안서 Ⅳ-13과 `03` 문서에서 가져옵니다. 이 필드는 LLM 호출 입력에 포함하지 않습니다.

| 모델 | 필드 | 보내지 않는 이유 |
| --- | --- | --- |
| 사용자 (User) | `id`, `nickname`, `birth_date` | 사용자 식별 정보. L3는 2인칭이라 이름이 필요 없음 (출처: PRD 7절, 03 3-4 L2·L3) |
| 길드 (Guild) | `name` | 식별 정보 (출처: PRD 7절) |
| 운동 제출건 (WorkoutSubmission) | `pose_data` | 관절 좌표 원본. L1·L2·L4는 각도 요약 통계로만, L3에는 보내지 않음 (출처: PRD 7절, 03 3-4) |
| 운동 제출건 (WorkoutSubmission) | `snapshot`의 수치 | L3·L4에 수치를 넣지 않음. 서사와 결과 카드 숫자가 어긋나지 않게 (출처: backlog US-02 (LLM), 03 R10) |
| 지급 내역 (RewardLedger) | `exp`, `stat_exp`, `damage` | 위와 같음 (출처: backlog US-05 (LLM)) |
| (저장하지 않음) | 영상, 얼굴 랜드마크 | 서버로 아예 받지 않음 (출처: 03 R11) |

## 시드(예시) 데이터
> 화면 확인과 다음 시간 테스트에 쓸 데이터입니다. 실제 개인정보를 쓰지 않습니다.
> 날짜는 2026-11-03 KST. 경험치·피해량 값은 카탈로그가 없어 `(카탈로그 미정)`.

| # | 모델 | 값 (필드=값) | 용도 (어느 스토리·화면) |
| --- | --- | --- | --- |
| 1 | User ×3, Guild ×1 | `u1` nickname=테스트플레이어, guild_id=`g1` / `u2` nickname=테스트길드장, guild_id=`g1` / `u3` nickname=테스트타인 / `g1` name=테스트길드, leader_user_id=`u2` | 본인·확인자·다른 사용자 권한 확인 (US-01~08 (권한)) |
| 2 | WorkoutSubmission + DailyCapReservation | `s1` user_id=`u1`, exercise_type=스쿼트, counted_reps=30, rewardable_reps=30, liveness_passed=참, confidence=0.95, status=`PREPARED`, snapshot.타격 수=30 / 예약 date=2026-11-03, amount=30 | 첫 데모 정상 경로: 미리보기 "충격파 스톰프 ×30" → 자동 승인 → 지급 (US-02·03·04) |
| 3 | WorkoutSubmission + RewardLedger | `s2` user_id=`u1`, counted_reps=30, status=`REWARDED`, approval_path=`AI_AUTO` / 지급 내역 submission_id=`s2`, exp·damage=(카탈로그 미정), protection_ends_at=지급+24시간 | 리플레이 30 COMBO·결과 카드 (US-05), 같은 지급 요청 두 번 (US-04) |
| 4 | DailyCapReservation + WorkoutSubmission | `u1` 그날 스쿼트 예약 합계=200 상태에서 `s3` counted_reps=30, rewardable_reps=0 | 일일 상한 초과: 보상 0, "일일 상한 초과" 카드 (US-01·05 (실패·거절)) |
| 5 | WorkoutSubmission | `s4` user_id=`u1`, counted_reps=30, liveness_passed=참, confidence=0.70, status=`PREPARED` | 확신도 기준 미만: 자동 승인 안 됨 (US-03 (실패·거절)). 이후 US-07·08 테스트 |

## 아직 정하지 못한 것
| 항목 | 누가 언제 정하나 |
| --- | --- |
| `[추가]` 필드를 넣을지, ★ 핵심 필드만으로 시작할지. 넣으면 PRD 6절에도 옮김 | 팀, 첫 기능 결정 때 (옮기기는 PM) |
| 영문 필드 이름·타입·값 표기(`SQUAT`, `AI_AUTO` 등) | 테크리더, `CODE-STYLE.md` 1번 이름 규칙과 함께 |
| 로그인 방식 → 사용자 모델의 인증 필드 | 팀, 뼈대 세우기 전 (PRD 미정 표) |
| 확신도 기준 0.90과 계산 방법 → `confidence` 저장 형식(0~1 / %) | 강준석·김지은, US-03 구현 시작 전 (PRD 미정 표) |
| 무작위 동작 확인 실패 시 처리 → `liveness_passed`=거짓 건이 생기는지 | 팀 회의, US-01 구현 시작 전 (PRD 미정 표) |
| 공략 대상(던전 적 / 주간 보스) → `damage` 반영 대상, 보스·던전 모델 필요 여부 | 팀 회의, US-02·US-04 구현 시작 전 (PRD 미정 표) |
| `pose_data`를 서버에 얼마나 보관할지 (재계산 후 삭제 / US-07 관절 선용 보관) | 팀 회의, 개인정보 처리방침과 함께 (STACK.md '확인할 것') |
| 일일 상한 예약: 건별 행(위 안)으로 두고 합계로 셀지, 날짜·운동별 합계 한 행으로 둘지 (동시 제출 시 원자적 예약 방법) | 테크리더, US-01 서버 구현 전 |
| 능력치 모델(축, '확정 대기' 저장 방법), 아이템을 별도 모델로 둘지·`LOCKED` 해제 뒤 상태 이름 | 팀 회의, US-04 구현 시작 전 |
| LLM 재시도·백그라운드 작업 상태 테이블 필요 여부 | 테크리더, US-02 구현 시작 전 (STACK.md '입력 데이터 계약과 재시도 계획') |
| "지인"을 어떻게 정할지 → 친구 목록 모델 필요 여부 | 팀 회의, US-07 구현 시작 전 (PRD 미정 표) |
| L1 입력의 "메모"를 제출건 필드로 둘지 (첫 데모 흐름엔 메모 입력이 없음) | 팀 회의, US-07 구현 시작 전 (03 3-4 L1) |
