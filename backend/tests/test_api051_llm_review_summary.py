"""API-051 L1 기록 요약·L2 이상치 설명 생성 — backlog US-07 (LLM)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.llm_helpers import FakeLLM, LLMError, LLMRateLimited, post, use_llm  # noqa: F401 (fixture)
from tests.review_helpers import leader_and_member, new_prepared, request_review
from tests.submission_helpers import prepare, start_session, submit, submit_body, upload_chunks

PATH = "/internal/llm/review-summaries"


def prepared_with_reps(client, intervals_sec: list[float], *, headers=None):
    """렙 간격을 정해서 제출하고 PREPARED로 만든다. 렙 수 = 간격 수 + 1."""
    from tests.character_helpers import new_player

    if headers is None:
        _, headers = new_player(client)
    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id)
    now = datetime.now(UTC)
    total = sum(intervals_sec)
    times = [now - timedelta(seconds=total + 1)]
    for gap in intervals_sec:
        times.append(times[-1] + timedelta(seconds=gap))
    reps = [{"repNo": i + 1, "ts": t.isoformat(), "counted": True} for i, t in enumerate(times)]
    body = {**submit_body(counted=len(reps)), "reps": reps, "clientRepCount": len(reps), "aiConfidence": 0.82}
    res = submit(client, headers, session_id, body)
    assert res.status_code == 202, res.json()
    sid = res.json()["submissionId"]
    assert prepare(client, sid).status_code == 200
    return sid, headers


def test_us07_api051_summary_and_rule_anomalies(client, use_llm):
    llm = use_llm(FakeLLM("스쿼트 5회, 중간에 빨라진 구간이 있어요.", "11~12번째 렙이 너무 빨라요."))
    sid, _ = prepared_with_reps(client, [3.0, 3.0, 0.4, 3.0])

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 200
    assert res.json() == {
        "summary": "스쿼트 5회, 중간에 빨라진 구간이 있어요.",
        "anomalies": [{"type": "TEMPO_TOO_FAST", "repNos": [4], "description": "11~12번째 렙이 너무 빨라요."}],
    }
    [(l1, l1_payload), (l2, l2_payload)] = llm.calls
    assert (l1, l2) == ("L1", "L2")
    # 운동 종류·렙 수·간격 통계만. 닉네임·좌표·길드명은 없다 (US-07 (LLM))
    assert l1_payload == {
        "exerciseName": "스쿼트",
        "countedReps": 5,
        "uncountedReps": 0,
        "repIntervalSec": {"avg": 2.35, "min": 0.4, "max": 3.0, "std": 1.13},
    }
    assert set(l2_payload) == {"anomalyType", "repNos", "repIntervalSec"}


def test_us07_api051_uniform_tempo_is_flagged(client, use_llm):
    use_llm(FakeLLM("요약", "간격이 기계처럼 같아요."))
    sid, _ = prepared_with_reps(client, [2.0] * 10)

    anomalies = post(client, PATH, {"submissionId": sid}).json()["anomalies"]

    assert anomalies == [{"type": "UNIFORM_TEMPO", "repNos": [], "description": "간격이 기계처럼 같아요."}]


def test_us07_api051_no_anomaly_no_l2_call(client, use_llm):
    llm = use_llm(FakeLLM("고르게 잘 했어요."))
    sid, _ = prepared_with_reps(client, [2.5, 3.1, 2.8])

    assert post(client, PATH, {"submissionId": sid}).json()["anomalies"] == []
    assert [level for level, _ in llm.calls] == ["L1"]


def test_us07_api051_failure_uses_input_sentence_and_fixed_descriptions(client, use_llm):
    use_llm(FakeLLM(LLMError, LLMError, LLMError, LLMError))
    sid, _ = prepared_with_reps(client, [3.0, 0.5])

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 200
    assert res.json() == {
        "summary": "스쿼트 인정 3회, 미인정 0회. 렙 간격 평균 1.75초.",
        "anomalies": [{"type": "TEMPO_TOO_FAST", "repNos": [3], "description": "렙 사이 간격이 매우 짧은 구간이 있어요."}],
    }


def test_us07_api051_rate_limited_saves_fallback(client, db, use_llm):
    use_llm(FakeLLM(LLMRateLimited))
    sid, _ = prepared_with_reps(client, [3.0, 3.0])

    res = post(client, PATH, {"submissionId": sid})

    assert res.status_code == 429
    saved = db.execute(text("SELECT ai_summary FROM workout_submission WHERE id = :id"), {"id": sid}).scalar_one()
    assert saved.startswith("스쿼트 인정 3회")


def test_us07_api051_shows_on_review_screens_without_changing_state(client, use_llm):
    use_llm(FakeLLM("요약 문장", "빠른 구간 설명"))
    leader_id, leader_headers, member = leader_and_member(client)
    sid, _ = prepared_with_reps(client, [3.0, 0.3], headers=member)
    post(client, PATH, {"submissionId": sid})
    expected = [{"type": "TEMPO_TOO_FAST", "repNos": [3], "description": "빠른 구간 설명"}]

    preview = client.get(f"/submissions/{sid}/review-share-preview", headers=member).json()
    assert preview["summary"] == "요약 문장"
    assert preview["anomalies"] == expected
    assert client.get(f"/submissions/{sid}", headers=member).json()["status"] == "PREPARED"

    request_review(client, sid, member, leader_id)
    material = client.get(f"/review-requests/{sid}", headers=leader_headers).json()
    assert material["summary"] == "요약 문장"
    assert material["anomalies"] == expected
    assert material["status"] == "PENDING_REVIEW"  # L1·L2는 상태를 바꾸지 않음


def test_us07_api051_missing_submission_is_404(client, use_llm):
    use_llm(FakeLLM())
    assert post(client, PATH, {"submissionId": "00000000-0000-0000-0000-000000000000"}).status_code == 404


def test_us07_api051_default_mock_client_works(client):
    sid, _ = new_prepared(client)
    res = post(client, PATH, {"submissionId": sid})
    assert res.status_code == 200
    assert res.json()["summary"]
