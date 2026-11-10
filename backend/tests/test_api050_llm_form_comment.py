"""API-050 L4 자세 교정 코멘트 생성 — backlog US-02 (실패·거절)·(LLM), US-05 (진단·처방 표현 검사)."""

from app.modules.llm.rules import FALLBACK_FORM_TIP
from tests.llm_helpers import FakeLLM, LLMError, LLMRateLimited, post, use_llm  # noqa: F401 (fixture)
from tests.review_helpers import new_prepared

PATH = "/internal/llm/form-comments"
POSE = {"kneeAngle": {"avg": 92.4, "min": 78, "max": 110.2}, "hipAngle": {"avg": 85.1, "min": 70.3, "max": 101.7}}
GOOD = "다음 세션에서는 내려갈 때 무릎이 안쪽으로 모이지 않게 해 보세요."


def body(sid, pose=POSE):
    return {"submissionId": sid, "poseSummary": pose}


def ai_form_tip(db, sid):
    from sqlalchemy import text

    return db.execute(text("SELECT ai_form_tip FROM workout_submission WHERE id = :id"), {"id": sid}).scalar_one()


def test_us02_api050_saves_form_tip(client, db, use_llm):
    use_llm(FakeLLM(GOOD))
    sid, _ = new_prepared(client)

    res = post(client, PATH, body(sid))

    assert res.status_code == 200
    assert res.json() == {"level": "L4", "text": GOOD, "isFallback": False}
    assert ai_form_tip(db, sid) == GOOD


def test_us02_api050_sends_only_exercise_criteria_and_angle_stats(client, use_llm):
    llm = use_llm(FakeLLM(GOOD))
    sid, _ = new_prepared(client)

    post(client, PATH, body(sid))

    [(level, payload)] = llm.calls
    assert level == "L4"
    assert payload == {"exerciseName": "스쿼트", "criteria": {"kneeAngleMax": None}, "poseSummary": POSE}


def test_us05_api050_filters_diagnosis_or_prescription_words(client, use_llm):
    llm = use_llm(FakeLLM("무릎 손상이 의심되니 병원 진단을 받아 보세요.", "치료가 필요해 보여요."))
    sid, _ = new_prepared(client)

    res = post(client, PATH, body(sid))

    assert res.json() == {"level": "L4", "text": FALLBACK_FORM_TIP, "isFallback": True}
    assert len(llm.calls) == 2


def test_us05_api050_filters_numbers_then_retries(client, use_llm):
    use_llm(FakeLLM("무릎 각도를 90도까지 내려 보세요.", GOOD))
    sid, _ = new_prepared(client)

    assert post(client, PATH, body(sid)).json() == {"level": "L4", "text": GOOD, "isFallback": False}


def test_us02_api050_llm_failure_falls_back(client, db, use_llm):
    use_llm(FakeLLM(LLMError("timeout"), LLMError("timeout")))
    sid, _ = new_prepared(client)

    res = post(client, PATH, body(sid))

    assert res.status_code == 200
    assert res.json()["isFallback"] is True
    assert ai_form_tip(db, sid) == FALLBACK_FORM_TIP


def test_us02_api050_rate_limited_is_429_with_fallback_saved(client, db, use_llm):
    use_llm(FakeLLM(LLMRateLimited))
    sid, _ = new_prepared(client)

    res = post(client, PATH, body(sid))

    assert res.status_code == 429
    assert ai_form_tip(db, sid) == FALLBACK_FORM_TIP


def test_us02_api050_rejects_bad_pose_summary(client, use_llm):
    use_llm(FakeLLM(GOOD))
    sid, _ = new_prepared(client)

    out_of_range = {"kneeAngle": {"avg": 400}}
    raw_coordinates = {"kneeAngle": {"avg": 90, "points": [[0.1, 0.2]]}}
    bad_name = {"knee angle!": {"avg": 90}}
    too_many = {f"joint{chr(65 + i)}": {"avg": 90} for i in range(11)}

    for pose in (out_of_range, bad_name, too_many):
        assert post(client, PATH, body(sid, pose)).status_code == 400, pose
    # 정해 둔 키(avg·min·max) 밖의 값은 버리고 LLM에 보내지 않는다
    llm = use_llm(FakeLLM(GOOD))
    post(client, PATH, body(sid, raw_coordinates))
    assert llm.calls[0][1]["poseSummary"] == {"kneeAngle": {"avg": 90.0}}
