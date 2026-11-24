# 음성 안내 녹음 파일 (API-071)

멘트 코드와 같은 이름으로 녹음 파일을 넣는다. 예: `COUNT_1.m4a`, `SET_DONE.m4a`, `FORM_SQUAT_TOO_FAST.m4a`

- 멘트 코드·대본은 `app/modules/workout_session/voice_cues.py`의 `VOICE_CUES`에 있다.
- 지원 확장자: `.m4a`, `.mp3` (같은 코드에 둘 다 있으면 `.m4a`를 쓴다). 파일 형식은 팀 확인 필요.
- 파일이 있으면 `GET /voice-cues`의 `audioUrl`이 `/static/voice/<파일>` 주소로 채워지고, 없으면 `null`이다.
- 파일을 넣거나 바꾸면 커밋하고 서버를 다시 배포한다. 앱은 다시 빌드하지 않아도 된다.
