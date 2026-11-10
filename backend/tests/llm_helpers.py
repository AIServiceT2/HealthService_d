"""LLM API 테스트 공통 도구. 실제 LLM 대신 응답을 정해 둔 가짜 클라이언트를 끼운다."""

from app.modules.llm.client import LLMError, LLMRateLimited
from tests.submission_helpers import internal_headers


class FakeLLM:
    """outputs를 차례로 돌려준다. 값이 예외(클래스·객체)면 그 예외를 던진다. 받은 입력은 calls에 남는다."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls: list[tuple[str, dict]] = []

    def generate(self, level, payload):
        self.calls.append((level, payload))
        out = self.outputs.pop(0) if self.outputs else "기본 출력"
        if isinstance(out, type) and issubclass(out, Exception) or isinstance(out, Exception):
            raise out
        return out


def post(client, path: str, body: dict):
    return client.post(path, json=body, headers=internal_headers())


__all__ = ["FakeLLM", "LLMError", "LLMRateLimited", "post"]
