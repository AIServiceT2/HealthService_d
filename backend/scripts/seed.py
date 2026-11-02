"""US-02 화면·수동 확인용 시드. 실행: backend/에서 `python -m scripts.seed`

테이블을 만들고(마이그레이션 도구는 미정), SUBMITTED 스쿼트 30회 제출건 1건을 넣는다.
DATA-MODEL.md 시드에는 SUBMITTED 건이 없어 계산 시험용으로 추가함 (API.md 항목 1 예시 아래 메모).
"""

from app.core.db import Base, SessionLocal, engine
from app.modules.submission.constants import EXERCISE_SQUAT, SubmissionStatus
from app.modules.submission.models import WorkoutSubmission


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        submission = WorkoutSubmission(
            status=SubmissionStatus.SUBMITTED,
            exercise_type=EXERCISE_SQUAT,
            counted_reps=30,
        )
        db.add(submission)
        db.commit()
        print(f"seeded SUBMITTED submission id={submission.id}")


if __name__ == "__main__":
    main()
