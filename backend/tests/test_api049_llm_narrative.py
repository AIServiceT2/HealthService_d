"""API-049 L3 전투 서사 생성 — backlog US-02 (실패·거절)·(LLM), US-05 (실패·거절)·(LLM)."""

from app.modules.snapshot.rules import FALLBACK_NARRATIVE
from tests.llm_helpers import FakeLLM, LLMError, LLMRateLimited, post, use_llm  # noqa: F401 (fixture)
from tests.review_helpers import new_prepared
from tests.submission_helpers import new_submission

PATH = "/internal/llm/narratives"


def story(client, sid, headers):
    return client.get(f"/submissions/{sid}/reward-preview", headers=headers).json()["narrative"]


def test_us02_api049_saves_narrative_to_ai_story(client, use_llm):
    llm = use_llm(FakeLLM("충격파 스톰프! 당신의 충격파가 골렘의 다리를 무너뜨렸다."))
    sid, headers = new_prepared(client)

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 200
    assert res.json() == {
        "level": "L3",
        "text": "충격파 스톰프! 당신의 충격파가 골렘의 다리를 무너뜨렸다.",
        "isFallback": False,
    }
    assert story(client, sid, headers) == {"level": "L3", "text": res.json()["text"], "isFallback": False}
    assert len(llm.calls) == 1


def test_us02_api049_sends_only_allowed_fields(client, use_llm):
    llm = use_llm(FakeLLM("충격파 스톰프! 당신의 일격이 적에게 꽂혔다."))
    sid, _ = new_prepared(client)

    post(client, PATH, {"submissionId": sid})

    [(level, payload)] = llm.calls
    assert level == "L3"
    # 스킬명·운동 종류·적 이름·약점 적중 여부만. 수치·닉네임·좌표는 없다 (backlog US-02 (LLM))
    assert payload == {"skillName": "충격파 스톰프", "exerciseName": "스쿼트", "enemyName": None, "weaknessHit": False}


def test_us05_api049_retries_output_with_number_then_succeeds(client, use_llm):
    llm = use_llm(FakeLLM("충격파가 30번 꽂혔다.", "충격파 스톰프! 당신의 일격이 적을 몰아붙였다."))
    sid, _ = new_prepared(client)

    res = post(client, PATH, {"submissionId": sid})

    assert res.json()["isFallback"] is False
    assert res.json()["text"] == "충격파 스톰프! 당신의 일격이 적을 몰아붙였다."
    assert len(llm.calls) == 2


def test_us05_api049_two_bad_outputs_fall_back(client, use_llm):
    llm = use_llm(FakeLLM("30 COMBO!", "경험치 150을 얻었다"))
    sid, headers = new_prepared(client)

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 200
    assert res.json() == {"level": "L3", "text": FALLBACK_NARRATIVE, "isFallback": True}
    assert story(client, sid, headers)["isFallback"] is True
    assert len(llm.calls) == 2


def test_us02_api049_llm_failure_falls_back_without_changing_state_or_numbers(client, use_llm):
    use_llm(FakeLLM(LLMError, LLMError))
    sid, headers = new_prepared(client)
    before = client.get(f"/submissions/{sid}/reward-preview", headers=headers).json()

    res = post(client, PATH, {"submissionId": sid})

    assert res.json()["isFallback"] is True
    after = client.get(f"/submissions/{sid}/reward-preview", headers=headers).json()
    assert after["status"] == before["status"] == "PREPARED"
    assert after["snapshot"] == before["snapshot"]  # 보상 수치는 그대로 (US-02 (LLM))


def test_us02_api049_rate_limit_saves_fallback_and_returns_429(client, use_llm):
    use_llm(FakeLLM(LLMRateLimited))
    sid, headers = new_prepared(client)

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 429
    assert res.json()["code"] == "RATE_LIMITED"
    assert story(client, sid, headers)["text"] == FALLBACK_NARRATIVE

    # 나중에 다시 부르면 기본 문구를 덮어쓴다
    use_llm(FakeLLM("충격파 스톰프! 당신의 일격이 적을 몰아붙였다."))
    assert post(client, PATH, {"submissionId": sid}).json()["isFallback"] is False


def test_us02_api049_existing_narrative_is_not_regenerated(client, use_llm):
    use_llm(FakeLLM("충격파 스톰프! 첫 서사."))
    sid, _ = new_prepared(client)
    post(client, PATH, {"submissionId": sid})
    second = use_llm(FakeLLM("충격파 스톰프! 다른 서사."))

    res = post(client, PATH, {"submissionId": sid})

    assert res.json()["text"] == "충격파 스톰프! 첫 서사."
    assert second.calls == []


def test_us02_api049_default_mock_client_works(client):
    sid, _ = new_prepared(client)

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 200
    assert res.json()["isFallback"] is False
    assert "충격파 스톰프" in res.json()["text"]


def test_us02_api049_submitted_or_missing(client, use_llm):
    use_llm(FakeLLM())
    submitted, _ = new_submission(client)

    assert post(client, PATH, {"submissionId": submitted}).status_code == 409
    assert post(client, PATH, {"submissionId": "00000000-0000-0000-0000-000000000000"}).status_code == 404


def test_us02_api049_internal_only(client):
    sid, headers = new_prepared(client)
    assert client.post(PATH, json={"submissionId": sid}).status_code == 401
    assert client.post(PATH, json={"submissionId": sid}, headers=headers).status_code == 401


def test_us05_api049_korean_number_words_are_rejected_but_ordinary_words_pass():
    """서사의 숫자 검사는 한글 수사도 본다 (backlog US-05). 단위가 붙을 때만 숫자로 본다."""
    from app.modules.llm.service import is_valid_narrative

    with_numbers = ["충격파가 서른 번 꽂혔다.", "세 번의 일격!", "삼십 회 공격", "열 개의 상자", "스물두 번 몰아쳤다", "한 번 더 내리쳤다"]
    ordinary = ["이번에는 더 깊게 앉았다.", "둘러싼 적을 쓰러뜨렸다.", "열정적인 일격이 터졌다.", "하나의 충격파가 땅을 갈랐다.", "세차게 내리쳤다.", "한계를 넘었다."]

    assert [t for t in with_numbers if is_valid_narrative(t, "충격파 스톰프")] == []
    assert [t for t in ordinary if not is_valid_narrative(t, "충격파 스톰프")] == []
