"""종목 판정기. import 시 기본 종목(SQUAT·PUSHUP·SITUP)이 등록된다."""

from rep_engine.counters import pushup as _pushup  # noqa: F401  (등록 부수효과)
from rep_engine.counters import situp as _situp  # noqa: F401  (등록 부수효과)
from rep_engine.counters import squat as _squat  # noqa: F401  (등록 부수효과)
