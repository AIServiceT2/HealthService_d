# 전운시 AI 렙 판정 엔진 (`ai/`)

관절 좌표 시퀀스로 스쿼트 렙 수, 렙별 인정·미인정과 사유, 확신도, 무작위 동작 확인 결과, 자세 요약, 이상 징후를 판정하는 Python 패키지 `rep_engine`입니다. 내부 API와 개발 도구가 함께 있습니다. 서버 재계산에 쓰는 **정답(reference) 구현**이라 같은 입력이면 항상 같은 결과(바이트 단위)를 냅니다. 모바일 구현은 [`test_vectors/`](test_vectors/README.md)로 이 엔진과 결과를 맞춥니다.

| 문서 | 내용 |
| --- | --- |
| [`SPEC.md`](SPEC.md) | 받은 구현 지시서 원문 |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | **SPEC과 다르게 구현한 곳, 가정, 팀 합의가 필요한 것** — 먼저 읽으세요 |
| [`CLAUDE.md`](CLAUDE.md) | 이 폴더의 작업 규칙 |
| [`test_vectors/README.md`](test_vectors/README.md) | 모바일 팀용 테스트 벡터 형식과 비교 규칙 |

## 지금 상태 (2026-11-09)

| 확인한 것 | 아직 확인하지 않은 것 |
| --- | --- |
| `ruff check`, `mypy rep_engine`, `pytest`(테스트 197개, `rep_engine` 커버리지 99%) — 로컬과 CI 조건(mediapipe 없는 가상환경) 모두 통과 | **실제 사람 영상으로 한 평가 없음.** 모든 정확도 수치는 합성 데이터 |
| 10분 세션(9,092프레임) 재계산 0.44초 (Apple M3) | 웹캠 창으로 실제 스쿼트 세기 (`webcam_demo`) |
| `docker compose up -d --build ai` → health·401·재계산 응답 | 실제 영상으로 `extract_keypoints → evaluate → plot_session` |
| MediaPipe 모델 3종 내려받기, 사람 없는 영상으로 추출 경로 | GitHub Actions에서 `ai-ci.yml` 실행 (푸시 후 확인) |

모든 판정 기준값(`config/catalog/cat_2026-11-01.yaml`)은 **가안**입니다. 근거와 한계는 DECISIONS.md를 보세요. 특히 확신도가 촬영 각도 때문에 생긴 판정 오류를 반영하지 못하는 문제(D-54)가 있습니다.

푸시업(`PUSHUP`)·윗몸 일으키기(`SITUP`)는 `cat_2026-11-10`에서만 판정할 수 있습니다. MVP 범위 밖이고, 기준값은 모두 실측 근거 없는 가정입니다 (D-66~D-69).

## 설치 (macOS·Linux, Python 3.11)

```bash
cd ai
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

| 파일 | 쓰는 곳 | 내용 |
| --- | --- | --- |
| `requirements.txt` | 로컬 개발 전체 | CI용 + mediapipe, opencv-python |
| `requirements-ci.txt` | GitHub Actions | 서비스용 + 테스트·린트·평가 도구 (mediapipe·opencv 제외) |
| `requirements-service.txt` | Docker 이미지 | numpy, pydantic, PyYAML, fastapi, uvicorn |

`rep_engine/`은 numpy·pydantic·PyYAML만 씁니다. mediapipe·opencv는 `tools/`에서만 씁니다(`tests/test_dependency_boundary.py`가 검사).

## 검사

```bash
cd ai
.venv/bin/ruff check && .venv/bin/mypy rep_engine && .venv/bin/pytest
.venv/bin/pytest --cov=rep_engine --cov-fail-under=90   # CI와 같은 명령
```

## PyCharm 설정

1. 저장소 루트(`dictionaryT`)를 프로젝트로 엽니다.
2. Settings → Project → Python Interpreter → Add Interpreter → Existing → `ai/.venv/bin/python`.
3. `ai` 폴더 우클릭 → Mark Directory as → **Sources Root**.
4. **pytest**: Run → Edit Configurations → + → pytest → Target: Script path `ai/tests`, **Working directory `ai/`**.
5. **도구**: Run → Edit Configurations → + → Python → Module name에 `tools.evaluate`처럼 입력, Parameters에 인자(예: `--labels data/labels_sample.csv`), **Working directory `ai/`**.

## 판정 흐름

```
업로드 청크 ─▶ 검증(seq·크기·시각·얼굴 null) ─▶ 어댑터(MediaPipe 33 / MoveNet 17 → 공통 골격 13, 픽셀 좌표)
  ─▶ 무작위 동작 확인(issuedAtT~expiresAtT)
  ─▶ 특징(kneeAngle·One Euro 필터·hipDrop…) ─▶ 스쿼트 상태 머신(STANDING→DESCENDING→ASCENDING)
  ─▶ 확신도 ─▶ poseSummary·formTags ─▶ 이상 징후 ─▶ (서버) 클라이언트 비교 ─▶ 자동 승인 판정
```

- 렙 미인정 사유: `OUT_OF_FRAME` > `TOO_FAST` > `SHALLOW_DEPTH` (하나만).
- 인정량과 확신도는 항상 **서버 값**입니다. 사용자는 횟수를 줄일 수만 있습니다(R12).
- 이 엔진은 판정만 내고 제출건 상태(`PREPARED → APPROVED` 등)는 바꾸지 않습니다. 상태 전이는 백엔드가 합니다(D-37).

## 내부 API

### 실행

```bash
# 로컬 (ai/에서)
AI_INTERNAL_TOKEN=<로컬용 값> .venv/bin/uvicorn service.app:app --port 8001

# 도커 (저장소 루트에서). 토큰은 셸 환경변수나 루트 .env로 (저장소에 넣지 않음)
docker compose up -d --build ai
curl http://localhost:8001/internal/health
# {"status":"ok","engineVersion":"0.1.0","catalogVersions":["cat_2026-11-01"]}
```

`AI_INTERNAL_TOKEN`이 비어 있으면 토큰이 필요한 엔드포인트는 모두 401입니다(D-45). 백엔드는 같은 compose 네트워크에서 `http://ai:8001/internal/...`로 부릅니다. 백엔드 쪽 호출 코드는 아직 없습니다.

| 엔드포인트 | 토큰 | 요청 → 응답 |
| --- | --- | --- |
| `GET /internal/health` | 불필요 | → `{status, engineVersion, catalogVersions}` |
| `POST /internal/recount` | `X-Internal-Token` | `{meta, chunks, client, userReducedCount?}` → `{result, comparison, decision}` |
| `POST /internal/liveness/evaluate` | `X-Internal-Token` | `{meta, frames}` → `LivenessResult` (`meta.liveness` 필수) |
| `POST /internal/liveness/issue` | `X-Internal-Token` | → `{action, instruction, challengeId}` (시각은 백엔드가 정함) |

### 재계산 호출 예시

아래 JSON은 합성 세션(1렙)을 실제로 호출한 결과입니다(2026-11-09). 요청의 `frames`는 길어서 두 개만 남기고, 좌표 자릿수도 줄여 적었습니다. 응답은 받은 그대로입니다(줄바꿈만 정리).

```bash
curl -X POST http://localhost:8001/internal/recount \
  -H "X-Internal-Token: $AI_INTERNAL_TOKEN" -H "Content-Type: application/json" \
  --data @recount.json
```

요청(`recount.json`):

```json
{
  "meta": {
    "sessionId": "sess-123",
    "exerciseType": "SQUAT",
    "catalogVersion": "cat_2026-11-01",
    "fps": 15,
    "imageWidth": 720,
    "imageHeight": 1280,
    "mirrored": false,
    "device": { "platform": "ANDROID", "modelVersion": "mediapipe-pose-full@0.10" },
    "liveness": { "challengeId": "ch-1", "action": "RAISE_LEFT_HAND", "issuedAtT": 0, "expiresAtT": 3000 }
  },
  "chunks": [
    { "sessionId": "sess-123", "seq": 0, "frames": [
      { "t": 0, "landmarks": [null, null, null, null, null, null, null, null, null, null, null,
        { "x": 0.5159, "y": 0.2596, "z": 0.0, "visibility": 0.9 }, "... 33개까지 ..."] },
      { "t": 67, "landmarks": null }
    ] }
  ],
  "client": {
    "clientRepCount": 1,
    "reps": [{ "startT": 4260, "endT": 5930, "accepted": true, "reason": null }],
    "aiConfidence": 0.91,
    "poseSummary": null
  }
}
```

- `landmarks`는 모델 원본 순서(MediaPipe 33 / MoveNet 17)이고, **얼굴 인덱스(MediaPipe 0~10, MoveNet 0~4)는 반드시 null**입니다(US-01, D-07). `null` 프레임은 사람 미검출입니다.
- `modelVersion` 접두어로 어댑터를 고릅니다: `mediapipe-pose…` / `movenet…`. 그 밖은 400입니다(D-04).
- 청크 하나는 300프레임 이하이면서 262,144바이트 이하여야 합니다. MediaPipe는 청크당 약 110프레임까지 들어갑니다(D-06).

응답:

```json
{
  "result": {
    "engineVersion": "0.1.0",
    "catalogVersion": "cat_2026-11-01",
    "reps": [
      { "index": 1, "startT": 3867, "bottomT": 4667, "endT": 5467, "accepted": true, "reason": null,
        "minKneeAngle": 85.8, "maxHipDrop": 0.332, "trunkLeanAtBottom": 28.0,
        "kneeAsymmetryAtBottom": 1.7, "invalidRatio": 0.0 }
    ],
    "recognizedReps": 1,
    "attemptedReps": 1,
    "liveness": {
      "challengeId": "ch-1", "action": "RAISE_LEFT_HAND", "status": "PASSED", "passedAtT": 1533,
      "evidence": { "maxHoldMs": 1000, "wrongHandMaxHoldMs": 0, "validFrameRatio": 1.0, "wrongHandDetected": false }
    },
    "aiConfidence": 0.9,
    "confidenceComponents": {
      "vis": 0.9, "valid": 1.0, "track": 1.0, "consistency": 0.5, "unaccepted": 1.0, "raw": 0.9,
      "livenessPenaltyApplied": false, "activeStartT": 1533, "activeEndT": 5467
    },
    "poseSummary": {
      "kneeFlexionDeg": { "avg": 94.2, "min": 94.2, "max": 94.2 },
      "trunkLeanDeg": { "avg": 28.0, "max": 28.0 },
      "kneeAsymmetryDeg": { "avg": 1.7 },
      "repDurationMs": { "avg": 1600.0, "std": 0.0 },
      "depthConsistencyDeg": 0.0,
      "formTags": []
    },
    "anomalies": []
  },
  "comparison": {
    "serverRepCount": 1, "clientRepCount": 1, "userReducedCount": null, "finalRepCount": 1,
    "mismatch": false, "mismatchRatio": 0.0, "errorCode": null,
    "matchedReps": 1, "clientOnlyReps": 0, "serverOnlyReps": 0, "acceptedDisagreements": 0,
    "serverConfidence": 0.9, "clientConfidence": 0.91, "confidenceDiff": 0.01, "anomalies": []
  },
  "decision": {
    "decision": "AUTO_APPROVE",
    "approvalPath": "AI_AUTO",
    "reasonCodes": [],
    "evidence": {
      "serverConfidence": 0.9, "autoApproveThreshold": 0.9, "livenessStatus": "PASSED",
      "livenessPolicy": "restart", "mismatch": false, "highAnomalies": []
    }
  }
}
```

이 예시는 렙이 1개라 일관성 점수가 중립값(0.5)이고, 확신도가 기준과 같은 0.9라서 자동 승인됐습니다. 렙 수와 확신도의 관계는 D-54를 보세요.

| `decision` | `approvalPath` | 백엔드 처리 (제안, D-37) |
| --- | --- | --- |
| `AUTO_APPROVE` | `AI_AUTO` | `PREPARED → APPROVED`, 승인 경로 `AI_AUTO` |
| `HUMAN_REVIEW` | `HUMAN_REVIEW` | `PREPARED` 유지 + 확인 요청 버튼 (US-03). `reasonCodes`: `LOW_CONFIDENCE` · `LIVENESS_NOT_PASSED` · `RECOUNT_MISMATCH` · `ANOMALY_HIGH` |
| `REJECT_RESTART` | `RESTART` | 무작위 동작 실패. 처리 방식은 PRD 미정 (D-38) |

### 오류

| HTTP | `code` | 언제 |
| --- | --- | --- |
| 400 | `VALIDATION_FAILED` | 요청 형식(camelCase만), 청크 누락(`details.missingSeq`), 크기·시각 순서, 얼굴 좌표, 모르는 모델, 없는 카탈로그 |
| 400 | `INVALID_REDUCTION` | `userReducedCount`가 서버 인정량보다 큼 |
| 401 | `UNAUTHORIZED` | 토큰 없음·틀림·서버에 토큰 미설정 |
| 500 | `CONFIG_ERROR` | 서버 카탈로그 파일 오류 |
| 200 | — | 클라이언트와 렙 수가 다르면 `comparison.errorCode = "SERVER_RECOUNT_MISMATCH"` (오류 아님) |

```json
{"code": "VALIDATION_FAILED", "message": "누락된 청크가 있음: [0]", "details": {"missingSeq": [0]}}
```

## 개발 도구 (`tools/`)

모두 `ai/`에서 `.venv/bin/python -m tools.<이름>`으로 실행하고, `--help`로 인자를 볼 수 있습니다.

| 도구 | 하는 일 | 확인 상태 (2026-11-09) |
| --- | --- | --- |
| `download_models` | MediaPipe lite/full/heavy `.task`를 `models/`로 받기 | 실행 확인 |
| `extract_keypoints` | 영상 → 세션 JSON (15fps, 얼굴 null, 청크 분할) | 사람 없는 테스트 영상으로만 확인 |
| `webcam_demo` | 실시간 렙 판정 화면, `--snapshots`로 인정 렙 최저점 사진 저장 | 리더가 카메라로 실행 확인. 사진 저장은 합성 입력으로 확인 |
| `plot_session` | 세션 → kneeAngle 그래프 PNG | 합성 세션으로 확인 |
| `evaluate` | 라벨 CSV 전체 평가 | 합성 샘플로 확인 |
| `compare_models` | lite/full/heavy 정확도·추론 시간 | 사람 없는 영상으로만 확인 (시간 비교 무의미, D-60) |
| `calibrate_confidence` | isotonic 보정 점 목록·신뢰도 곡선 | 합성 샘플로 확인 |
| `angle_study` | 촬영 각도·거리별 정확도 → 권장 촬영 각도 근거 | 합성 샘플로 확인 |
| `make_test_vectors` | `test_vectors/` 생성 | 실행 확인 |
| `make_sample_data` | 합성 세션·`data/labels_sample.csv` (실데이터 아님) | 실행 확인 |

### 실제 영상 하나로 끝까지

```bash
cd ai
.venv/bin/python -m tools.download_models                      # 처음 한 번 (models/, git 제외)
.venv/bin/python -m tools.extract_keypoints data/videos/s01_side_near.mp4 --model full
#   → data/keypoints/s01_side_near.json
# data/labels.csv에 이 세션의 정답 한 줄을 적는다 (아래 '라벨 작성법')
.venv/bin/python -m tools.evaluate                             # → reports/eval_<날짜>.md, .csv
.venv/bin/python -m tools.plot_session data/keypoints/s01_side_near.json   # → reports/s01_side_near.png
```

### 그 밖의 사용 예

```bash
# 웹캠 데모 (키: L 무작위 동작 · R 리셋 · S 저장 · Q 종료). 처음엔 macOS가 카메라 권한을 묻는다
.venv/bin/python -m tools.webcam_demo --model lite
# 인정 렙마다 최저점 사진 1장 → ~/Downloads/jeonunsi_snapshots/<세션ID>/rep03_86.2deg.jpg
# 흐림 없음(얼굴이 나옴). 이 PC에만 두고 저장소·공유 폴더에 올리지 않는다 (D-65)
.venv/bin/python -m tools.webcam_demo --model lite --snapshots
.venv/bin/python -m tools.webcam_demo --source data/videos/s01.mp4 --headless   # 창 없이

# 다른 카탈로그(기준값)로 비교 평가
.venv/bin/python -m tools.evaluate --config path/to/cat_try.yaml --tag try

# 모델 비교 (라벨의 session_file 이름이 영상 이름과 같은 행을 정답으로 씀)
.venv/bin/python -m tools.compare_models data/videos/ --labels data/labels.csv

# 확신도 보정 (정답·오답 세션이 모두 있어야 함) → 점 목록을 카탈로그 confidence.calibration에 옮김
.venv/bin/python -m tools.calibrate_confidence --labels data/labels.csv

# 촬영 조건별 정확도 (조건마다 세션 5개 이상이어야 권장안을 냄)
.venv/bin/python -m tools.angle_study --labels data/labels.csv --min-n 5

# 실데이터 없이 도구 확인: 합성 샘플 만들고 평가
.venv/bin/python -m tools.make_sample_data --n 40
.venv/bin/python -m tools.evaluate --labels data/labels_sample.csv --tag sample

# 엔진·카탈로그를 바꾼 뒤 테스트 벡터 재생성 (tests/test_vectors.py가 어긋남을 잡음)
.venv/bin/python -m tools.make_test_vectors
```

결과물은 `reports/`(git 제외)에 쌓입니다. 합성 데이터로 만든 리포트에는 "근거로 쓰지 않는다"는 경고가 자동으로 들어갑니다.

## 데이터 수집 가이드

기준값과 확신도 보정(D-54), 권장 촬영 각도(US-01 튜토리얼)는 **실제 촬영 데이터가 있어야** 정할 수 있습니다.

### 촬영 전에

- 촬영 대상자의 동의를 받습니다. 영상은 `data/videos/`에만 두고 **저장소에 올리지 않습니다**(git 제외). 추출한 좌표(`data/keypoints/*.json`)를 저장소에 올릴지는 팀 결정 전입니다(D-53). 정해지기 전에는 올리지 않습니다.
- 얼굴이 나와도 추출 단계에서 얼굴 좌표는 null로 지워집니다. 하지만 원본 영상에는 얼굴이 남으니 영상은 공유 폴더에도 올리지 않습니다.

### 촬영 조건 (6가지 × 사람마다)

| | 가까이 (`near`): 전신이 화면 세로의 70~90% | 멀리 (`far`): 전신이 화면 세로의 40~50% |
| --- | --- | --- |
| 측면 (`side`): 몸 옆면이 카메라를 향함 | ☐ | ☐ |
| 45° (`diag45`) | ☐ | ☐ |
| 정면 (`front`) | ☐ | ☐ |

- 폰은 세로로, 허리 높이에 고정합니다. 머리부터 발끝까지 화면 안에 들어오게 합니다.
- 조건마다 세션 하나에 아래 동작을 섞고, **실제로 몇 번 했는지 사람이 세어 적습니다**.

| 동작 | 횟수 (세션당) | 라벨 열 |
| --- | --- | --- |
| 정상 스쿼트 (허벅지가 바닥과 평행 이하) | 5~10 | `expected_accepted` |
| 반쪽 스쿼트 (얕게) | 2~3 | `expected_shallow` |
| 빠른 반복 (한 번에 0.8초 미만) | 1~2 | `expected_too_fast` |
| 내려간 상태로 화면 밖으로 잠깐 나갔다 오기 (1초 이상) | 1~2 | `expected_out_of_frame` |

- 세션 처음 3초는 정면을 보고 서서 왼손을 머리 위로 1초 이상 듭니다(무작위 동작 확인 연습, D-24).
- 파일 이름 예: `s01_side_near.mp4` (사람 번호 `s01`은 실명 대신 씁니다).

### 라벨 작성법 (`data/labels.csv`)

`data/labels.csv`는 실데이터 전용입니다. 합성 샘플은 `data/labels_sample.csv`에 따로 있습니다(D-52).

```csv
session_file,view,distance,subject,expected_accepted,expected_shallow,expected_too_fast,expected_out_of_frame,notes
keypoints/s01_side_near.json,side,near,s01,8,2,1,1,실내 형광등
```

| 열 | 값 |
| --- | --- |
| `session_file` | `data/` 기준 상대 경로 |
| `view` | `side` / `diag45` / `front` |
| `distance` | `near` / `far` |
| `subject` | 사람 번호 (실명 금지). 합성은 `synthetic` |
| `expected_accepted` | 사람이 센 **정상 렙 수** (필수) |
| `expected_shallow` 등 3개 | 사람이 센 개수. 세지 않았으면 비워 둠(그 사유는 평가에서 빠짐) |
| `notes` | 조명·옷·배경 등 |

## 구조

| 경로 | 내용 |
| --- | --- |
| `rep_engine/landmarks.py`, `adapters.py` | 공통 골격 13개, MediaPipe(33)·MoveNet(17) → 공통 골격 |
| `rep_engine/schemas.py`, `validation.py` | 입출력 pydantic 모델(JSON camelCase), 청크 검증 |
| `rep_engine/config.py` | 카탈로그 로드·검증, 모델별 덮어쓰기 |
| `rep_engine/features/` | 각도·거리, One Euro 필터, 프레임 특징 |
| `rep_engine/counters/` | 종목 판정기 등록부, 스쿼트 상태 머신 |
| `rep_engine/liveness.py` | 무작위 동작 발급·판정 |
| `rep_engine/confidence.py`, `summary.py`, `anomaly.py` | 확신도, poseSummary·formTags, 이상 징후 |
| `rep_engine/session.py`, `recount.py` | 세션 실행기, 서버 재계산 비교·자동 승인 판정 |
| `rep_engine/rounding.py`, `stats.py` | 반올림(0.5 올림), 통계 |
| `service/app.py` | FastAPI 내부 API |
| `tools/` | 개발 도구, 합성 생성기(`synth.py`), 공용 입출력(`common.py`) |
| `config/catalog/` | 판정 기준값 (모두 가안) |
| `test_vectors/` | 모바일 팀 공유용 입력·기대 결과 |
| `tests/` | pytest |
| `models/`, `data/videos/`, `reports/` | git 제외 (모델 파일, 원본 영상, 리포트) |
