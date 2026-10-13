# 표백제 — 전운시

**전**지적 **운**동 **시**점: 현실 운동 기반 픽셀 RPG

## 팀

**표백제**

| 이름 | GitHub |
| --- | --- |
| 김지은 | [@jieun0903](https://github.com/jieun0903) |
| 성민규 | [@rhtnddd](https://github.com/rhtnddd) |
| 이시은 | [@Sieun0225](https://github.com/Sieun0225) |
| 손범수 | [@sonbumsu](https://github.com/sonbumsu) |
| 강준석 | [@Kangjunseok09](https://github.com/Kangjunseok09) |

역할, 교대 계획, 블록별 정리 담당은 [팀 구성](docs/team/roles.md)에 있습니다.

## 세부 주제

> 상태: 선정안 작성 완료, 팀 확정 전 ([4단계 결정 기록](docs/decisions/topic-selection.md))

| 항목 | 내용 |
| --- | --- |
| 도메인 | 개인 운동·건강관리 지원 서비스 |
| 세부 주제 | 전운시: 운동이 전투가 되는 인증형 RPG |
| 주 사용자 | 혼자서는 운동을 꾸준히 하기 어려운 초보 운동인 |
| 해결할 문제 | 운동 결과가 숫자와 달성 여부로만 남고 인증 판정도 일관되지 않아, 성취감을 느끼며 운동을 지속하기 어렵다 |
| 한 줄 정의 | 카메라로 인식한 운동이 캐릭터의 능력치와 공격이 되고, 걸은 걸음 수가 체력을 채우며, 다른 길드의 검토를 거쳐 보상이 반영되는 서비스 |

## 필수 조건

| 조건 | 우리 서비스에서 | 자세히 |
| --- | --- | --- |
| 상태 전이 | 운동 제출건: `SUBMITTED → PREPARED → PENDING_REVIEW → APPROVED → REWARDED`. 반려(`REJECTED`), 재제출, 종료(`CLOSED`), 승인 전 취소(`CANCELED`), 신고 후 회수(`REVOKED`) 경로 포함 | [3-2 상태 전이](docs/domain/03-rules-states-llm.md) |
| LLM | 기록 요약, 이상치 설명, 전투 서사. 검토자가 확인하고 승인·반려를 결정하며, LLM은 보상 수치와 상태를 바꾸지 않음 | [3-4 LLM이 들어갈 자리](docs/domain/03-rules-states-llm.md) |

## 문서 지도

| 단계 | 문서 | 내용 |
| --- | --- | --- |
| 0 | [docs/team/roles.md](docs/team/roles.md) | 팀 구성, 역할, 교대 계획, 블록별 정리 담당 |
| 0 | [docs/domain/README.md](docs/domain/README.md) | 조사 관점, 태그 규칙, 파일 규칙, 찾아볼 곳 |
| 1 | [docs/domain/01-first-look-glossary.md](docs/domain/01-first-look-glossary.md) | 첫인상, 용어 사전, 검색어 |
| 2 | [docs/domain/02-people-flow-benchmark.md](docs/domain/02-people-flow-benchmark.md) | 사람, As-Is, 데이터, 벤치마크, 논문 |
| 3 | [docs/domain/03-rules-states-llm.md](docs/domain/03-rules-states-llm.md) | 규칙, 상태 전이, LLM 자리, 시간 규칙, 법령·통계 |
| — | [docs/domain/cards/](docs/domain/cards/) | 근거 카드 (카드마다 파일 하나) |
| — | [docs/domain/ai-check-log.md](docs/domain/ai-check-log.md) | AI 확인 기록 |
| 4 | [docs/decisions/topic-selection.md](docs/decisions/topic-selection.md) | 필수 조건 확인, 후보 평가, 주제 확정, 결정 기록 |
| 5 | [docs/interview/mvp-assumptions-questions.md](docs/interview/mvp-assumptions-questions.md) | MVP 가설, 기능 목록, 가정·위험, 질문지, 미팅 준비 |
| 6 | [docs/proposal/](docs/proposal/) | 제안서 절차, 양식(docx), 초안(draft.md), 완성본(docx·PDF) |
| — | [logs/](logs/) | 개인 회고 (`pre-[GitHub 아이디].md`) |
