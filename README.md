# 전운시

**전**지적 **운**동 **시**점

> 스쿼트로 하체가 강해지고, 걸은 만큼 회복하는 현실 운동 기반 픽셀 RPG

폰 카메라 앞에서 한 맨몸 운동은 기기 안에서 한 개씩 세어지고, AI 판정을 바로 받아 캐릭터의 성장과 전투 리플레이가 됩니다. AI가 애매하다고 본 기록만 지인·길드장에게 확인을 요청합니다. 걸음 수는 캐릭터 체력을 회복시키고, 건강 앱 러닝 연동은 후순위입니다 ([제안서 v2 Ⅳ-9](docs/proposal/draft.md#9-서비스-개요)).

## 팀

| 항목 | 내용 |
| --- | --- |
| 팀명 | 표백제 |
| 배정받은 큰 도메인 | 개인 운동·건강관리 지원 서비스 |
| 세부 주제 (한 줄) | 맨몸 운동을 꾸준히 하려는 10~20대가 AI 판정을 바로 받은 운동 기록을 캐릭터 성장과 전투 리플레이로 이어갈 수 있게 하는 서비스 ([제안서 v2 Ⅳ-9](docs/proposal/draft.md#9-서비스-개요), 처음 선정안은 [4-4](docs/decisions/topic-selection.md#4-4-문제-정의서-선정한-후보)) |
| 팀원과 역할 | 아래 표 (스프린트마다 교대, 교대 계획은 [docs/team/roles.md](docs/team/roles.md)) |

| 이름 | GitHub 아이디 | S1 역할 |
| --- | --- | --- |
| 김지은 | [jieun0903](https://github.com/jieun0903) | 팀 리더 (프로덕트 오너 겸) |
| 성민규 | [rhtnddd](https://github.com/rhtnddd) | 테크 리드 |
| 이시은 | [Sieun0225](https://github.com/Sieun0225) | 개발자 1 |
| 손범수 | [sonbumsu](https://github.com/sonbumsu) | 개발자 2 |
| 강준석 | [Kangjunseok09](https://github.com/Kangjunseok09) | 테스트 담당 |

## 세부 주제 필수 조건

| 조건 | 우리 주제에서는 | 자세히 |
| --- | --- | --- |
| LLM이 서비스 기능 안에서 쓰인다 | 기록 요약(L1)과 이상치 설명(L2)을 만들어 애매한 건을 확인하는 지인·길드장이 관절 선·실루엣과 함께 보고, 전투 서사(L3)·자세 교정 코멘트(L4)·성장 리포트(L5)는 규칙 검사로 숫자·다른 스킬명 등을 거른 뒤 보여 준다. 운동 종류·횟수·보상·상태는 LLM이 바꾸지 않는다 | [제안서 v2 Ⅳ-13](docs/proposal/draft.md#13-llm-활용-방안-필수) |
| 핵심 대상에 상태 전이가 있다 | 운동 제출건 정상 경로: `SUBMITTED → PREPARED → APPROVED`(AI 판정) `→ REWARDED`. 확신도 기준 미만이면 `PREPARED → PENDING_REVIEW → APPROVED / REJECTED`. 반려 `REJECTED → SUBMITTED`(연동 세션만, 최대 2회) / `CLOSED`, 승인 전 `CANCELED`, 신고 확정 시 `REVOKED` | [제안서 v2 Ⅳ-12](docs/proposal/draft.md#12-핵심-대상과-상태-흐름-필수) (03 3-2는 아직 미팅 전 기준) |

## 문서 지도

| 단계 | 파일 | 하는 일 | 상태 |
| --- | --- | --- | --- |
| 0 | [docs/team/roles.md](docs/team/roles.md) | 팀 구성, 역할, 교대 계획 | ☑ |
| 0 | [docs/domain/README.md](docs/domain/README.md) | 조사 관점, 태그 규칙, 파일 규칙, 찾아볼 곳 | 읽기만 |
| 1 | [docs/domain/01-first-look-glossary.md](docs/domain/01-first-look-glossary.md) | 첫인상, 용어 사전, 검색어 | ☑ |
| 2 | [docs/domain/02-people-flow-benchmark.md](docs/domain/02-people-flow-benchmark.md) | 사람, 현재 흐름, 데이터, 기존 서비스, 논문 | ☑ |
| 3 | [docs/domain/03-rules-states-llm.md](docs/domain/03-rules-states-llm.md) | 규칙, 상태 전이, LLM 자리, 법령·통계 | ☑ (3-2는 미팅 전 기준, 제안서 Ⅳ-12에 맞춰 수정 필요) |
| - | [docs/domain/cards/](docs/domain/cards/) | 논문·자료 근거 카드 (카드마다 파일 하나) | ☑ |
| - | [docs/domain/ai-check-log.md](docs/domain/ai-check-log.md) | AI에게 물어본 것과 확인 결과 | ☑ |
| 4 | [docs/decisions/topic-selection.md](docs/decisions/topic-selection.md) | 필수 조건 확인, 후보 평가, 주제 확정 | ☑ |
| 5 | [docs/interview/mvp-assumptions-questions.md](docs/interview/mvp-assumptions-questions.md) | MVP 가설, 기능 목록, 가정·위험, 질문지, 미팅 준비 | ☑ |
| 6 | [docs/proposal/README.md](docs/proposal/README.md) | **클라이언트에게 보내는 프로젝트 제안서** (Claude 초안 → 팀 확인 → Word 양식, 완성본 docx·PDF) | ☑ |
| 6 | [docs/interview/client-meeting-1.md](docs/interview/client-meeting-1.md) | 1차 고객 미팅 기록 (질의응답, 피드백 처리, 팀 결정 D1~D15) | ☑ |
| - | `logs/pre-[GitHub 아이디].md` | 개인 회고 (사람마다 파일 하나) | ☑ |
| - | `logs/daily/YYYY-MM-DD-[GitHub 아이디].md` | 매일 작업 기록 ([양식](logs/daily/daily-log-template.md)) | 매일 |
| 2-1 | [docs/requirements/user-flows.md](docs/requirements/user-flows.md) | 첫 데모에서 보여줄 핵심 사용자 흐름 (상태 4개 이상) | ☑ |
| 2-1 | [docs/requirements/backlog.md](docs/requirements/backlog.md) | 스토리와 인수 조건, 필수/선택 | ☑ |
| 2-1 | [docs/decisions/mvp-scope.md](docs/decisions/mvp-scope.md) | MVP 포함·제외(이유), 제안서(v2)와 다른 점 | ☑ |
| 2-1 | [docs/decisions/stack-inputs.md](docs/decisions/stack-inputs.md) | 기술 스택을 정하기 전 우리 팀 경험·조건 정리 | ☑ |
| 2-1 | [docs/team/working-agreement.md](docs/team/working-agreement.md) | 팀 작업 규칙 | ☑ (리뷰 대기 시간만 미정) |
| 2-1 | [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/) | 스토리·버그 이슈 양식 | ☑ |
| 2-1 | [.github/pull_request_template.md](.github/pull_request_template.md) | PR 본문 양식, 리뷰 체크리스트 | ☑ |

> 단계가 끝나면 상태 칸을 ☑로 바꾸고 PR로 올립니다.

## 작업 규칙

작업 규칙은 [docs/team/working-agreement.md](docs/team/working-agreement.md)로 옮겨 다듬었습니다. 핵심만 적습니다.

- main에 바로 커밋하거나 force push하지 않습니다. 모든 변경은 브랜치를 만들고 PR로 올립니다.
- 병합 전에 팀원 1명이 GitHub에서 Approve를 누릅니다. 작성자가 혼자 병합하지 않습니다. (v2·제안서 PR은 작성자 제외 4명) 2026-10-26 기준 main 브랜치 보호가 꺼져 있어 테크 리드가 켜야 합니다.
- PR 본문에 그 파일의 정리 담당을 적고, 다른 사람이 같은 파일을 고칠 때는 정리 담당에게 먼저 말합니다.
- 근거 카드, 개인 회고, 매일 기록은 사람마다 파일이 달라 동시에 써도 충돌하지 않습니다.
