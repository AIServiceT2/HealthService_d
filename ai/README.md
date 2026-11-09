# 전운시 AI 렙 판정 엔진 (`ai/`)

관절 좌표 시퀀스로 스쿼트 렙 수, 렙별 인정·미인정과 사유, 확신도, 무작위 동작 확인 결과, 자세 요약을 판정하는 Python 패키지 `rep_engine`입니다. 서버 재계산에 쓰는 정답(reference) 구현이라 같은 입력이면 항상 같은 결과를 냅니다.

- 명세: [`SPEC.md`](SPEC.md) (받은 지시서 원문)
- 결정·충돌 기록: [`docs/DECISIONS.md`](docs/DECISIONS.md) — SPEC과 다르게 구현한 곳은 여기를 먼저 보세요
- 작업 규칙: [`CLAUDE.md`](CLAUDE.md)

> 이 문서는 골격입니다. 도구 사용법, 도커 실행, 백엔드 호출 예시, 데이터 수집 가이드는 9단계에서 채웁니다.

## 설치 (macOS, Python 3.11)

```bash
cd ai
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt   # CI·도커용은 requirements-ci.txt / requirements-service.txt
```

## 검사

```bash
cd ai
.venv/bin/ruff check && .venv/bin/mypy rep_engine && .venv/bin/pytest
```

## 내부 API 실행

```bash
# 로컬 (ai/에서)
AI_INTERNAL_TOKEN=<로컬용 값> .venv/bin/uvicorn service.app:app --port 8001

# 도커 (저장소 루트에서). 토큰은 루트 .env 또는 셸 환경변수로 (저장소에 넣지 않음)
docker compose up -d --build ai
curl http://localhost:8001/internal/health
```

| 엔드포인트 | 토큰 | 내용 |
| --- | --- | --- |
| `GET /internal/health` | 불필요 | `{status, engineVersion, catalogVersions}` |
| `POST /internal/recount` | 필요 | `{meta, chunks, client, userReducedCount?}` → `{result, comparison, decision}` |
| `POST /internal/liveness/evaluate` | 필요 | `{meta, frames}` → `LivenessResult` |
| `POST /internal/liveness/issue` | 필요 | → `{action, instruction, challengeId}` |

토큰은 `X-Internal-Token` 헤더로 보냅니다. 오류 형식은 `{code, message, details}`이고, 요청·응답 예시는 9단계에서 채웁니다.

## 개발 도구 (`tools/`)

모두 `ai/`에서 `python -m tools.<이름> --help`로 사용법을 볼 수 있습니다. 자세한 예시와 데이터 수집 가이드는 9단계에서 채웁니다.

| 도구 | 하는 일 | 확인 상태 (2026-11-09) |
| --- | --- | --- |
| `download_models` | MediaPipe lite/full/heavy `.task`를 `models/`로 받기 | 실행 확인 |
| `extract_keypoints` | 영상 → 세션 JSON (15fps, 얼굴 null, 청크 분할) | 사람 없는 테스트 영상으로만 확인 |
| `webcam_demo` | 실시간 렙 판정 화면 (L/R/S/Q) | 영상 입력 `--headless`로만 확인. 카메라 창은 직접 확인 필요 |
| `plot_session` | 세션 → kneeAngle 그래프 PNG | 합성 세션으로 확인 |
| `evaluate` | 라벨 CSV 전체 평가 → reports/eval_* | 합성 샘플로 확인 |
| `compare_models` | lite/full/heavy 정확도·추론 시간 비교 | 사람 없는 영상으로만 확인 |
| `calibrate_confidence` | isotonic 보정 점 목록·신뢰도 곡선 | 합성 샘플로 확인 |
| `angle_study` | 촬영 각도·거리별 정확도 리포트 | 합성 샘플로 확인 |
| `make_test_vectors` | `test_vectors/` 생성 (모바일 팀 공유) | 실행 확인 |
| `make_sample_data` | 합성 세션·`data/labels_sample.csv` 생성 (실데이터 아님) | 실행 확인 |

## PyCharm 설정

1. 저장소 루트(`dictionaryT`)를 프로젝트로 엽니다.
2. Settings → Project → Python Interpreter → Add → Existing → `ai/.venv/bin/python`.
3. `ai` 폴더 우클릭 → Mark Directory as → **Sources Root**.
4. pytest Run Configuration의 Working directory를 `ai/`로 지정합니다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `rep_engine/landmarks.py` | 공통 골격 13개, 모델별 인덱스 매핑 |
| `rep_engine/adapters.py` | MediaPipe(33)·MoveNet(17) → 공통 골격(픽셀 좌표) |
| `rep_engine/schemas.py` | 입출력 pydantic 모델 (JSON camelCase) |
| `rep_engine/config.py` | 카탈로그 설정 로드·검증, 모델별 덮어쓰기 |
| `rep_engine/validation.py` | 청크 완결성·크기·시각 순서·관절 형식 검사 |
| `rep_engine/features/` | 각도·거리(geometry), One Euro 필터(filters), 프레임 특징 추출(extractor) |
| `rep_engine/counters/` | 종목 판정기 등록부(base), 스쿼트 상태 머신(squat) |
| `rep_engine/rounding.py` | 출력 반올림 규칙 (0.5 올림) |
| `rep_engine/liveness.py` | 무작위 동작 발급(`secrets`)·판정 |
| `rep_engine/confidence.py` | 확신도 원시 점수·보정 매핑 |
| `rep_engine/summary.py` | poseSummary, 자세 오류 태그 (L4 입력) |
| `rep_engine/anomaly.py` | 규칙 기반 이상 징후 (L2 입력) |
| `rep_engine/session.py` | 세션 실행기 (`SessionRunner` 스트리밍, `run_session` 배치) |
| `rep_engine/recount.py` | 서버 재계산 비교, R12 감소, 자동 승인 판정 |
| `config/catalog/` | 판정 기준값 (모두 가안) |
| `tools/synth.py` | 합성 스쿼트 생성기 (측면·45°·정면, 거리, MediaPipe·MoveNet, 잡음·가림·손 들기) |
| `test_vectors/` | 모바일 팀 공유용 입력·기대 결과 ([비교 규칙](test_vectors/README.md)) |
