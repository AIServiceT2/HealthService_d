"""API-071 음성 안내 멘트 목록 — 노션 '전운시 API 명세서' API-071, 기능명세 JN-039 (US-01 연계, 별도 스토리 없음).

기대값은 노션 API-071의 요청·응답·Error Code에 적힌 것만 검사한다. 카운트 최대 횟수·멘트 문구는 미정(가안)이라
값 자체는 검사하지 않고, 노션 예시에 있는 코드·문구만 확인한다.
"""

import uuid

from app.modules.workout_session import voice_cues
from tests.character_helpers import new_player


def _cues(client, headers, **params):
    return client.get("/voice-cues", headers=headers, params=params)


def test_us01_api071_without_token_is_401(client):
    res = client.get("/voice-cues")

    assert res.status_code == 401
    assert res.json()["code"] == "UNAUTHENTICATED"


def test_us01_api071_without_exercise_returns_common_cues_only(client):
    _, headers = new_player(client)

    res = _cues(client, headers)

    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["version"], str) and body["version"]
    cues = body["cues"]
    assert all(c["exerciseCode"] is None for c in cues)
    by_code = {c["code"]: c for c in cues}
    assert by_code["COUNT_1"] == {
        "code": "COUNT_1",
        "type": "COUNT",
        "exerciseCode": None,
        "number": 1,
        "reasonCode": None,
        "text": "하나",
        "audioUrl": None,
    }
    assert by_code["SET_DONE"]["type"] == "SET_DONE"
    assert by_code["WORKOUT_DONE"]["type"] == "WORKOUT_DONE"
    assert not any(c["type"] == "FORM" for c in cues)


def test_us01_api071_squat_adds_form_cues_for_engine_reasons(client):
    _, headers = new_player(client)

    res = _cues(client, headers, exerciseCode="SQUAT")

    assert res.status_code == 200
    cues = res.json()["cues"]
    form = [c for c in cues if c["type"] == "FORM"]
    # 사유 코드는 렙 판정 엔진과 같다 (ai/README.md)
    assert {c["reasonCode"] for c in form} == {"OUT_OF_FRAME", "TOO_FAST", "SHALLOW_DEPTH"}
    assert all(c["exerciseCode"] == "SQUAT" for c in form)
    shallow = next(c for c in form if c["reasonCode"] == "SHALLOW_DEPTH")
    assert shallow["code"] == "FORM_SQUAT_SHALLOW_DEPTH"
    assert shallow["text"] == "조금 더 앉아 주세요"
    # 공통 멘트도 함께 온다
    assert {"COUNT_1", "SET_DONE", "WORKOUT_DONE"} <= {c["code"] for c in cues}


def test_us01_api071_audio_url_is_null_before_recording(client, tmp_path, monkeypatch):
    monkeypatch.setattr(voice_cues, "VOICE_DIR", tmp_path)  # 녹음 파일이 하나도 없는 폴더
    _, headers = new_player(client)

    cues = _cues(client, headers, exerciseCode="SQUAT").json()["cues"]

    assert all(c["audioUrl"] is None for c in cues)


def test_us01_api071_unknown_exercise_is_400(client):
    _, headers = new_player(client)

    res = _cues(client, headers, exerciseCode="NOT_AN_EXERCISE")

    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_us01_api071_recorded_file_fills_audio_url(client, tmp_path, monkeypatch):
    # 녹음 파일을 멘트 코드 이름으로 넣으면 그 멘트만 audioUrl이 채워진다 (backend/static/voice/README.md)
    (tmp_path / "SET_DONE.m4a").write_bytes(b"fake-audio")
    (tmp_path / "COUNT_1.mp3").write_bytes(b"fake-audio")
    monkeypatch.setattr(voice_cues, "VOICE_DIR", tmp_path)
    _, headers = new_player(client)

    by_code = {c["code"]: c for c in _cues(client, headers).json()["cues"]}

    assert by_code["SET_DONE"]["audioUrl"].endswith("/static/voice/SET_DONE.m4a")
    assert by_code["COUNT_1"]["audioUrl"].endswith("/static/voice/COUNT_1.mp3")
    assert by_code["COUNT_2"]["audioUrl"] is None


def test_us01_api071_static_voice_file_is_served(client):
    # 실제 녹음 파일과 겹치지 않는 이름으로 잠깐 넣었다가 지운다
    name = f"__test_{uuid.uuid4().hex}.m4a"
    path = voice_cues.VOICE_DIR / name
    path.write_bytes(b"fake-audio")
    try:
        res = client.get(f"/static/voice/{name}")
    finally:
        path.unlink()

    assert res.status_code == 200
    assert res.content == b"fake-audio"
