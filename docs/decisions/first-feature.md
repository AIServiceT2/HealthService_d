# 우리 팀의 첫 기능

> **저장 위치:** `docs/decisions/first-feature.md`

> **사용 방법**
> 1. 2-2에서 만든 뼈대 위에 **기능 하나**를 끝까지 만듭니다. 어떤 기능인지는 **팀이 고릅니다.** Claude가 정해 주지 않습니다. Claude는 후보의 빈틈을 찾아 줄 수만 있습니다.
> 2. 기능은 `backlog.md`의 **필수 스토리 하나**입니다. 인수 조건에 `미정`이 없고, 화면·서버·데이터를 **모두 거치고**, 오늘 안에 끝낼 수 있게 작은 것을 고릅니다. LLM 호출이 들어간 기능은 오늘은 피합니다(키와 실패 시 동작까지 정해야 해서 범위가 커집니다).
> 3. 이 파일은 **PM이** 팀 결정을 받아 적습니다. 2절 셋째 칸(테스트할 내용)은 **테스트 담당이 구현 전에** 적습니다. 입력과 기대 결과는 인수 조건과 `API.md`에 적힌 것만 씁니다. 같은 파일을 동시에 고치지 않습니다. 후보 비교는 팀 채팅의 후보 표로 하고 여기에는 고른 이유만 적습니다. 승인한 계획의 영역별 할 일도 문서에 옮겨 적지 않고 PM이 팀 채팅에 올립니다.
> 4. 2절의 완성 기준은 **`backlog.md`의 인수 조건에서 가져옵니다.** 새로 만들지 않습니다. 정하지 않은 규칙은 `미정`으로 남깁니다.
> 5. `>`로 시작하는 안내 문장은 지워도 됩니다.

- 작성일: 2026-11-02 (PM 초안, 1절 범위와 2절 '오늘 만드나'는 팀 확인 필요)
- 고른 스토리: `US-02` 보상·타격 수 미리보기 (기능 ID `F-03`) (출처: backlog.md US-02, PRD v1.0 3절)

- 고른 이유 (우리 팀 상황에서): [팀 작성 필요]
- 고르지 않은 후보와 이유 (다음 시간 이후에 다시 볼 것): [팀 작성 필요]
- 주의: US-02는 LLM 관여 '예 (L3·L4 생성)'인 스토리다 (출처: backlog.md US-02). 양식 안내 2번은 LLM 호출이 들어간 기능을 오늘은 피하라고 하므로, 오늘은 LLM 호출 없이 `SUBMITTED → PREPARED` 계산과 미리보기까지만 만든다 (1절).

## 1. 오늘 만드는 범위

| 만드는 것 | 만들지 않는 것 (이유) |
| --- | --- |
| 서버: 시드 데이터의 `SUBMITTED` 제출건(스쿼트 인정량 30)을 계산해 `PREPARED`로 바꾸고 타격 수 30을 저장 (2절 #1) | L3 서사·L4 교정 코멘트 LLM 호출 (LLM 제공사·모델 미정, 양식 안내 2번. 출처: PRD 미정 표) |
| 서버: 계산이 실패하면 `SUBMITTED`에 남기기 (2절 #3) | LLM 실패 시 기본 문구 저장 (기본 문구 내용 미정. 출처: PRD 미정 표, backlog US-02 미확정) |
| 데이터: 제출건의 `status`와 스냅샷의 타격 수 (필드 이름은 DATA-MODEL.md 확정 후 따름) | 본인만 미리보기 조회 (로그인 방식·토큰 저장 방식 미정. 출처: PRD v1.0 미정 표) |
| 화면: 제출건 1건의 상태와 보상 미리보기(타격 수) 표시 (화면 이름은 DESIGN.md 확정 후 따름) | 카메라 렙 인식·자동 제출(US-01). 제출건은 시드 데이터로 대신함 |
| | 스냅샷의 확정 능력치·약점 배율·카탈로그 버전·확신도 전체 (약점 배율은 MVP 제외 범위와 겹치고 확신도 계산 방법이 미정. 출처: mvp-scope.md 제외 표, PRD 미정 표) → 2절 #2는 팀 확인 필요 |

> 한 스토리 안에서도 오늘은 **끝까지 이어지는 가장 작은 흐름**만 만듭니다. 나머지 인수 조건은 다음 시간으로 남기고, 어느 것을 남겼는지 아래 표에 적습니다.

## 2. 완성 기준 (인수 조건에서 가져옴)

| # | 인수 조건 (`backlog.md` 원문) | 오늘 만드나 | 테스트할 내용 (입력 → 기대 결과, 인수 조건·`API.md`에 적힌 것만) / 확인 방법 |
| --- | --- | --- | --- |
| 1 | (정상) `SUBMITTED` 건의 계산이 끝나면 상태가 `PREPARED`가 되고, 인정 렙 30회 스쿼트의 타격 수는 30으로 저장된다 | 예 | **입력:** `status`=`SUBMITTED`, `exercise_type`=스쿼트, `counted_reps`=30인 제출건 1건 (시험용 `SUBMITTED` 시드는 미정. 출처: API.md 입력·출력 예시) → 보상 계산 실행 → **기대:** `status`=`PREPARED`, `snapshot`의 타격 수=30 (키 이름 미정). 이어서 같은 건의 미리보기를 조회 → **기대:** `status`=`PREPARED` 그대로, 타격 수 30 (출처: API.md 항목 1 '바뀌는 상태' — ② 조회는 상태를 바꾸지 않음) / **확인 방법:** pytest `test_us02_ac1_submitted_squat_30_becomes_prepared_with_30_hits` (2026-11-02 통과), 화면 '제출 상세·보상 미리보기'에서 상태와 타격 수 30을 직접 확인. 현재 구현은 `POST /submissions/{id}/prepare`·`GET /submissions/{id}`, 타격 수 키 `snapshot.hit_count` — 둘 다 router.py·service.py에 '제안·팀 확인 필요'로 적혀 있고 API.md는 아직 `미정` |
| 2 | (정상) 스냅샷에 카탈로그 버전·확정 능력치·약점 배율·AI 판정 확신도가 저장되고, 이후 운영자가 카탈로그를 바꿔도 이 제출건의 보상 수치는 바뀌지 않는다 | 팀 확인 필요 | 오늘 만들지 않음 (팀 확인 필요). 테스트 내용은 범위가 정해진 뒤 작성 |
| 3 | (실패·거절) 보상 계산이 실패하면 상태는 `SUBMITTED`에 남고, 재시도해서 계산이 성공했을 때만 `PREPARED`가 된다 | 예 | **입력:** #1과 같은 `SUBMITTED` 제출건, 보상 계산이 실패하도록 만든 상태 (실패를 일으키는 방법은 구현에 따라 정함 `미정`) → 보상 계산 실행 → **기대:** `status`=`SUBMITTED` 그대로, `snapshot`에 타격 수가 저장되지 않음. 실패 원인을 없애고 같은 건을 다시 계산 → **기대:** 그때만 `status`=`PREPARED`, 타격 수=30 (출처: backlog US-02 (실패·거절) 1번째, API.md 항목 1 '실패 응답'). 오류 코드·본문은 미정이라 검사하지 않음 / **확인 방법:** pytest `test_us02_ac3_calculation_failure_keeps_submitted_then_retry_succeeds` (2026-11-02 통과) |
| 4 | (실패·거절) LLM 호출이 실패해도 상태는 `PREPARED`가 되고, `ai_story`·`ai_form_tip`에는 미리 정한 기본 문구가 저장된다 | 아니오 (기본 문구 미정, LLM 미연결) | 오늘 만들지 않음 (기본 문구 미정, LLM 미연결). 다음 시간 |
| 5 | (권한) 보상 미리보기는 제출한 본인에게만 보이고, 다른 사용자가 같은 제출건의 미리보기를 요청하면 거부된다 | 아니오 (로그인 방식 미정) | 오늘 만들지 않음 (로그인 방식 미정). 다음 시간 |
| 6 | (LLM) LLM이 만든 `ai_story`·`ai_form_tip`은 제출건 상태와 보상 수치(경험치·피해량·타격 수)를 바꾸지 않는다. 같은 제출건에서 LLM 출력이 달라져도 보상 수치는 같다 | 아니오 (LLM 미연결) | 오늘 만들지 않음 (LLM 미연결). 다음 시간 |
| 7 | (LLM) L3 요청에는 스킬명·운동 종류·적 이름·약점 적중 여부만, L4 요청에는 판정 기준·관절 각도 요약 통계·미인정 사유만 담기고, 수치·메모·관절 좌표 원본·얼굴 정보·닉네임·길드명은 담기지 않는다 (제안서 Ⅳ-13) | 아니오 (LLM 미연결) | 오늘 만들지 않음 (LLM 미연결). 다음 시간 |

## 3. 실행 확인 (5명 모두, 각자 자기 Mac에서)

| 이름 | Mac | 서버 실행 | 화면에서 기능 확인 | 테스트 실행 | 남은 문제 (명령과 오류 메시지 그대로) |
| --- | --- | --- | --- | --- | --- |
| 김지은 | Apple M3, macOS 27.0.1 | 성공 — `docker compose up -d db` → `backend/`에서 `python3.11 -m venv .venv`, `.venv/bin/pip install -r requirements.txt`, `.venv/bin/uvicorn app.main:app --port 8000` → `GET /health` `{"status":"ok"}`. `python -m scripts.seed`로 만든 `SUBMITTED` 건을 `POST /submissions/{id}/prepare` → `PREPARED`, `hit_count` 30. 같은 건 다시 계산 → 409 `{"detail":"PREPARED 상태는 계산할 수 없음"}` | `미실행` (폰에서 직접 열어 보지 않음) | 성공 — 서버 `.venv/bin/python -m pytest -v` → 3 passed. 앱 `mobile/`에서 `npm ci`, `npm test` → 4 pass (목데이터 커밋 67666ba 반영 후 다시 실행), `npm run typecheck` → 오류 없음 | ① pytest 경고 그대로: `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.` (원문의 백틱만 뺌) ② 테스트가 끝날 때 `TRUNCATE workout_submission`을 하는데 개발용 DB(`jeonunsi`)와 같은 DB라, 시드로 넣은 제출건도 지워짐 ③ 앱 테스트가 STACK.md의 Jest + React Native Testing Library가 아니라 `tsx --test`(Node 테스트)임 → 테크리더 확인 필요 |
| 강준석 | | | | | |
| 성민규 | | | | | |
| 손범수 | | | | | |
| 이시은 | | | | | |

> 성공 / 실패 / `미실행` / `테스트 미구성`으로 씁니다. "Claude가 완료라고 답함"은 확인이 아닙니다. MCP(브라우저 서버)로 연 화면은 참고이고, **내가 직접 브라우저에서 열어** 본 결과를 씁니다.

**일부러 틀린 구현 시험** (테스트 담당, 서버·화면이 병합되고 테스트가 통과한 뒤)

| 일부러 만든 오류 | 잡아야 하는 완성 기준 # | 실제로 실패한 테스트 | 못 잡았다면 추가한 테스트 |
| --- | --- | --- | --- |
| `service.py` `prepare_submission`에서 타격 수 계산 **전에** `status`를 `PREPARED`로 바꾸고 커밋 | #3 | `test_us02_ac3_...` 실패 (`AssertionError: assert 'PREPARED' == 'SUBMITTED'`). 1 failed, 2 passed | — |
| `calculate_hit_count`에서 타격 수를 절반으로 계산 (`counted_reps // (unit * 2)`) | #1 | `test_us02_ac1_...` 실패 (`assert 15 == 30`), `test_us02_ac3_...`도 재시도 단계에서 실패. 2 failed, 1 passed | — |
| `prepare_submission`의 상태 검사(`SUBMITTED`가 아니면 거부)를 지움 → `PREPARED` 건도 다시 계산됨 | 오늘 범위(#1·#3)에는 해당 기준 없음. 스냅샷이 바뀌지 않아야 한다는 #2와 관련 | 못 잡음 (3 passed) | 추가하지 않음. #2가 '팀 확인 필요'라 기준이 정해지면 테스트 작성 |

## 4. 오늘 못 끝낸 것 (과제)

| 항목 | 담당 | 다음 시간 전까지 |
| --- | --- | --- |
| 2절 #2, #4~#7 (스냅샷 전체, LLM, 권한) | 미정 | 미정 |
| 3절 실행 확인 (강준석·성민규·손범수·이시은) | 각 본인 | 미정 |
| 화면에서 기능 확인 (폰에서 직접 열어 보기) | 김지은 | 미정 |
| API 경로·`snapshot.hit_count` 키를 API.md에 확정 (지금은 코드에만 '제안'으로 있음) | PM, 개발자1·2 합의 | 미정 |
| 확인된 실행·테스트 명령을 CLAUDE.md·README에 반영 | 테크리더 | 미정 |
| 테스트 DB를 개발 DB와 분리할지, 앱 테스트 도구(STACK.md Jest vs `tsx --test`) | 테크리더 | 미정 |

**임시 응답을 쓴 곳** (서버가 병합된 뒤 실제 주소로 바꿨는지)

| 화면 파일 | 쓰던 임시 응답 | 실제 주소로 바꿨나 |
| --- | --- | --- |
| `mobile/app/workout/[id].tsx` (`mobile/src/api/submissions.ts`) | 목데이터 `mobile/src/api/mockSubmissions.ts` 3건 (계산 전 30회 / 계산 완료 20회 / 계산 오류 15회). `EXPO_PUBLIC_USE_MOCK=true`일 때만 사용 (커밋 67666ba) | 기본값은 실제 서버 `GET /submissions/{id}`·`POST /submissions/{id}/prepare`를 부름. 목데이터 모드를 언제 없앨지는 미정 |
