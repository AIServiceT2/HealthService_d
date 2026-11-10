"""지급 규칙. 다른 모듈은 이 파일의 함수로만 지급 내역·아이템을 다룬다."""

import base64
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.orm import Session

from app.modules.character.models import Character
from app.modules.reward.models import Item, ItemStatus, RewardLedger
from app.modules.reward.rules import PROTECTION_PERIOD
from app.modules.snapshot.models import SubmissionSnapshot
from app.modules.submission.constants import SubmissionStatus
from app.modules.submission.models import WorkoutSubmission
from app.modules.workout_session.models import WorkoutSession


class SubmissionNotFound(Exception):
    pass


class NotApproved(Exception):
    pass


class AlreadyRewarded(Exception):
    """다른 요청(다른 Idempotency-Key)으로 이미 지급된 건."""


class NoCharacter(Exception):
    pass


@dataclass(frozen=True)
class Damage:
    # 데모 공략 대상(던전/보스)이 미정이라 세션에 고른 대상을 그대로 둔다 (없으면 None)
    target_type: str | None
    target_id: uuid.UUID | None
    amount: int


@dataclass(frozen=True)
class GrantResult:
    submission_id: uuid.UUID
    already_granted: bool
    exp: int
    items: list[Item]
    damage: Damage
    rewarded_at: datetime


def _result(db: Session, submission: WorkoutSubmission, ledger: RewardLedger, already: bool) -> GrantResult:
    """지급 결과는 스냅샷·아이템·세션에서 다시 구한다 (다시 불러도 같은 값)."""
    snapshot = db.get(SubmissionSnapshot, submission.id)
    session = db.get(WorkoutSession, submission.session_id)
    items = list(db.scalars(select(Item).where(Item.submission_id == submission.id).order_by(Item.id)))
    return GrantResult(
        submission_id=submission.id,
        already_granted=already,
        exp=snapshot.exp,
        items=items,
        damage=Damage(session.target_type, session.target_id, snapshot.total_damage),
        rewarded_at=ledger.rewarded_at,
    )


def grant(db: Session, submission_id: uuid.UUID, idempotency_key: uuid.UUID) -> GrantResult:
    """스냅샷 값만큼 경험치·아이템을 한 트랜잭션으로 반영하고 APPROVED → REWARDED (노션 API-041, US-04).

    - 이미 지급된 건: 같은 Idempotency-Key면 첫 결과(alreadyGranted=true), 다르면 AlreadyRewarded
    - APPROVED가 아니면 NotApproved, 캐릭터가 없으면 NoCharacter (APPROVED에 남아 다시 호출 가능)
    - 중간에 실패하면 아무것도 반영되지 않는다 (한 트랜잭션)
    - 피해는 던전·보스 모델이 없어 어디에도 깎지 않고 결과에만 담는다 [임시, battle API-045·046 이후]
    - 능력치 경험치는 능력치 모델이 미정이라 반영하지 않는다 (노션 API-041)
    """
    try:
        submission = db.scalars(
            select(WorkoutSubmission)
            .where(WorkoutSubmission.id == submission_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one_or_none()
        if submission is None:
            raise SubmissionNotFound(str(submission_id))
        ledger = db.get(RewardLedger, submission_id)
        if ledger is not None:
            if ledger.idempotency_key != idempotency_key:
                raise AlreadyRewarded(str(submission_id))
            result = _result(db, submission, ledger, already=True)
            db.rollback()
            return result
        if submission.status != SubmissionStatus.APPROVED:
            raise NotApproved(submission.status)
        snapshot = db.get(SubmissionSnapshot, submission_id)

        # 경험치는 원자적으로 더한다 (같은 캐릭터에 지급이 동시에 와도 덮어쓰지 않음)
        updated = db.execute(
            update(Character)
            .where(Character.user_id == submission.user_id)
            .values(exp=Character.exp + snapshot.exp)
        )
        if updated.rowcount == 0:
            raise NoCharacter(str(submission.user_id))

        ledger = RewardLedger(
            submission_id=submission_id,
            idempotency_key=idempotency_key,
            rewarded_at=datetime.now(UTC),
        )
        db.add(ledger)
        db.add_all(
            Item(user_id=submission.user_id, submission_id=submission_id, status=ItemStatus.LOCKED)
            for _ in range(snapshot.drop_count)
        )
        submission.status = SubmissionStatus.REWARDED
        submission.version += 1
        db.flush()
        result = _result(db, submission, ledger, already=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


# ---- 24시간 잠금 해제 (노션 API-042) ----


@dataclass(frozen=True)
class ReleaseResult:
    released_items: int
    confirmed_stats: int


def release_locks(db: Session, now: datetime | None = None) -> ReleaseResult:
    """지급 뒤 24시간이 지난 LOCKED 아이템을 UNLOCKED로 바꾼다 (노션 API-042).

    - 경계: rewarded_at + 24시간 '이후'(같은 시각 포함)부터 해제 [제안 — 명세 '24시간 경계 처리 미정']
    - UPDATE 한 문장이라 배치가 동시에 두 번 돌아도 같은 아이템을 두 번 세지 않는다
    - 능력치 확정은 능력치 모델이 미정이라 0. 캐릭터 경험치의 '확정 대기'는 시간으로 계산하므로
      (pending_exp) 배치가 바꿀 것이 없다
    """
    now = now or datetime.now(UTC)
    unlockable = select(RewardLedger.submission_id).where(
        RewardLedger.rewarded_at <= now - PROTECTION_PERIOD
    )
    try:
        result = db.execute(
            update(Item)
            .where(Item.status == ItemStatus.LOCKED, Item.submission_id.in_(unlockable))
            .values(status=ItemStatus.UNLOCKED)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return ReleaseResult(released_items=result.rowcount, confirmed_stats=0)


# ---- 아이템 잠금 상태 (API-007·043·044·047 공통) ----


def item_status(item: Item, rewarded_at: datetime, now: datetime | None = None) -> str:
    """보여 줄 아이템 상태. 지급 뒤 24시간이 지났으면 해제 배치(API-042)를 아직 안 돌렸어도 UNLOCKED.

    경험치 '확정 대기'(pending_exp_subquery)도 시각으로 계산하므로, 아이템도 같은 기준으로 보여 줘야
    배치를 돌리기 전에 경험치는 확정·아이템은 잠김으로 어긋나지 않는다 (backlog US-04 (정상) 2번째).
    경계는 release_locks와 같다(지급 + 24시간 '이후', 같은 시각 포함).
    """
    now = now or datetime.now(UTC)
    if item.status == ItemStatus.UNLOCKED or rewarded_at <= now - PROTECTION_PERIOD:
        return ItemStatus.UNLOCKED
    return ItemStatus.LOCKED


# ---- 내 지급 내역 (노션 API-043) ----


class InvalidCursor(Exception):
    pass


@dataclass(frozen=True)
class RewardEntry:
    submission_id: uuid.UUID
    exp: int
    items: list[Item]
    damage: int
    rewarded_at: datetime

    @property
    def protection_ends_at(self) -> datetime:
        return self.rewarded_at + PROTECTION_PERIOD


@dataclass(frozen=True)
class RewardPage:
    items: list[RewardEntry]
    next_cursor: str | None


# 커서: 마지막 항목의 (rewarded_at, submission_id)를 base64url로 감싼 값
def _encode_cursor(entry: RewardEntry) -> str:
    raw = f"{entry.rewarded_at.isoformat()}|{entry.submission_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        at_text, id_text = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        at = datetime.fromisoformat(at_text)
        if at.tzinfo is None:
            raise ValueError(at_text)
        return at, uuid.UUID(id_text)
    except ValueError:
        raise InvalidCursor(cursor) from None


def list_my_rewards(db: Session, user_id: uuid.UUID, cursor: str | None, limit: int) -> RewardPage:
    """본인 지급 내역만, 최신 지급순(rewarded_at 내림차순, 같으면 제출 ID) (노션 API-043).

    수치는 스냅샷 값이다 (지급 내역에는 시각만 저장, 노션 DB 11절). 정렬은 명세에 없어 최신순 [제안].
    """
    query = (
        select(RewardLedger, SubmissionSnapshot)
        .join(WorkoutSubmission, WorkoutSubmission.id == RewardLedger.submission_id)
        .join(SubmissionSnapshot, SubmissionSnapshot.submission_id == RewardLedger.submission_id)
        .where(WorkoutSubmission.user_id == user_id)
    )
    if cursor is not None:
        after_at, after_id = _decode_cursor(cursor)
        query = query.where(
            tuple_(RewardLedger.rewarded_at, RewardLedger.submission_id) < tuple_(after_at, after_id)
        )
    rows = db.execute(
        query.order_by(RewardLedger.rewarded_at.desc(), RewardLedger.submission_id.desc()).limit(limit + 1)
    ).all()
    page, more = rows[:limit], len(rows) > limit

    ids = [ledger.submission_id for ledger, _ in page]
    items_by_submission: dict[uuid.UUID, list[Item]] = {i: [] for i in ids}
    if ids:
        for item in db.scalars(select(Item).where(Item.submission_id.in_(ids)).order_by(Item.id)):
            items_by_submission[item.submission_id].append(item)
    entries = [
        RewardEntry(
            submission_id=ledger.submission_id,
            exp=snapshot.exp,
            items=items_by_submission[ledger.submission_id],
            damage=snapshot.total_damage,
            rewarded_at=ledger.rewarded_at,
        )
        for ledger, snapshot in page
    ]
    return RewardPage(entries, _encode_cursor(entries[-1]) if more else None)


# ---- 인벤토리 (노션 API-044) ----


@dataclass(frozen=True)
class InventoryItem:
    item: Item
    unlock_at: datetime
    status: str


def my_inventory(db: Session, user_id: uuid.UUID) -> list[InventoryItem]:
    """본인 아이템 전부 (노션 API-044). 명세에 페이지 나눔이 없어 한 번에 돌려준다.

    unlockAt = 지급 시각 + 24시간. 정렬은 명세에 없어 최신 지급순 [제안].
    아이템 카탈로그(종류·이름)는 미정이라 아직 없다.
    """
    rows = db.execute(
        select(Item, RewardLedger.rewarded_at)
        .join(RewardLedger, RewardLedger.submission_id == Item.submission_id)
        .where(Item.user_id == user_id)
        .order_by(RewardLedger.rewarded_at.desc(), Item.submission_id.desc(), Item.id)
    ).all()
    now = datetime.now(UTC)
    return [
        InventoryItem(item, rewarded_at + PROTECTION_PERIOD, item_status(item, rewarded_at, now))
        for item, rewarded_at in rows
    ]


# ---- 다른 모듈용 (API-007 내 캐릭터·성장 조회) ----
# 캐릭터 조회가 경험치와 같은 SQL 한 문장에 넣을 수 있게 '값'이 아니라 스칼라 하위 쿼리로 돌려준다.
# 따로 읽으면 그 사이에 지급이 커밋될 때 confirmed(= exp - pending)가 음수가 된다 (검토에서 재현).


def pending_exp_subquery(user_id: uuid.UUID, now: datetime | None = None):
    """지급 뒤 보호 기간(24시간)이 아직 안 지난 경험치 합계 = '확정 대기' 경험치."""
    now = now or datetime.now(UTC)
    return (
        select(func.coalesce(func.sum(SubmissionSnapshot.exp), 0))
        .join(RewardLedger, RewardLedger.submission_id == SubmissionSnapshot.submission_id)
        .join(WorkoutSubmission, WorkoutSubmission.id == SubmissionSnapshot.submission_id)
        .where(
            WorkoutSubmission.user_id == user_id,
            RewardLedger.rewarded_at > now - PROTECTION_PERIOD,
        )
        .scalar_subquery()
    )


def locked_item_count_subquery(user_id: uuid.UUID, now: datetime | None = None):
    """잠긴 아이템 수. 지급 뒤 24시간이 안 지났고 아직 해제되지 않은 것만 센다 (item_status와 같은 기준)."""
    now = now or datetime.now(UTC)
    return (
        select(func.count())
        .select_from(Item)
        .join(RewardLedger, RewardLedger.submission_id == Item.submission_id)
        .where(
            Item.user_id == user_id,
            Item.status == ItemStatus.LOCKED,
            RewardLedger.rewarded_at > now - PROTECTION_PERIOD,
        )
        .scalar_subquery()
    )
