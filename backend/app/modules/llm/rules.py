"""LLM 입력·출력 규칙 (03-rules-states-llm.md 3-4, backlog US-02·05·07, 노션 API-049~051)."""

import re

# 출력 검사에 실패하면 다시 만들고, 이 횟수만큼 실패하면 기본 문구 (backlog US-05: 2번 실패하면 기본 문구)
MAX_ATTEMPTS = 2
# 출력 길이 상한 [제안·팀 확인 필요]. 한두 문장 (03 3-4)
MAX_OUTPUT_LENGTH = 200

DIGITS = re.compile(r"[0-9０-９]")

# ---- L3 전투 서사 ----

# 운동 종류별 스킬명. 스킬 카탈로그가 아직 없어 user-flows.md 5단계의 '충격파 스톰프'만 둔다 [가정]
SKILL_BY_EXERCISE: dict[str, str] = {"SQUAT": "충격파 스톰프"}
# 서사에 나오면 안 되는 아이템명. 아이템 카탈로그가 아직 없어 비어 있다 (노션 ERD '아직 정하지 못한 것')
ITEM_NAMES: tuple[str, ...] = ()
