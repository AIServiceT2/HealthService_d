# ai/ 결정 기록

- 시작일: 2026-11-09
- 우선순위: **팀 결정 > 저장소 문서(STACK.md, backlog.md, first-feature.md 등) > `ai/SPEC.md`**. SPEC과 저장소 문서가 다르면 저장소 문서를 따르고 여기에 적는다 (2026-11-09 리더 결정).
- 상태 표기: **확정(팀 결정)** = 리더가 이 작업 지시에서 정한 것 / **제안·팀 합의 필요** = 다른 파트(백엔드·모바일)와의 계약을 바꾸거나 기준값을 정하는 것 / **가정** = 근거 없이 둔 값.
- 모든 기준값은 실제 데이터로 검증하기 전의 가안이다. 실데이터 평가 결과는 아직 없다.
- 마지막 갱신: 2026-11-09 (9단계까지, D-01~D-64)

## 팀 합의 필요 요약 (SPEC 13장 9단계 요구 항목 포함)

자세한 내용은 아래 결정 목록의 D번호를 본다. "누구와"는 제안이며 담당은 팀이 정한다.

| 항목 | D번호 | 지금 구현 | 누구와 |
| --- | --- | --- | --- |
| 좌표 좌우·미러링 규칙 | D-03 | 업로드는 미러링 전 원본, `mirrored=true`면 x 되돌림 + 좌우 스왑 | 모바일 |
| 얼굴 좌표 미전송과 무작위 동작 기준 | D-02, D-07, D-24 | 얼굴 인덱스 null 강제, 손 들기는 어깨 기준(정면 필요) | 모바일·PM |
| `kneeFlexionDeg` 정의 | D-29 | 180 − kneeAngle | 백엔드(L4)·모바일 |
| 서버 확신도만 사용 (클라이언트 값 불신) | D-36 | 승인 판단은 서버 값, 차이 ≥ 0.15면 경고 | 백엔드·모바일 |
| 재계산 허용 오차 | D-39 | 10% 초과면 `SERVER_RECOUNT_MISMATCH` | 백엔드 |
| 인정 깊이 등 판정 기준값 | D-63 | SPEC 가안 그대로 (100° 등) | 테스트 담당·전원 |
| 무작위 동작 실패 정책 | D-38 | `restart`(기본) / `review` 둘 다 구현 | 팀 회의 (PRD 미정) |
| 자동 승인 기준 0.90의 보정 근거 | D-64, D-54 | 근거 없음. 보정은 항등 매핑 | 테스트 담당·김지은 (PRD 미정) |
| 확신도가 촬영 각도 오류를 못 잡음 | D-54 | 구현 그대로 둠, 제안만 | 팀 |
| `poseSummary` 확장(formTags 등)·`RepEvent` null 허용 | D-30, D-21 | 구현함 | 백엔드(L4)·모바일 |
| 승인 경로 이름과 상태 전이 대응 | D-37 | `AI_AUTO` / `HUMAN_REVIEW` / `RESTART` | 백엔드 |
| API 계약 (오류 코드, R12 감소, 렙 대조, 시각 발급) | D-40, D-41, D-46 | 구현함 | 백엔드 |
| 청크 크기·업로드 형식·API 처리 시간 | D-06, D-12, D-44 | 300프레임·256KB 둘 다 검사 | 모바일·백엔드 |
| 실제 몸 좌표 저장 정책 (공개 저장소) | D-53 | 합성·웹캠 세션은 git 제외 | 팀 |
| ai 서비스 포트 | D-47 | 8001 (기존 5432·8000과 겹치지 않음) | 테크리더 (합의됨) |
| 루트 규칙과의 충돌 | 맨 아래 표 | — | — |

## 결정 목록

| # | 내용 | 상태 | 근거·충돌 |
| --- | --- | --- | --- |
| D-01 | 엔진 내부는 **모델 독립 공통 골격 13개**(코, 좌우 어깨·팔꿈치·손목·엉덩이·무릎·발목)를 쓴다. 어댑터 2개: MediaPipe(33) → 공통, MoveNet(COCO 17) → 공통. SPEC에서 MediaPipe 인덱스를 직접 쓰는 부분은 모두 공통 골격으로 바꿨다. z는 쓰지 않는다 | 확정(팀 결정) | SPEC 1·3.1장은 MediaPipe 고정 ↔ STACK.md '앱 안 자세 인식'은 fast-tflite+TFLite(MoveNet 등)로 시작하고 어댑터로 공통 형식 변환. STACK.md를 따름 |
| D-02 | **무작위 동작 확인의 머리 기준을 코 대신 어깨로 추정한다.** 머리 높이 = 어깨 중점 y − `head_height_ratio`(가정 0.9) × 어깨 너비. 손 든 판정 = 손목 y < 머리 높이 − `hand_above_head_margin` × 어깨 너비 | 제안·팀 합의 필요 | SPEC 6.2는 "손목이 코보다 위" ↔ backlog US-01 인수 조건 "서버로 전송된 데이터에는 얼굴 랜드마크 좌표가 없다", STACK.md "MediaPipe 0~10번, MoveNet 0~4번 제거". 코는 얼굴 랜드마크라 서버에 없음. 앱도 같은 식을 써야 기기·서버 결과가 같아짐. 공통 골격의 코 자리는 남겨 두되 서버 데이터에서는 항상 null |
| D-03 | 좌우(left/right)는 **사용자 본인 신체 기준**. 업로드 좌표는 미러링하지 않은 원본 추론 결과. `mirrored=true`면 엔진이 x를 1−x로 되돌리고 좌우 관절을 스왑한다(SPEC은 스왑만 언급. x까지 되돌려야 미러링 전과 완전히 같아짐) | 제안·모바일 팀 합의 필요 | SPEC 3.1 |
| D-04 | 어댑터 선택: `device.modelVersion` 접두어. 형식 `<family>-<variant>[@<version>]`. `mediapipe-pose…` → MediaPipe, `movenet…` → MoveNet. 그 밖은 `UnknownModelError` → API `VALIDATION_FAILED` | 제안·팀 합의 필요 (API 필드 값 형식) | 리더 결정 2 |
| D-05 | visibility(MediaPipe)와 score(MoveNet)는 둘 다 `Landmark.visibility`(0~1)로 받는다. 분포 차이는 카탈로그 `model_overrides.<family>`로 맞춘다. MoveNet `min_visibility`는 0.3(가정) | 제안·팀 합의 필요 | MoveNet 값은 측정하지 않은 가정. 실데이터로 정해야 함 |
| D-06 | **청크 크기 제한과 SPEC 청크 규격이 맞지 않는다.** camelCase JSON으로 직렬화하면 300프레임 청크가 MediaPipe 33개 약 709KB, MoveNet 17개 약 337KB로 `maxBytes` 262144B를 넘는다. 한 청크에 들어가는 최대 프레임 수는 MediaPipe 약 110개, MoveNet 약 233개다(2026-11-09 무작위 좌표로 측정). 엔진은 두 제한을 모두 검사하므로 클라이언트가 청크를 더 작게 나눠야 한다. 대안: 압축 배열 형식, 공통 13개만 업로드, maxBytes 상향 | 제안·팀 합의 필요 (API-020) | SPEC 1·3.2장 |
| D-07 | 얼굴 인덱스(MediaPipe 0~10, MoveNet 0~4)에 값이 있으면 `VALIDATION_FAILED`. 얼굴 외 관절의 null은 visibility 0으로 처리 | 제안·팀 합의 필요 | backlog US-01 (정상) 3번째 |
| D-08 | 정규화 좌표 허용 범위는 [−1, 2]. MediaPipe는 화면 밖 관절에 [0,1]을 조금 벗어난 값을 내므로 [0,1]로 막으면 실제 데이터가 거부된다. 범위 밖 관절은 visibility로 걸러짐 | 가정 | SPEC 3.2 "값 범위 확인" |
| D-09 | SPEC의 기능 번호 `JN-xxx`는 저장소 문서에 없다. 코드·문서에서는 새 번호로 쓰지 않고 SPEC 장 번호나 기존 스토리로 가리킨다. 대응(추정): JN-001→US-01, JN-003→US-03, JN-012·013·014·015→US-01(F-10·F-11·R1·R12), JN-018→US-02·05의 L4 입력, JN-019→US-07의 L2 입력. `API-0xx` 번호는 2026-11-09 main에 들어온 백엔드 빈 라우터(`backend/app/modules/*/router.py`, 노션 API 명세서 기준)의 경로 이름에 있다(API-020 세션 시작, API-021 무작위 동작 결과, API-022 청크 업로드 `PUT …/pose-chunks/{seq}`, API-026 제출, API-033 자동 승인 판정 등). 모두 501만 돌려주고 필드 계약은 아직 없어 이 엔진과 충돌하지 않는다. `docs/API.md`에는 아직 없다 | 제안·팀 합의 필요 | 루트 CLAUDE.md "기존 문서에 있는 번호만 쓴다" |
| D-10 | `first-feature.md` 범위: #1·#3은 이미 `backend/`에 구현·통과 기록이 있다(2026-11-02). 나머지 #2·#4~#7은 팀 확인·LLM·로그인 방식이 미정이고 `backend/`의 일이라 이 작업(`ai/`)에서는 하지 않는다 | 확인 필요 | first-feature.md 2·4절 |
| D-11 | 카탈로그에 SPEC 11장에 없는 키를 추가했다: `liveness.head_height_ratio`, `confidence.min_reps_for_consistency`(3)·`neutral_score`(0.5)(SPEC 7.1 문장의 숫자를 설정으로 옮김), `anomaly.frozen_motion_ratio`·`zero_jitter_*`·`stationary_motion_ratio`(SPEC 8.3에 기준 숫자가 없음), `recount.rep_match_iou`(0.5, SPEC 9.2), `model_overrides` | 가정 (값) | 매직 넘버 금지 규칙 |
| D-12 | 청크 규격(`maxFrames` 300, `maxBytes` 262144, `fps` 15)은 판정 기준이 아니라 API 계약값이라 카탈로그가 아닌 `schemas.CHUNK_SPEC`에 둔다. 크기는 서버가 받은 청크를 camelCase JSON으로 다시 직렬화해 잰다(보낸 원문 바이트와 조금 다를 수 있음) | 제안·팀 합의 필요 | SPEC 3.2 |
| D-13 | One Euro 필터는 `kneeAngle`에만 적용한다. `kneeAsymmetry`·`trunkLean`·`hipDrop`은 필터 전 값. 필터 리셋은 "마지막 유효 프레임과 지금 유효 프레임의 간격 ≥ `filter_reset_gap_ms`"일 때. 기준 자세 보정은 필터 적용 각도로 판단하고, 무효 프레임이 끼면 연속 구간을 처음부터 다시 잰다 | 가정 | SPEC 4.3·4.4 |
| D-14 | 특징에 `torso_leg_ratio`(상체 길이 ÷ (허벅지+정강이))를 추가했다. 5단계 `BODY_PROPORTION_SHIFT`용. 무릎을 굽혀도 변하지 않게 엉덩이–발목 직선 대신 허벅지+정강이를 쓴다 | 가정 | SPEC 8.3 |
| D-15 | 상태 머신에 SPEC에 없는 `WAIT_STAND` 상태를 추가했다. max_rep_ms 초과로 폐기했거나 화면 이탈로 끊은 뒤 다시 설 때(kneeAngle ≥ stand_angle)까지 기다린다. 실시간 UI의 `state`에 이 값이 나올 수 있다 | 제안·모바일 팀 합의 필요 | SPEC 5.2 "stand_angle 이상이 될 때까지 대기" |
| D-16 | 연속 무효 구간이 `max_gap_in_rep_ms`를 넘어 렙을 끊을 때: 최저각이 `attempt_angle` 아래였으면 바로 OUT_OF_FRAME으로 기록한다. 아직 시도 각도에 못 미쳤으면 보류했다가, **다시 나타난 첫 프레임의 각도가 시도 각도 아래(앉은 채 돌아옴)면 OUT_OF_FRAME으로 기록**하고 선 채로 돌아오면 기록하지 않는다. (2026-11-09 8단계 보완: 처음엔 시도 각도 전에 끊긴 렙을 모두 버렸는데, 합성 평가에서 바닥이 가려진 렙 46개가 하나도 기록되지 않아 사용자가 '화면 이탈' 안내를 못 받는 문제를 확인함) | 가정 | SPEC 5.2·5.3이 이 경우를 정하지 않음 |
| D-17 | 세션이 끝날 때 진행 중이던 렙(아직 서지 않음)은 기록하지 않는다 | 가정 | SPEC에 없음 |
| D-18 | 렙 시작 전(STANDING) 무효 프레임은 렙에 포함하지 않는다. 그래서 하강을 가린 뒤 바닥에서 다시 나타나면 재등장 시점이 렙 시작이 되어 TOO_FAST(하강 시간 부족)로 미인정된다. 인정되지 않으므로 보상 악용은 아니지만, 사유가 OUT_OF_FRAME이 아니라는 점은 알아 둘 것 | 가정 | 테스트 작성 중 확인 (`test_reason_priority_out_of_frame_first`) |
| D-19 | 렙 안의 무효 비율은 **프레임 수** 기준(렙 시작~끝까지 처리한 프레임 중 무효 프레임). 화면 이탈로 끊긴 렙은 끊길 때까지의 무효 프레임을 포함한다 | 가정 | SPEC 5.3 "무효 프레임 비율" |
| D-20 | 출력 반올림은 **0.5 올림(half-up)**: 각도 소수 1자리, 비율·hipDrop·확신도 소수 3자리. Python 기본 `round`(짝수 반올림)는 모바일과 결과가 달라질 수 있어 쓰지 않는다 | 제안·모바일 팀 합의 필요 | SPEC 13장 |
| D-21 | `RepEvent.trunkLeanAtBottom`·`kneeAsymmetryAtBottom`은 null을 허용한다(어깨나 한쪽 다리가 안 보이면 계산 불가). SPEC은 float | 제안·팀 합의 필요 (API-026 필드) | SPEC 5.4 |
| D-22 | **정면 촬영의 한계:** `angle_or_hip_drop` 모드도 렙 *시작*과 *시도* 판정은 무릎 각도(160°/145°)로 한다. 정면에서는 2D 무릎 각도가 덜 줄어들어서, 합성 데이터(무릎 벌림 0.12)에서는 깊이 80° 스쿼트가 화면상 약 133°였다. 실제 정면 촬영에서 145° 아래로 내려가지 않으면 렙 자체가 기록되지 않는다. 실데이터로 확인하기 전까지 정면 지원은 검증되지 않은 상태 | 확인 필요 (실데이터) | SPEC 5.1 |
| D-23 | 판정기는 플러그인 등록부(`counters/base.py`의 `register_counter`/`make_counter`)로 고른다. 지금 등록된 종목은 `SQUAT` 하나 | 확정(SPEC) | SPEC 1장 |
| D-24 | 무작위 동작 확인은 **카메라를 정면으로 보고** 해야 한다. 기준 길이가 어깨 너비라서 측면이면 0에 가까워져 판정이 너무 쉬워진다. 앱 안내 문구(US-01 튜토리얼)에 반영 필요 | 제안·팀 합의 필요 | D-02의 결과 |
| D-25 | 무작위 동작 유지 시간은 같은 조건이 끊김 없이 이어진 프레임의 첫 시각부터 잰다(ms). 어깨가 안 보이거나 사람이 없는 프레임은 유지를 끊고, 유효 프레임 비율의 분모에 들어간다. `issuedAtT` 전·`expiresAtT` 후 프레임은 보지 않는다 | 가정 | SPEC 6.2 |
| D-26 | `LivenessResult.evidence`에 `wrongHandDetected`(반대 손 유지 ≥ `wrong_hand_hold_ms`)를 추가했다. `wrongHandMaxHoldMs`는 항상 실제 최대값을 낸다. 양손 지시(`RAISE_BOTH_HANDS`)에서 한 손만 든 것은 "반대 손"으로 보지 않는다 | 제안·팀 합의 필요 (API 필드 추가) | SPEC 6.2 |
| D-27 | 확신도 활성 구간: SPEC대로 liveness **통과 시각**부터. 통과하지 못했으면(없는 경우 포함) 첫 프레임부터. liveness가 없을 때도 PASSED가 아니므로 `liveness_penalty`를 곱한다 | 가정 | SPEC 7.1 |
| D-28 | 무효 연속 구간의 시간 = 다음 유효 프레임 시각(없으면 활성 구간 끝) − 첫 무효 프레임 시각. 렙 시간 CV·최저각 표준편차는 **모집단 표준편차**(n으로 나눔) | 가정 | SPEC 7.1 |
| D-29 | `poseSummary.kneeFlexionDeg` = 180 − minKneeAngle (펴면 0°). API 예시의 숫자가 어느 정의인지 불명확해서 이렇게 정했다 | 제안·팀 합의 필요 (API-026, L4 입력) | SPEC 4.1 |
| D-30 | **`poseSummary` 확장:** `formTags`(SPEC 8.2), `depthConsistencyDeg`, `repDurationMs`를 넣었다. 수치는 인정 렙의 **반올림된 RepEvent 값**으로 계산한다(기기·서버가 같은 렙 목록이면 요약도 같도록). `trunkLeanDeg`·`kneeAsymmetryDeg`는 해당 값이 있는 렙만으로 계산하고, 하나도 없으면 null | 제안·팀 합의 필요 (리더 지시: poseSummary 확장은 팀 결정 전) | SPEC 8.1·8.2 |
| D-31 | formTag 판정은 SPEC 문장대로 **초과(>)**. 예: TOO_FAST 비율이 정확히 0.2면 `TEMPO_TOO_FAST`가 붙지 않는다 | 가정 | SPEC 8.2 |
| D-32 | 이상 징후 기준 해석: LANDMARKS_FROZEN = 관절 이동량 ≤ 이미지 대각선의 0.00002배(약 0.03px, 사실상 같은 좌표)가 2초 넘게 이어짐. ZERO_JITTER = 정지 구간(관절 평균 속도 < 대각선의 0.06배/초, 2초 이상)의 프레임당 이동량 중앙값 < 0.0002배(약 0.3px). FROZEN이 이미 잡히면 ZERO_JITTER는 내지 않는다. BODY_PROPORTION_SHIFT는 **서 있는 프레임만**으로 1초 구간 중앙값을 비교(구간마다 최소 3프레임). 처음 0.0005로 둔 FROZEN 기준이 ZERO_JITTER 기준보다 커서 ZERO_JITTER가 절대 나올 수 없었던 것을 테스트로 발견해 고쳤다. 모든 값은 실제 MediaPipe·MoveNet 떨림을 재 보지 않은 가정 | 가정 (실데이터 필요) | SPEC 8.3에 기준 숫자 없음 |
| D-33 | `Anomaly.detail`은 사람이 읽는 한국어 문장이다(수치 포함). L2에 넘길 때 수치를 뺄지, 코드만 넘길지는 백엔드 LLM 입력 계약에서 정한다 | 제안·팀 합의 필요 | PRD 7절 LLM에 보내지 않을 정보 |
| D-34 | **렙 판정 구간:** 무작위 동작 통과 → `passedAtT` 이후 프레임, 실패(만료·사람 없음) → `expiresAtT` 이후 프레임, 확인 없음 → 처음부터. SPEC은 실패한 경우를 정하지 않았다. 확신도 활성 구간(D-27)과는 기준이 다르다 | 가정 | SPEC 9.1 4단계 |
| D-35 | `run_session(meta, chunks, catalog=None, catalog_dir=None)`. 카탈로그를 직접 넘기면 `catalogVersion`이 같아야 한다(다르면 `ConfigError`). 스트리밍용 `SessionRunner`(push/finish)를 웹캠 데모·기기 포팅 기준으로 쓴다 | 확정(SPEC) | SPEC 9.1 |
| D-36 | **확신도는 서버 값으로만 승인 판단한다.** 클라이언트 `aiConfidence`는 비교·기록용. 차이가 0.15 이상이면 `CLIENT_CONFIDENCE_DIVERGENCE`(MEDIUM)를 `comparison.anomalies`에 넣는다. `SessionResult.anomalies`는 클라이언트 값 없이 계산되므로 따로 둔다. 승인 판단은 두 목록을 모두 본다 | 제안·팀 합의 필요 (리더 지시: 서버 확신도 재계산 정책은 팀 결정 전) | SPEC 9.2 |
| D-37 | **승인 경로 이름:** `approvalPath` = `AI_AUTO` / `HUMAN_REVIEW` / `RESTART`. SPEC의 `AUTO` 대신 DATA-MODEL.md 제안값 `AI_AUTO`를 쓴다(저장소 문서 우선). 백엔드 상태 전이와의 대응(제안): `AUTO_APPROVE` → `PREPARED → APPROVED`(approval_path=`AI_AUTO`). `HUMAN_REVIEW` → `PREPARED` 유지 + 확인 요청 버튼(US-03 (실패·거절) 1번째. 자동으로 `PENDING_REVIEW`가 되지 않음, US-07은 신청자가 보낼 때). `REJECT_RESTART` → 처리 방식은 PRD '미정'(무작위 동작 확인 실패 처리) | 제안·팀 합의 필요 | DATA-MODEL.md `approval_path`, backlog US-03·07, PRD 미정 표 |
| D-38 | `liveness_policy` 기본값 `restart`는 SPEC 가안일 뿐이다. 무작위 동작 실패 시 처리는 PRD·backlog US-01 '미확정'이다. 두 정책 모두 구현했고 카탈로그 값으로 바꾼다. 어느 쪽이든 실패 건은 자동 승인되지 않는다(US-03 (실패·거절) 2번째) | 팀 결정 필요 | PRD 미정 표 |
| D-39 | 재계산 불일치: `|서버 인정량 − clientRepCount| / max(clientRepCount, 1) > 0.10`. 서버 인정량은 사용자 감소 적용 **전** 값. 비율이 정확히 0.10이면 불일치가 아님. `SERVER_RECOUNT_MISMATCH`는 `comparison.errorCode`로 내고 HTTP 200 | 제안·팀 합의 필요 (허용 오차) | SPEC 9.2 |
| D-40 | R12 감소: `userReducedCount`가 0 이상이고 서버 인정량 이하면 그 값이 최종 인정량. 크거나 음수면 `InvalidReductionError`(`INVALID_REDUCTION`, API 400 예정) | 제안·팀 합의 필요 | SPEC 9.2, 도메인 R12, DESIGN.md 3절 "줄이기 조작 위치·서버 반영 계약 추가 확인" |
| D-41 | 렙 대조: 서버 렙 순서대로, 아직 안 쓴 클라이언트 렙 중 시간 IoU가 가장 큰 것(같으면 앞쪽)을 IoU ≥ 0.5일 때 짝짓는 결정적 탐욕 매칭. 클라이언트 렙은 `startT`·`endT`·`accepted`(·`reason`)만 읽고 나머지 필드는 무시. 클라이언트 `poseSummary`는 형식 검사 없이 기록용 | 제안·팀 합의 필요 (API-026 필드) | SPEC 9.2 |
| D-42 | 인정 렙이 0개여도 다른 조건을 만족하면 `AUTO_APPROVE`가 나올 수 있다. 보상 0 처리는 백엔드 규칙(US-01 일일 상한 초과와 같은 방식)에 맡긴다 | 확인 필요 | SPEC 9.3에 없음 |
| D-43 | 성능: 9,092프레임(15fps 약 10분) `run_session` 0.44초 (Apple M3, 2026-11-09, 커버리지 계측 없이). 측면 선택·어댑터에서 IntEnum 인덱싱을 정수로 바꿔 0.56초에서 줄였다. 성능 테스트는 측정 구간에서만 추적기(`sys.settrace`)를 잠시 꺼서, CI의 `--cov` 실행에서도 실제 실행 시간을 잰다 | 확정 (측정값) | SPEC 9.4 |
| D-44 | **API 전체 처리 시간:** 10분 세션 요청 본문이 MediaPipe 17.1MB, MoveNet 9.5MB다. JSON 파싱·검증에 0.89초 / 0.66초, 재계산(청크 크기 재직렬화 포함)에 0.66초 / 0.32초가 걸렸다(M3, 2026-11-09). **재계산 자체는 1초 안이지만 파싱까지 합치면 MediaPipe 약 1.6초.** 백엔드가 청크를 받는 대로 나눠 보내는 방식, 본문 압축 형식(D-06)을 함께 정해야 함 | 제안·팀 합의 필요 | SPEC 9.4 |
| D-45 | 내부 토큰: `AI_INTERNAL_TOKEN`이 비어 있으면 보호된 엔드포인트는 모두 401(fail closed). 비교는 `secrets.compare_digest`. 토큰 값은 `.env`에만 두고 저장소에 넣지 않는다 | 확정(보안 기본값) | SPEC 9.4, 루트 CLAUDE.md 비밀 값 규칙 |
| D-46 | API 오류: 요청 형식·청크·모델·카탈로그 → 400 `VALIDATION_FAILED`(누락 청크는 `details.missingSeq`), R12 위반 → 400 `INVALID_REDUCTION`, 토큰 → 401 `UNAUTHORIZED`, 서버 카탈로그 파일 오류 → 500 `CONFIG_ERROR`. JSON 필드는 camelCase만 받는다(snake_case 필드는 400). `/internal/liveness/issue`는 동작·문구·ID만 주고 `issuedAtT`·`expiresAtT`는 백엔드가 세션 시각 기준으로 정한다 | 제안·팀 합의 필요 (백엔드 계약) | SPEC 9.4. backend/에 AI 서비스를 부르는 코드·계약 없음(2026-11-09 origin/main `fca2229` 기준 확인. 노션 명세 기반 빈 라우터만 있음, D-09) |
| D-47 | 루트 `docker-compose.yml`의 `ai` 블록은 SPEC의 `${AI_INTERNAL_TOKEN}` 대신 `${AI_INTERNAL_TOKEN:-}`를 쓴다. 동작은 같다(값이 없으면 빈 문자열). 토큰이 없는 팀원이 `docker compose up -d db`만 실행해도 경고가 뜨던 것을 없애기 위해서. 포트 8001은 기존 서비스(db 5432, 백엔드 8000)와 겹치지 않는다 | 확정 (리더 결정: 테크리더와 합의) | SPEC 2.1 |
| D-48 | `ai-ci.yml` 트리거 경로에 `ai/**`와 함께 워크플로 파일 자신(`.github/workflows/ai-ci.yml`)을 넣었다. 워크플로만 고친 PR에서도 검사가 돌게 하려고 | 제안 | SPEC 2.1 |
| D-49 | Docker 이미지는 `python:3.11-slim`에 비루트 사용자(uid 10001)로 실행한다. 2026-11-09 로컬에서 `docker compose up -d --build ai`로 빌드·실행해 health·401·발급·재계산 응답을 확인했다 | 확정 (실행 확인) | SPEC 2.1 |
| D-50 | 테스트 실행 시 `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`가 뜬다. backend/와 같은 경고(first-feature.md 3절). 동작에는 영향 없음 | 확인 필요 (테크리더) | — |
| D-51 | **MoveNet 추출 도구는 만들지 않았다.** MoveNet 실행에는 TensorFlow 또는 TFLite 런타임이 더 필요해 의존성이 무겁다(리더 결정 2: 무거우면 어댑터·합성 테스트까지만). MoveNet 어댑터와 합성 테스트(MediaPipe와 같은 판정)는 있다. `compare_models`는 MediaPipe lite/full/heavy만 비교한다 | 후속 작업 | 리더 결정 2 |
| D-52 | 라벨 파일을 나눴다. `data/labels.csv`는 **실데이터 전용**(지금은 머리글만). 합성 샘플 라벨은 `data/labels_sample.csv`(git 제외, `tools.make_sample_data`로 재생성). SPEC 13장 8단계는 "data/labels.csv에 샘플 행"이지만 실데이터와 섞이지 않게 바꿨다 | 제안 | 루트 CLAUDE.md "데이터를 지어내지 않는다" |
| D-53 | `data/keypoints/sample/`(합성 40개 약 37MB, 재생성 가능)와 `data/keypoints/webcam/`(웹캠으로 저장한 **실제 사람 좌표**)을 git에서 뺐다. 저장소가 공개(STACK.md GitHub Actions 행)라서 팀원의 몸 좌표를 올리지 않기 위해서다. 실제 추출 세션(`data/keypoints/*.json`)을 저장소에 올릴지는 동의·보관 정책과 함께 팀이 정해야 한다 | 팀 결정 필요 | SPEC 2장(keypoints는 git 포함) ↔ 공개 저장소·개인정보 |
| D-54 | **확신도가 판정 오류를 반영하지 못한다 (합성 평가로 발견).** 확신도 구성요소(가시도·유효 비율·추적·일관성·화면 이탈)는 관절이 잘 보이는지만 재고, 촬영 각도가 판정에 맞는지는 재지 않는다. 합성 샘플 40개에서 45°·정면 세션은 깊은 렙을 얕다고 잘못 판정해 렙 수가 틀렸는데도 확신도가 약 0.9였다. 기준 0.90에서 37.5%가 자동 승인 대상이고 그중 60%가 렙 수 오답. 테스트 벡터 `09_front_view`는 인정 0인데 확신도 0.9. 보정 학습 결과는 "어떤 확신도든 정답 확률 ≤ 0.5"였다(카탈로그에는 반영하지 않음). 제안: 촬영 각도 적합도(예: 어깨 너비/상체 길이로 측면 여부 추정) 구성요소 추가, 인정 0렙 자동 승인 금지(D-42) 등. SPEC 7.1 확신도 정의를 바꾸는 일이라 팀 결정 필요 | 팀 결정 필요 | SPEC 7장 |
| D-55 | 합성 평가 수치(측면 100%, 45°·정면 0%)는 단순한 투영 모델(무릎 벌림 0.12 등)의 결과다. 실제 정확도나 촬영 권장(US-01 튜토리얼 문구)의 근거로 쓰지 않는다. 리포트에도 같은 경고를 자동으로 넣는다 | 확정 (표시 규칙) | 루트 CLAUDE.md 근거 규칙 |
| D-56 | `extract_keypoints`는 **사람이 없는 테스트 영상**(3초, 30fps, 움직이는 도형)으로만 실행해 봤다: 모델 로드, VIDEO 모드, 15fps 다운샘플(45프레임), 청크 저장까지 확인. 사람 관절이 실제로 잡히는지는 실제 영상이 없어 확인하지 못했다. 실행 중 다운샘플링 버그(부동소수 오차로 63프레임이 뽑힘)를 발견해 고쳤다 | 확인 필요 (실제 영상) | SPEC 13장 완료 기준 |
| D-57 | `download_models`는 macOS python.org 빌드에서 시스템 인증서를 못 찾아 TLS 검증에 실패했다. 검증을 끄지 않고 `certifi`(httpx 의존성으로 이미 설치됨) 인증서 묶음을 쓰게 했다. URL은 공식 문서(developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)에서 2026-11-09 확인. 받은 파일: lite 5,777,746B / full 9,398,198B / heavy 30,664,242B (sha256은 실행 로그) | 확정 (실행 확인) | SPEC 10장 1 |
| D-58 | 그래프(`plot_session`, 보정 신뢰도 곡선) 글자는 영문이다. matplotlib 기본 글꼴에 한글이 없어 운영체제마다 글자가 깨지기 때문 | 확정 | — |
| D-59 | 테스트 벡터: 좌표 소수 5자리·가시도 3자리로 반올림한 입력으로 기대 결과를 계산. 비교 허용 오차(시각 ±1프레임, 각도 ±1°, 확신도 ±0.01)는 제안값. 지금 벡터 10개는 모두 합성. 엔진이 바뀌면 `tests/test_vectors.py`가 실패하므로 재생성해야 한다 | 제안·모바일 팀 합의 필요 | SPEC 10장 9 |
| D-60 | `compare_models`를 사람이 없는 영상으로 돌리면 lite/full/heavy 추론 시간이 모두 약 13ms로 같다. 사람이 없으면 관절 추정 단계가 돌지 않기 때문으로 보인다. 모델 비교는 사람이 나오는 실제 영상으로 다시 해야 한다. 이 도구의 시간은 PC 기준이며 폰 속도가 아니다 | 확인 필요 (실제 영상) | SPEC 10장 6 |
| D-61 | `webcam_demo`: OpenCV 기본 글꼴은 한글을 못 그려 화면에는 영문 상태명, 한국어 지시 문구는 로그로 낸다. 확인용으로 `--source <영상>`·`--headless`를 추가했다. 화면 창·키 입력·카메라로 실제 스쿼트를 세는 것은 직접 실행해 확인해야 한다 | 확인 필요 (직접 실행) | SPEC 13장 완료 기준 |
| D-62 | 합성 생성기를 `tests/synth.py`에서 `tools/synth.py`로 옮겼다(샘플 데이터·테스트 벡터 도구도 써야 해서). 45° 촬영(`view="diag45"`)과 거리(`person_scale`)를 추가했다 | 확정 | SPEC 10장 |
| D-63 | **판정 기준값은 모두 SPEC 11장 가안 그대로다.** 하강 시작 160°, 시도 145°, 인정 깊이 100°, 서기 160°, 바닥 판정 여유 8°, hipDrop 0.25, 최소 렙 800ms, 최소 하강 300ms, 최대 렙 10초, 렙 안 무효 비율 0.2, 렙 안 무효 구간 1초. 실측 근거가 없다. 특히 인정 깊이 100°(kneeFlexion 80°)는 backlog US-01 "가동범위 기준"의 숫자가 문서에 없어 SPEC 값을 쓴 것이다. 실데이터를 모은 뒤 `tools.evaluate --config`로 후보 카탈로그를 비교해 정한다 | 팀 결정 필요 (테스트 담당이 비교 기준 작성) | SPEC 11장, STACK.md '확정 전 검증 계획' |
| D-64 | **자동 승인 기준 0.90의 근거가 없다.** PRD·backlog의 90%는 미확정 값이고(PRD 미정 표), 보정 매핑은 항등(`[[0,0],[1,1]]`)이라 지금 0.90은 "원시 점수 0.90"일 뿐 "렙 수가 맞을 확률 90%"가 아니다. 합성 샘플로 보정을 학습해 보니 쓸 수 없는 결과였다(D-54). 라벨이 붙은 실제 세션(정답·오답 모두 포함)을 모아 `tools.calibrate_confidence`로 점 목록을 만들고, 기준별 자동 승인 비율·오류율 표를 보고 팀이 정한다 | 팀 결정 필요 (PRD 미정: 기준은 팀, 계산 방법은 강준석·김지은) | SPEC 7.2, PRD 미정 표 |

## 루트 규칙과의 충돌 (SPEC 0장 요구)

| SPEC | 루트 규칙 | 처리 |
| --- | --- | --- |
| "명세가 모호하면 멈추지 말고 가정으로 구현" | 루트 CLAUDE.md "근거가 없으면 지어내지 않고 미정으로 표시" | 가정으로 구현하되 이 문서에 `가정`으로 표시. 계약을 바꾸는 항목은 `제안·팀 합의 필요` |
| 루트 `docker-compose.yml`, `.github/workflows/ai-ci.yml`, 루트 README 수정 | CODE-STYLE 4번: compose·CI는 테크리더, README는 PM 담당 | 2026-11-09 리더가 "테크리더와 합의됨, 추가만, ai/ 작업과 별도 커밋"으로 결정. compose `ai` 블록·`ai-ci.yml`은 커밋 `cd65f3f`, 루트 README 링크 한 줄은 9단계 별도 커밋. 기존 내용은 고치지 않음 |
| 앱은 MediaPipe 고정 | STACK.md: fast-tflite로 시작, MediaPipe와 비교 | D-01 |
| 코 기준 손 들기 판정 | backlog US-01·STACK.md: 얼굴 좌표 미전송 | D-02 |
