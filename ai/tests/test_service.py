from typing import Any

import pytest
from fastapi.testclient import TestClient

from rep_engine.schemas import LivenessAction
from service.app import TOKEN_ENV, app
from tests.synth import SynthConfig, challenge, synth_frames, synth_session, varied_squats

TOKEN = "test-token"
H = {"X-Internal-Token": TOKEN}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    return TestClient(app)


def live_sc(**kw: Any) -> SynthConfig:
    base: dict[str, Any] = {
        "reps": varied_squats(8, seed=11),
        "lead_in_ms": 4000,
        "noise_px": 1.5,
        "hand_raises": [(500, 2000, "LEFT")],
        "liveness": challenge(LivenessAction.RAISE_LEFT_HAND, 0, 3000),
    }
    base.update(kw)
    return SynthConfig(**base)


def recount_body(sc: SynthConfig, client_count: int = 8, **extra: Any) -> dict[str, Any]:
    meta, chunks = synth_session(sc)
    body: dict[str, Any] = {
        "meta": meta.to_dict(),
        "chunks": [c.to_dict() for c in chunks],
        "client": {
            "clientRepCount": client_count,
            "reps": [],
            "aiConfidence": 0.95,
            "poseSummary": None,
        },
    }
    body.update(extra)
    return body


def assert_error(resp: Any, status: int, code: str) -> dict[str, Any]:
    assert resp.status_code == status, resp.text
    body: dict[str, Any] = resp.json()
    assert set(body) == {"code", "message", "details"} and body["code"] == code
    return body


def test_health_needs_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    r = TestClient(app).get("/internal/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["engineVersion"]
    assert "cat_2026-11-01" in body["catalogVersions"]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/internal/recount"),
        ("post", "/internal/liveness/evaluate"),
        ("post", "/internal/liveness/issue"),
    ],
)
def test_token_required(client: TestClient, method: str, path: str) -> None:
    assert_error(getattr(client, method)(path, json={}), 401, "UNAUTHORIZED")
    assert_error(
        getattr(client, method)(path, json={}, headers={"X-Internal-Token": "x"}),
        401,
        "UNAUTHORIZED",
    )


def test_unset_server_token_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    r = TestClient(app).post("/internal/liveness/issue", headers=H)
    assert_error(r, 401, "UNAUTHORIZED")


def test_recount_auto_approve_contract(client: TestClient) -> None:
    r = client.post("/internal/recount", json=recount_body(live_sc()), headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"result", "comparison", "decision"}
    res, cmp, dec = body["result"], body["comparison"], body["decision"]
    assert res["recognizedReps"] == 8 and res["liveness"]["status"] == "PASSED"
    assert {
        "engineVersion",
        "catalogVersion",
        "reps",
        "attemptedReps",
        "aiConfidence",
        "confidenceComponents",
        "poseSummary",
        "anomalies",
    } <= set(res)
    assert {"startT", "bottomT", "endT", "minKneeAngle", "invalidRatio"} <= set(res["reps"][0])
    assert cmp["finalRepCount"] == 8 and cmp["errorCode"] is None
    assert dec["decision"] == "AUTO_APPROVE" and dec["approvalPath"] == "AI_AUTO"


def test_recount_mismatch_is_200(client: TestClient) -> None:
    r = client.post("/internal/recount", json=recount_body(live_sc(), client_count=20), headers=H)
    assert r.status_code == 200
    assert r.json()["comparison"]["errorCode"] == "SERVER_RECOUNT_MISMATCH"
    assert r.json()["decision"]["decision"] == "HUMAN_REVIEW"


def test_recount_user_reduction(client: TestClient) -> None:
    ok = client.post(
        "/internal/recount", json=recount_body(live_sc(), userReducedCount=5), headers=H
    )
    assert ok.json()["comparison"]["finalRepCount"] == 5
    bad = client.post(
        "/internal/recount", json=recount_body(live_sc(), userReducedCount=9), headers=H
    )
    body = assert_error(bad, 400, "INVALID_REDUCTION")
    assert body["details"] == {"userReducedCount": 9, "serverRepCount": 8}


def test_recount_missing_chunks(client: TestClient) -> None:
    body = recount_body(live_sc())
    assert len(body["chunks"]) >= 3
    body["chunks"] = [c for c in body["chunks"] if c["seq"] != 1]
    err = assert_error(
        client.post("/internal/recount", json=body, headers=H), 400, "VALIDATION_FAILED"
    )
    assert err["details"]["missingSeq"] == [1]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["meta"]["device"].update(modelVersion="yolo-pose"),
        lambda b: b["meta"].update(catalogVersion="cat_1999-01-01"),
        lambda b: b["meta"].update(exerciseType="PUSHUP"),
        lambda b: b["meta"].pop("imageWidth"),
        lambda b: b["chunks"][0]["frames"][1].update(t=0),
        lambda b: b["chunks"][0]["frames"][0]["landmarks"].__setitem__(
            0, {"x": 0.5, "y": 0.1, "z": 0.0, "visibility": 0.9}
        ),  # 얼굴 좌표
        lambda b: b["meta"].update(image_width=720),  # snake_case 필드는 거부
    ],
)
def test_recount_validation_failed(client: TestClient, mutate: Any) -> None:
    body = recount_body(live_sc(reps=varied_squats(1)))
    mutate(body)
    assert_error(client.post("/internal/recount", json=body, headers=H), 400, "VALIDATION_FAILED")


def test_liveness_evaluate(client: TestClient) -> None:
    sc = live_sc(reps=[], lead_in_ms=3500, tail_ms=0)
    meta, _ = synth_session(sc)
    frames = [f.to_dict() for f in synth_frames(sc)]
    r = client.post(
        "/internal/liveness/evaluate", json={"meta": meta.to_dict(), "frames": frames}, headers=H
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "PASSED" and body["challengeId"] == "ch-1"
    assert set(body["evidence"]) == {
        "maxHoldMs",
        "wrongHandMaxHoldMs",
        "validFrameRatio",
        "wrongHandDetected",
    }
    no_ch = meta.to_dict() | {"liveness": None}
    r = client.post(
        "/internal/liveness/evaluate", json={"meta": no_ch, "frames": frames}, headers=H
    )
    assert_error(r, 400, "VALIDATION_FAILED")
    r = client.post(
        "/internal/liveness/evaluate",
        json={"meta": meta.to_dict(), "frames": frames[::-1]},
        headers=H,
    )
    assert_error(r, 400, "VALIDATION_FAILED")


def test_liveness_issue(client: TestClient) -> None:
    body = client.post("/internal/liveness/issue", headers=H).json()
    assert set(body) == {"action", "instruction", "challengeId"}
    assert body["action"] in {a.value for a in LivenessAction}


def test_config_error_is_500(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from rep_engine.errors import ConfigError
    from service import app as app_module

    def broken(_: str) -> None:
        raise ConfigError("카탈로그 깨짐")

    monkeypatch.setattr(app_module, "get_catalog", broken)
    r = client.post(
        "/internal/recount", json=recount_body(live_sc(reps=varied_squats(1))), headers=H
    )
    assert_error(r, 500, "CONFIG_ERROR")


def test_request_timing_is_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO", logger="ai.service"):
        client.get("/internal/health")
    assert any("/internal/health" in m and "ms" in m for m in caplog.messages)


def test_ten_minute_recount_via_api(client: TestClient) -> None:
    """10분 세션(9000프레임 이상)을 API로 끝까지 처리한다. 시간 기준(1초)은
    test_session.py의 재계산 성능 테스트에서 확인한다 (JSON 파싱 시간은 DECISIONS D-44)."""
    sc = SynthConfig(reps=varied_squats(200, seed=1), noise_px=1.5, model="movenet")
    r = client.post("/internal/recount", json=recount_body(sc, client_count=200), headers=H)
    assert r.status_code == 200 and r.json()["result"]["recognizedReps"] == 200
