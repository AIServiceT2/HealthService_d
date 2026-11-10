"""API-034 확인 요청 공유 내용 미리보기 — backlog US-07 (정상) 2번째: 보내기 전에 보낼 내용의 미리보기."""

from tests.character_helpers import new_player
from tests.review_helpers import auto_approval, new_prepared
from tests.submission_helpers import new_submission


def preview(client, sid, headers):
    return client.get(f"/submissions/{sid}/review-share-preview", headers=headers)


def test_us07_api034_owner_sees_share_content_for_low_confidence(client):
    sid, headers = new_prepared(client, confidence=0.82)

    res = preview(client, sid, headers)

    assert res.status_code == 200
    # 관절 선 리플레이·L1·L2·통증 안내는 아직 없어 빈 값 (service.ShareContent)
    assert res.json() == {"skeletonReplayUrl": None, "summary": None, "anomalies": [], "painNotice": None}


def test_us07_api034_does_not_expose_face_age_or_guild(client):
    sid, headers = new_prepared(client, confidence=0.82)
    body = preview(client, sid, headers).json()
    for key in body:
        assert not any(word in key.lower() for word in ("face", "birth", "age", "guild"))


def test_us07_api034_only_owner(client):
    sid, _ = new_prepared(client, confidence=0.82)
    _, other = new_player(client)

    res = preview(client, sid, other)

    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN"


def test_us07_api034_rejects_auto_approvable_submission(client):
    sid, headers = new_prepared(client, confidence=0.94, liveness=True)

    res = preview(client, sid, headers)

    assert res.status_code == 409
    assert res.json()["code"] == "INVALID_STATE"


def test_us07_api034_rejects_approved_and_submitted(client):
    approved, headers = new_prepared(client, confidence=0.94, liveness=True)
    auto_approval(client, approved)
    submitted, submitted_headers = new_submission(client)

    assert preview(client, approved, headers).status_code == 409
    assert preview(client, submitted, submitted_headers).status_code == 409


def test_us07_api034_missing_liveness_is_reviewable_even_with_high_confidence(client):
    sid, headers = new_prepared(client, confidence=0.99, liveness=False)
    assert preview(client, sid, headers).status_code == 200
