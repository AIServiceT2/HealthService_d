"""종목 판정기. import 시 기본 종목이 등록된다.

SQUAT·PUSHUP·SITUP·LUNGE·INVERTED_SHOULDER_PRESS·GLUTE_BRIDGE·SIDE_LEG_LIFT.
"""

from rep_engine.counters import glute_bridge as _glute_bridge  # noqa: F401  (등록 부수효과)
from rep_engine.counters import (  # noqa: F401  (등록 부수효과)
    inverted_shoulder_press as _inverted_shoulder_press,
)
from rep_engine.counters import lunge as _lunge  # noqa: F401  (등록 부수효과)
from rep_engine.counters import pushup as _pushup  # noqa: F401  (등록 부수효과)
from rep_engine.counters import side_leg_lift as _side_leg_lift  # noqa: F401  (등록 부수효과)
from rep_engine.counters import situp as _situp  # noqa: F401  (등록 부수효과)
from rep_engine.counters import squat as _squat  # noqa: F401  (등록 부수효과)
