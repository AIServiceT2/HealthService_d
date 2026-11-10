"""보상 계산 규칙 (노션 API-031).

경험치·피해 공식·드랍 확률은 노션 명세에서 '미정'이다. 아래 값은 명세 예시(30타 → exp 150,
totalDamage 900, dropCount 1)와 같은 비율로 맞춘 가안이다 [가안·팀 확인 필요].
"""

EXP_PER_HIT = 5
DAMAGE_PER_HIT = 30
# 약점 배율 기본값 가안 1.0 (노션 API-031). 약점 판정은 MVP 제외 (mvp-scope.md)
DEFAULT_WEAKNESS_MULTIPLIER = 1.0
# 타격이 1 이상이면 상자 1개 (드랍 확률 미정)
DROP_COUNT_WHEN_HIT = 1
