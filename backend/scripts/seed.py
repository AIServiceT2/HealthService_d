"""US-02 화면·수동 확인용 시드. 실행: backend/에서 `python -m scripts.seed`

테이블을 만들고(마이그레이션 도구는 미정), 시드 사용자 1명과 SUBMITTED 스쿼트 30회 제출건 1건을 넣는다.
제출건에 사용자·세션이 필수가 되어(노션 API-026) 사용자·세션도 함께 만든다.
비밀번호는 실제 값이 아닌 시드 전용 예시 값이다.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from app.core.db import Base, SessionLocal, engine
from app.main import app  # noqa: F401  모든 모델을 등록한다
from app.modules.auth.models import User
from app.modules.auth.service import hash_password
from app.modules.submission.constants import EXERCISE_SQUAT, SubmissionStatus
from app.modules.submission.models import DailyCapReservation, WorkoutSubmission
from app.modules.workout_session.models import SessionStatus, WorkoutSession


def main() -> None:
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    with SessionLocal() as db:
        user = User(
            email=f"seed-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("example-password"),
            nickname="시드플레이어",
            birth_date=date(2010, 3, 14),
        )
        db.add(user)
        db.flush()
        session = WorkoutSession(
            user_id=user.id,
            exercise_code=EXERCISE_SQUAT,
            status=SessionStatus.SUBMITTED,
            liveness_action="RAISE_LEFT_HAND",
            liveness_issued_at=now - timedelta(minutes=10),
            started_at=now - timedelta(minutes=10),
        )
        db.add(session)
        db.flush()
        submission = WorkoutSubmission(
            user_id=user.id,
            session_id=session.id,
            idempotency_key=uuid.uuid4(),
            exercise_code=EXERCISE_SQUAT,
            status=SubmissionStatus.SUBMITTED,
            started_at=session.started_at,
            ended_at=now,
            counted_reps=30,
            version=0,
            confidence=0.94,
        )
        db.add(submission)
        db.flush()
        db.add(DailyCapReservation(submission_id=submission.id, amount=30))
        db.commit()
        print(f"seeded user email={user.email} (password: example-password)")
        print(f"seeded SUBMITTED submission id={submission.id}")


if __name__ == "__main__":
    main()
