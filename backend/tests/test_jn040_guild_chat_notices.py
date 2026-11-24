"""길드 채팅 자동 알림 — 기능명세 JN-040, 노션 API-041·046 메모 (2026-11-24 저장소에서 추가, 별도 스토리 없음).

- WORKOUT_DONE: 지급 완료 때 길드원이고 타격 수가 1 이상이면 1개. payload는 운동 종류·타격 수·공략 대상 종류만
- BOSS_DEFEATED: 주간 보스 피해 합계가 최대 체력 이상이 된 지급에서 길드·주마다 1개
- BOSS_WEEK_STARTED: 그 주 보스가 처음 생길 때 1개
- 알림을 만들지 못해도 지급은 되돌리지 않는다
"""

import uuid

from sqlalchemy import func, select

from app.modules.battle.models import GuildBoss
from app.modules.guild_chat import service as guild_chat_service
from app.modules.guild_chat.models import GuildChatMessage
from app.modules.submission.models import WorkoutSubmission
from tests.battle_helpers import rewarded
from tests.guild_helpers import join_with_code, new_guild
from tests.reward_helpers import approved_submission, grant


def _items(client, guild_id, headers, type_=None):
    items = client.get(f"/guilds/{guild_id}/chat/messages", headers=headers, params={"limit": 50}).json()["items"]
    return [m for m in items if type_ is None or m["type"] == type_]


def _boss(client, guild_id, headers) -> uuid.UUID:
    res = client.get(f"/guilds/{guild_id}/boss", headers=headers)
    assert res.status_code == 200, res.json()
    return uuid.UUID(res.json()["bossId"])


def _count(db, type_) -> int:
    return db.scalar(select(func.count()).select_from(GuildChatMessage).where(GuildChatMessage.type == type_))


# ---- WORKOUT_DONE ----


def test_jn040_workout_done_after_grant(client, db):
    guild_id, leader_id, leader = new_guild(client)

    rewarded(client, db, headers=leader)

    [notice] = _items(client, guild_id, leader, "WORKOUT_DONE")
    assert notice["sender"] == {"userId": str(leader_id), "nickname": "플레이어"}
    assert notice["body"] is None
    assert notice["payload"] == {"exerciseCode": "SQUAT", "hitCount": 30, "targetType": None}


def test_jn040_workout_done_has_target_type_only(client, db):
    guild_id, _, leader = new_guild(client)
    boss_id = _boss(client, guild_id, leader)

    rewarded(client, db, target=("BOSS", boss_id), headers=leader)

    [notice] = _items(client, guild_id, leader, "WORKOUT_DONE")
    # 경험치·피해량·확신도·아이템·대상 ID는 넣지 않는다
    assert notice["payload"] == {"exerciseCode": "SQUAT", "hitCount": 30, "targetType": "BOSS"}


def test_jn040_workout_done_is_seen_by_other_member(client, db):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)

    rewarded(client, db, headers=member)

    assert len(_items(client, guild_id, leader, "WORKOUT_DONE")) == 1


def test_jn040_workout_done_pushed_over_websocket(client, db):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)

    with client.websocket_connect(f"/guilds/{guild_id}/chat/ws") as ws:
        ws.send_json({"type": "AUTH", "accessToken": leader["Authorization"].removeprefix("Bearer ")})
        assert ws.receive_json()["type"] == "READY"
        rewarded(client, db, headers=member)

        event = ws.receive_json()

    assert event["type"] == "MESSAGE_CREATED"
    assert event["message"]["type"] == "WORKOUT_DONE"


def test_jn040_no_workout_done_without_guild(client, db):
    rewarded(client, db)

    assert _count(db, "WORKOUT_DONE") == 0


def test_jn040_no_workout_done_when_hit_count_is_zero(client, db):
    guild_id, _, leader = new_guild(client)

    rewarded(client, db, headers=leader, counted=0)

    assert _items(client, guild_id, leader, "WORKOUT_DONE") == []


def test_jn040_same_grant_request_twice_posts_once(client, db):
    guild_id, _, leader = new_guild(client)
    submission_id, _ = approved_submission(client, db, headers=leader)
    key = str(uuid.uuid4())

    assert grant(client, submission_id, key).status_code == 200
    assert grant(client, submission_id, key).json()["alreadyGranted"] is True

    assert len(_items(client, guild_id, leader, "WORKOUT_DONE")) == 1


def test_jn040_notice_failure_does_not_undo_grant(client, db, monkeypatch):
    guild_id, _, leader = new_guild(client)
    submission_id, _ = approved_submission(client, db, headers=leader)

    def broken(*_args, **_kwargs):
        raise RuntimeError("알림 저장 실패")

    monkeypatch.setattr(guild_chat_service, "post_workout_done", broken)

    res = grant(client, submission_id)

    assert res.status_code == 200
    assert res.json()["alreadyGranted"] is False
    assert db.get(WorkoutSubmission, uuid.UUID(submission_id)).status == "REWARDED"
    assert _items(client, guild_id, leader, "WORKOUT_DONE") == []


# ---- BOSS_WEEK_STARTED ----


def test_jn040_boss_week_started_once_when_boss_is_created(client, db):
    guild_id, _, leader = new_guild(client)

    _boss(client, guild_id, leader)
    _boss(client, guild_id, leader)

    [notice] = _items(client, guild_id, leader, "BOSS_WEEK_STARTED")
    boss = db.scalars(select(GuildBoss).where(GuildBoss.guild_id == guild_id)).one()
    assert notice["sender"] is None
    assert notice["payload"] == {"weekStart": boss.week_start.isoformat(), "hpMax": boss.hp_max}


def test_jn040_boss_notice_failure_does_not_break_boss_lookup(client, db, monkeypatch):
    guild_id, _, leader = new_guild(client)

    def broken(*_args, **_kwargs):
        raise RuntimeError("알림 저장 실패")

    monkeypatch.setattr(guild_chat_service, "post_boss_notice", broken)

    res = client.get(f"/guilds/{guild_id}/boss", headers=leader)

    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"


# ---- BOSS_DEFEATED ----


def _weak_boss(client, db, guild_id, headers, hp_max) -> uuid.UUID:
    boss_id = _boss(client, guild_id, headers)
    db.get(GuildBoss, boss_id).hp_max = hp_max
    db.commit()
    return boss_id


def test_jn040_boss_defeated_when_hp_reaches_zero(client, db):
    guild_id, _, leader = new_guild(client)
    _, member = join_with_code(client, guild_id, leader)
    # 스쿼트 30회 = 피해 900 (가안). 두 번째 지급에서 1800 ≥ 1000
    boss_id = _weak_boss(client, db, guild_id, leader, hp_max=1000)

    rewarded(client, db, target=("BOSS", boss_id), headers=leader)
    assert _items(client, guild_id, leader, "BOSS_DEFEATED") == []

    rewarded(client, db, target=("BOSS", boss_id), headers=member)

    [notice] = _items(client, guild_id, leader, "BOSS_DEFEATED")
    assert notice["sender"] is None
    assert notice["payload"]["hpMax"] == 1000
    assert client.get(f"/guilds/{guild_id}/boss", headers=leader).json()["status"] == "DEFEATED"


def test_jn040_boss_defeated_only_once_per_week(client, db):
    guild_id, _, leader = new_guild(client)
    boss_id = _weak_boss(client, db, guild_id, leader, hp_max=500)

    rewarded(client, db, target=("BOSS", boss_id), headers=leader)
    rewarded(client, db, target=("BOSS", boss_id), headers=leader)

    assert len(_items(client, guild_id, leader, "BOSS_DEFEATED")) == 1


def test_jn040_dungeon_target_does_not_post_boss_defeated(client, db):
    from app.modules.battle.catalog import DEMO_DUNGEON_ID

    guild_id, _, leader = new_guild(client)

    rewarded(client, db, target=("DUNGEON", DEMO_DUNGEON_ID), headers=leader)

    assert _items(client, guild_id, leader, "BOSS_DEFEATED") == []
