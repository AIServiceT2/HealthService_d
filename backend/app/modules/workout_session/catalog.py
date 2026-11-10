"""운동 카탈로그 (노션 API-018·019·020).

노션 ERD는 EXERCISE_TYPE 테이블(code, name, daily_cap)이지만, 지금은 MVP 운동이 스쿼트 1종이고
값을 바꾸는 API가 없어 코드 상수로 둔다 [제안·팀 확인 필요]. 운동이 늘거나 운영자가 바꾸게 되면 테이블로 옮긴다.
"""

from dataclasses import dataclass

# ai/ 렙 판정 엔진의 카탈로그 파일(ai/config/catalog/cat_2026-11-01.yaml)과 같은 버전.
# 노션 예시 값은 "2026.11-1"이지만 서버 재계산(API-026)이 이 버전으로 엔진 기준값을 찾으므로 엔진 쪽 이름을 따른다
CATALOG_VERSION = "cat_2026-11-01"


@dataclass(frozen=True)
class Exercise:
    code: str
    name: str
    daily_cap: int  # 일일 인정 상한 (client-meeting-1 질의응답 3: 스쿼트 200회)


# MVP 운동은 스쿼트 1종 (mvp-scope.md 제외 표)
EXERCISES: dict[str, Exercise] = {
    "SQUAT": Exercise(code="SQUAT", name="스쿼트", daily_cap=200),
}
