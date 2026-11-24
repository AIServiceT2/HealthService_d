"""음성 안내 멘트 목록 (노션 API-071, 기능명세 JN-039).

노션 ERD는 VOICE_CUE 테이블이지만, 값을 바꾸는 API가 없어 catalog.py처럼 코드 상수로 둔다 [제안·팀 확인 필요].
녹음 파일은 backend/static/voice/<멘트 코드>.m4a(또는 .mp3)로 넣으면 서버가 /static/voice/로 내려 주고,
API-071의 audioUrl이 그 주소로 채워진다. 파일을 넣고 서버만 다시 배포하면 된다 (앱은 다시 빌드하지 않음).

미정 (노션 JN-039 '미정 사항'):
- 카운트 최대 횟수 → 첫 데모 목표 30회에 맞춰 30까지 [가안]
- 멘트 문구 → 노션 예시('하나', '한 세트 완료!', '운동 완료! 수고했어요', '조금 더 앉아 주세요') 외에는 [가안]
- 파일 형식(.m4a / .mp3), 녹음 전(audioUrl null)일 때 무음으로 둘지 기기 TTS로 읽을지
"""

from dataclasses import dataclass
from pathlib import Path

# 녹음 파일 폴더. main.py가 backend/static을 /static으로 내려 준다
STATIC_DIR = Path(__file__).resolve().parents[3] / "static"
VOICE_DIR = STATIC_DIR / "voice"
# 같은 코드에 여러 개가 있으면 앞의 확장자를 쓴다. 파일 형식은 팀 확인 필요
AUDIO_EXTENSIONS = (".m4a", ".mp3")

# 멘트가 바뀌면 올린다. 앱은 이 값이 바뀌었을 때만 다시 받는다 (노션 API-071). 값은 노션 예시를 따름
VOICE_CUE_VERSION = "2026.11-1"

# 카운트 최대 횟수 [가안] (노션 JN-039 미정)
COUNT_MAX = 30


@dataclass(frozen=True)
class VoiceCue:
    code: str
    type: str  # COUNT / SET_DONE / WORKOUT_DONE / FORM
    exercise_code: str | None  # 모든 운동 공통이면 None
    number: int | None  # COUNT일 때 읽는 횟수
    reason_code: str | None  # FORM일 때 렙 미인정 사유 (ai/README.md: OUT_OF_FRAME / TOO_FAST / SHALLOW_DEPTH)
    text: str


_TENS = ["", "열", "스물", "서른"]
_ONES = ["", "하나", "둘", "셋", "넷", "다섯", "여섯", "일곱", "여덟", "아홉"]


def _korean_count(n: int) -> str:
    """1~39를 '하나'·'열하나'·'서른' 같은 고유어 수로 읽는다."""
    return _TENS[n // 10] + _ONES[n % 10]


VOICE_CUES: tuple[VoiceCue, ...] = (
    *(
        VoiceCue(f"COUNT_{n}", "COUNT", None, n, None, _korean_count(n))
        for n in range(1, COUNT_MAX + 1)
    ),
    VoiceCue("SET_DONE", "SET_DONE", None, None, None, "한 세트 완료!"),
    VoiceCue("WORKOUT_DONE", "WORKOUT_DONE", None, None, None, "운동 완료! 수고했어요"),
    # 자세 교정. SHALLOW_DEPTH 문구만 노션 예시이고 나머지는 [가안]
    VoiceCue(
        "FORM_SQUAT_OUT_OF_FRAME", "FORM", "SQUAT", None, "OUT_OF_FRAME", "몸 전체가 화면에 보이게 서 주세요"
    ),
    VoiceCue("FORM_SQUAT_TOO_FAST", "FORM", "SQUAT", None, "TOO_FAST", "조금 더 천천히 해 주세요"),
    VoiceCue("FORM_SQUAT_SHALLOW_DEPTH", "FORM", "SQUAT", None, "SHALLOW_DEPTH", "조금 더 앉아 주세요"),
)


def cues_for(exercise_code: str | None) -> list[VoiceCue]:
    """공통 멘트 + (운동을 고르면) 그 운동의 멘트. 운동을 안 고르면 공통 멘트만 (노션 API-071)."""
    return [c for c in VOICE_CUES if c.exercise_code is None or c.exercise_code == exercise_code]


def audio_file_for(code: str, voice_dir: Path | None = None) -> str | None:
    """멘트 코드에 맞는 녹음 파일 이름. 녹음 전이면 None."""
    folder = voice_dir if voice_dir is not None else VOICE_DIR
    for ext in AUDIO_EXTENSIONS:
        if (folder / f"{code}{ext}").is_file():
            return f"{code}{ext}"
    return None
