"""API-048 전투 리플레이 조회 — 노션 '전운시 API 명세서' API-048, backlog US-05.

렙 시각은 테스트에서 DB로 정해 둔다 (세션 시작 + 간격). t는 첫 렙부터의 초이고(첫 렙 0초),
30초를 넘으면 비율을 유지해 줄인다 (제안).
"""

import uuid
from datetime import timedelta

from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.models import DailyCapReservation, RepEvent, WorkoutSubmission
from tests.battle_helpers import rewarded
from tests.character_helpers import new_player
from tests.reward_helpers import approved_submission, grant
from tests.submission_helpers import new_submission, prepare, submit_body


def _replay(client, submission_id, headers):
    return client.get(f"/submissions/{submission_id}/replay", headers=headers)


def _space_reps(db, submission_id, seconds):
    """렙 i(1부터)의 시각을 세션 시작 + i × seconds초로 둔다."""
    submission = db.get(WorkoutSubmission, uuid.UUID(submission_id))
    for rep in db.query(RepEvent).filter_by(submission_id=submission.id):
        rep.ts = submission.started_at + timedelta(seconds=rep.rep_no * seconds)
    db.commit()


def _rewarded_with(client, db, *, counted=30, uncounted=0, reserved=None):
    """counted개 인정·uncounted개 미인정, 예약량 reserved로 지급까지 마친 건."""
    from tests.submission_helpers import start_session, submit, upload_chunks

    _, headers = new_player(client)
    session_id = start_session(client, headers)
    upload_chunks(client, headers, session_id)
    submission_id = submit(client, headers, session_id, submit_body(counted=counted, uncounted=uncounted)).json()[
        "submissionId"
    ]
    if reserved is not None:
        db.get(DailyCapReservation, uuid.UUID(submission_id)).amount = reserved
        db.commit()
    client.post("/characters", json={}, headers=headers)
    prepare(client, submission_id)
    db.get(WorkoutSubmission, uuid.UUID(submission_id)).status = "APPROVED"
    db.commit()
    assert grant(client, submission_id).status_code == 200
    return submission_id, headers


def test_us05_replay_combo_equals_hit_count_and_fits_30s(client, db):
    """(정상) 리플레이 콤보 수 = 결과 카드 타격 수 (30렙 → 30 COMBO), 30초를 넘지 않는다."""
    submission_id, headers = rewarded(client, db, counted=30)
    _space_reps(db, submission_id, 10)  # 실제로는 10초마다 → 300초

    res = _replay(client, submission_id, headers)

    assert res.status_code == 200
    body = res.json()
    hits = [e for e in body["events"] if e["type"] == "HIT"]
    card = client.get(f"/submissions/{submission_id}/result", headers=headers).json()["card"]
    assert body["hitCount"] == len(hits) == card["hitCount"] == 30
    assert sum(e["damage"] for e in hits) == card["totalDamage"] == 900
    times = [e["t"] for e in body["events"]]
    assert times == sorted(times)
    assert times[0] == 0.0  # 첫 렙 기준
    assert times[1] == 1.0  # 10초 × (30/290), 소수 첫째 자리 반올림
    assert times[-1] == 30.0
    assert body["skeletonUrl"] is None


def test_us05_short_session_keeps_real_seconds(client, db):
    submission_id, headers = rewarded(client, db, counted=5)
    _space_reps(db, submission_id, 2)  # 2·4·6·8·10초

    times = [e["t"] for e in _replay(client, submission_id, headers).json()["events"]]

    assert times == [0.0, 2.0, 4.0, 6.0, 8.0]  # 첫 렙 기준, 30초 안이라 줄이지 않음


def test_us05_replay_times_do_not_depend_on_phone_clock(client, db):
    """앱 시계가 서버보다 5분 느리거나 빨라도 렙 사이 간격이 그대로다 (검토에서 재현한 문제의 회귀 테스트).

    렙 시각은 앱 시계, 세션 시작은 서버 시계라 둘을 빼던 때는 느리면 모두 0초, 빠르면 30초 끝으로 몰렸다.
    """
    results = []
    for skew in (timedelta(0), timedelta(minutes=-5), timedelta(minutes=5)):
        submission_id, headers = rewarded(client, db, counted=5)
        submission = db.get(WorkoutSubmission, uuid.UUID(submission_id))
        for rep in db.query(RepEvent).filter_by(submission_id=submission.id):
            rep.ts = submission.started_at + skew + timedelta(seconds=3 * rep.rep_no)
        db.commit()
        results.append([e["t"] for e in _replay(client, submission_id, headers).json()["events"]])

    assert results == [[0.0, 3.0, 6.0, 9.0, 12.0]] * 3


def test_us05_uncounted_reps_are_miss(client, db):
    submission_id, headers = _rewarded_with(client, db, counted=3, uncounted=2)

    events = _replay(client, submission_id, headers).json()["events"]

    assert [(e["repIndex"], e["type"]) for e in events] == [(1, "HIT"), (2, "HIT"), (3, "HIT"), (4, "MISS"), (5, "MISS")]
    assert events[3]["reason"] is None  # 미인정 사유는 저장되지 않음
    assert events[3]["damage"] is None


def test_us05_reps_over_daily_cap_are_miss_daily_cap(client, db):
    """상한이 20회만 남아 20타면, 인정된 나머지 10렙은 MISS(DAILY_CAP). 콤보 수는 타격 수와 같다."""
    submission_id, headers = _rewarded_with(client, db, counted=30, reserved=20)

    body = _replay(client, submission_id, headers).json()

    assert body["hitCount"] == 20
    assert [e["type"] for e in body["events"]] == ["HIT"] * 20 + ["MISS"] * 10
    assert {e["reason"] for e in body["events"][20:]} == {"DAILY_CAP"}
    assert sum(e["damage"] for e in body["events"][:20]) == 600


def test_us05_damage_remainder_goes_to_last_hit(client, db):
    submission_id, headers = rewarded(client, db, counted=3)
    db.get(SubmissionSnapshot, uuid.UUID(submission_id)).total_damage = 100  # 100 ÷ 3
    db.commit()

    damages = [e["damage"] for e in _replay(client, submission_id, headers).json()["events"]]

    assert damages == [33, 33, 34]


def test_us05_daily_cap_exceeded_has_no_replay(client, db):
    """(실패·거절) 일일 상한 초과로 타격 0이면 리플레이 없이 409 (결과 카드는 dailyCapExceeded)."""
    submission_id, headers = _rewarded_with(client, db, counted=30, reserved=0)

    res = _replay(client, submission_id, headers)

    assert res.status_code == 409
    assert res.json()["details"]["reason"] == "DAILY_CAP_EXCEEDED"
    assert client.get(f"/submissions/{submission_id}/result", headers=headers).json()["card"]["dailyCapExceeded"]


def test_us05_not_rewarded_cannot_open_replay(client, db):
    """(실패·거절) REWARDED가 아닌 건(PREPARED, CANCELED 등)은 리플레이를 열 수 없다."""
    prepared_id, prepared_headers = new_submission(client)
    prepare(client, prepared_id)
    canceled_id, canceled_headers = new_submission(client)
    client.post(f"/submissions/{canceled_id}/cancel", json={}, headers=canceled_headers | {"If-Match": "0"})
    approved_id, approved_headers = approved_submission(client, db)

    for submission_id, headers in (
        (prepared_id, prepared_headers),
        (canceled_id, canceled_headers),
        (approved_id, approved_headers),
    ):
        res = _replay(client, submission_id, headers)
        assert res.status_code == 409, submission_id
        assert res.json()["code"] == "INVALID_STATE"


def test_us05_replay_only_for_owner(client, db):
    """(권한) 리플레이는 본인에게만 보인다."""
    submission_id, _ = rewarded(client, db)
    _, other = new_player(client)

    res = _replay(client, submission_id, other)

    assert res.status_code == 403
    assert _replay(client, uuid.uuid4(), other).status_code == 404
    assert client.get(f"/submissions/{submission_id}/replay").status_code == 401
