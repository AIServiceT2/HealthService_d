# ai/ 작업 규칙

- 이 디렉터리는 전운시 AI 렙 판정 엔진이다. 전체 명세는 `ai/SPEC.md`를 따른다. 단, 팀 결정·저장소 문서가 우선하며 달라진 점은 `docs/DECISIONS.md`에 있다.
- 모든 명령은 `ai/`에서 실행한다. 가상환경은 `ai/.venv`.
- `ai/` 밖은 SPEC.md 0장의 허용 목록 외에는 수정하지 않는다. 루트 CLAUDE.md의 팀 규칙도 그대로 지킨다.
- `rep_engine/`은 numpy, pydantic, pyyaml만 import한다. mediapipe, opencv는 `tools/`에서만.
- 엔진 내부는 모델 독립 공통 골격 13개(`rep_engine/landmarks.py`)만 쓴다. 모델별 인덱스(MediaPipe 33, MoveNet 17)는 어댑터(`rep_engine/adapters.py`)에만 둔다. z 좌표에 의존하는 로직을 만들지 않는다.
- 얼굴 랜드마크는 서버로 받지 않는다(backlog US-01). 업로드 좌표의 얼굴 인덱스는 반드시 null.
- 기준값은 `config/catalog/*.yaml`에만 둔다. 코드에 매직 넘버 금지.
- 엔진은 결정적이어야 한다: 벽시계, 무작위성, 전역 상태 금지 (liveness 동작 발급만 예외).
- 변경 후 반드시 `ruff check && mypy rep_engine && pytest` 통과.
- 팀 합의가 필요한 결정은 `docs/DECISIONS.md`에 기록한다.
