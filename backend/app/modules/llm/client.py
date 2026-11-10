"""LLM 호출. 제공사·모델은 미정이다 (STACK.md 'LLM 연동', PRD 미정 표).

제공사를 정하기 전에는 모의 응답(MockLLMClient)으로 입력 통제·출력 검사·실패 경로를 개발한다
(STACK.md '제공사 확정 전 모의 응답과 기본 문구로 실패 경로를 개발한다'). 모의 응답은 실제 LLM 연동이
아니므로 '실제 LLM 사용 완료'로 기록하지 않는다.

제공사가 정해지면 LLMClient 형식(generate)에 맞는 클래스를 하나 추가하고 get_llm_client에서 고른다.
키는 .env에만 두고 저장소에 넣지 않는다. 앱에는 키를 넣지 않는다 (LLM은 백엔드에서만 호출).
"""

import os
from typing import Any, Protocol

LLM_PROVIDER_ENV = "LLM_PROVIDER"


class LLMError(Exception):
    """호출 실패 (시간 초과·제공사 오류 등). 기본 문구로 진행한다 (03 R5)."""


class LLMRateLimited(LLMError):
    """호출 한도 초과 (노션 API-049~051 429 RATE_LIMITED)."""


class LLMClient(Protocol):
    def generate(self, level: str, payload: dict[str, Any]) -> str:
        """level(L1~L4)과 허용된 입력(payload)만 받아 글 한 덩어리를 돌려준다."""
        ...


class MockLLMClient:
    """제공사 확정 전 모의 응답. 입력으로 정해진 문장을 만들고 숫자를 넣지 않는다."""

    def generate(self, level: str, payload: dict[str, Any]) -> str:
        if level == "L3":
            enemy = payload.get("enemyName") or "적"
            return f"{payload['skillName']}! 당신의 일격이 {enemy}에게 꽂혔다."
        if level == "L4":
            return "다음 세션에서는 내려갈 때 무릎이 발끝 방향을 따라가게 해 보세요."
        if level == "L1":
            return f"{payload['exerciseName']} 기록입니다. 렙 간격이 대체로 고르게 이어졌어요."
        if level == "L2":
            return "렙 사이 간격이 다른 구간보다 짧아요. 관절 선으로 동작을 확인해 주세요."
        raise LLMError(f"알 수 없는 level: {level}")


def get_llm_client() -> LLMClient:
    """LLM_PROVIDER가 없거나 'mock'이면 모의 응답. 다른 값은 제공사가 정해지기 전이라 쓸 수 없다."""
    provider = os.environ.get(LLM_PROVIDER_ENV, "mock")
    if provider == "mock":
        return MockLLMClient()
    raise RuntimeError(f"LLM 제공사가 정해지지 않았습니다 ({LLM_PROVIDER_ENV}={provider})")
