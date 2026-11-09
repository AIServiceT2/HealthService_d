> **이 저장소에서의 적용 메모 (2026-11-09):** 아래는 받은 지시서 원문이다. 원문은 고치지 않는다.
> 팀 결정과 저장소 문서(STACK.md, first-feature.md 등)가 이 문서보다 우선한다. 달라진 점은 `docs/DECISIONS.md`에 있다.
> 특히 MediaPipe 33개 인덱스를 직접 쓰는 대신 **모델 독립 공통 골격 13개 + 모델별 어댑터(MediaPipe 33 / MoveNet 17)** 구조를 쓴다 (DECISIONS.md D-01).

# 전운시 AI 렙 판정 엔진 구현 지시서

이 문서를 처음부터 끝까지 읽고, 0장의 규칙을 지키면서 13장의 작업 순서대로 **모든 기능을 빠짐없이 구현**하라. 각 단계가 끝날 때마다 `ruff check`, `mypy rep_engine`, `pytest`를 실행해 전부 통과시킨 뒤 다음 단계로 넘어가라. 명세가 모호하면 멈추지 말고 합리적인 가정으로 구현한 뒤, 그 가정을 `ai/docs/DECISIONS.md`에 기록하라. 데이터나 결과를 지어내지 마라.

---

## 0. 모노레포 배치 규칙 (가장 먼저 읽을 것)

이 저장소(`dictionaryT`)는 `backend/`, `mobile/`, `ai/`가 함께 있는 모노레포다. **이 문서의 모든 작업은 `ai/` 디렉터리 안에서 한다.** 이 문서에 나오는 모든 경로(`rep_engine/`, `tools/`, `config/`, `docs/` 등)는 특별히 루트라고 명시하지 않는 한 `ai/` 기준 상대 경로다.

작업 시작 전에 반드시:
1. 루트 `CLAUDE.md`, `README.md`, `docker-compose.yml`, `.gitignore`, `docs/`를 읽고 저장소 규칙(커밋 규칙, 문서 위치, 네이밍, 사용 중인 포트)을 파악하라. 이 문서와 루트 규칙이 충돌하면 루트 규칙을 따르고, 충돌 내용을 `ai/docs/DECISIONS.md`에 기록하라.
2. `backend/`에 AI 서비스를 호출하는 코드나 API 명세가 이미 있는지 확인하고, 있으면 그 계약(경로, 필드명, 포트)에 맞춰라. 단, `backend/`는 읽기만 한다.

수정 허용 범위:
- `ai/` 안: 자유롭게 생성·수정.
- 루트 `docker-compose.yml`: `ai` 서비스 블록 **추가만** 허용. 기존 서비스 설정은 건드리지 마라.
- 루트 `.github/workflows/`: `ai-ci.yml` 새 파일 **추가만** 허용.
- 루트 `README.md`: `ai/README.md`로 가는 링크 한 줄 **추가만** 허용.
- 그 외 `backend/`, `mobile/`, `.claude/`, `.mcp.json`, 루트 `CLAUDE.md`, 루트 `.gitignore`, `logs/`, 루트 `docs/`는 **절대 수정하지 마라.** 수정이 필요하다고 판단되면 하지 말고 최종 보고에 제안으로 적어라.

모든 터미널 명령은 `cd ai` 후 실행한다고 가정하라.

---

## 1. 역할과 목표

너는 "전운시"(운동하면 RPG 캐릭터가 성장하는 피트니스 게임) 프로젝트의 AI 개발을 맡은 시니어 Python 엔지니어다.

목표는 **관절 좌표 시퀀스를 받아 스쿼트 렙 수, 렙별 인정/미인정과 사유, 세션 확신도, 무작위 동작 확인 결과, 자세 요약을 판정하는 Python 패키지 `rep_engine`** 과, 그것을 감싼 내부 API 및 개발 도구를 만드는 것이다.

이 엔진의 위치:
- 모바일 앱(iOS/Android)은 기기에서 MediaPipe Pose로 관절 좌표를 뽑아 실시간으로 렙을 세고, 좌표를 청크로 서버에 올린다. **영상은 저장·전송하지 않는다.**
- 서버는 받은 좌표로 **같은 엔진을 돌려 렙 수와 확신도를 다시 계산**하고, 기기 결과와 비교한다.
- 따라서 이 Python 엔진이 **정답(reference) 구현**이다. 모바일 팀은 이 엔진의 테스트 벡터로 자기 구현을 검증한다. 결정성(같은 입력 → 항상 같은 출력)이 최우선이다.

근거 명세:
- JN-001 렙을 세어 자동 제출 / JN-003 확신도 기준 이상이면 자동 승인(기준 90% 가안)
- JN-012 판정 기준·권장 촬영 각도 안내 / JN-013 무작위 동작 확인
- JN-014 온디바이스 렙 인식·즉시 피드백 (관절 누락·인식 불가를 정상 인정으로 처리하지 않음, 가동범위 미달 렙은 인정량에서 제외, 사용자의 횟수 증가 요청은 거부)
- JN-015 일일 상한·서버 재검증 / JN-018 L4 자세 교정 코멘트 입력 / JN-019 L2 규칙 기반 이상 징후
- API-020 세션 시작: `chunkSpec = { maxFrames: 300, maxBytes: 262144, fps: 15 }`, `exerciseType = SQUAT`
- API-026 세션 종료·제출: 아래 3장, 9장의 필드명을 그대로 따른다.

MVP 범위는 **스쿼트 하나**지만, 종목을 추가할 수 있게 종목별 판정기를 플러그인 구조로 만든다.

---

## 2. 개발 환경과 프로젝트 구조

- IDE: PyCharm, 저장소 루트(`dictionaryT`)를 프로젝트로 연다.
- Python 3.11, 가상환경은 **`ai/.venv`** 에 만든다. PyCharm 인터프리터를 `ai/.venv`로 지정하고, `ai/` 폴더를 **Sources Root**로 표시한다(Mark Directory as → Sources Root). README에 이 설정 방법을 적는다.
- 의존성(`ai/requirements.txt`, 설치 시점 안정 버전으로 고정):
  - 런타임: `numpy`, `pydantic>=2`, `pyyaml`
  - 자세 추정(도구 전용): `mediapipe`, `opencv-python`
  - 서버: `fastapi`, `uvicorn`
  - 도구·평가: `matplotlib`, `scikit-learn`
  - 개발: `pytest`, `pytest-cov`, `ruff`, `mypy`, `httpx`(FastAPI TestClient용)
- 도커 이미지용 `ai/requirements-service.txt`(numpy, pydantic, pyyaml, fastapi, uvicorn만)와 CI용 `ai/requirements-ci.txt`(mediapipe, opencv 제외)를 별도로 둔다.
- **`rep_engine` 핵심 패키지는 numpy, pydantic, pyyaml만 import한다.** mediapipe, opencv는 `tools/`에서만 쓴다. (서버 재계산 환경을 가볍게 유지하고, 모바일 포팅 대상 로직을 분리하기 위함)

```
dictionaryT/
├── backend/                     # 수정 금지
├── mobile/                      # 수정 금지
├── docker-compose.yml           # ai 서비스 블록 추가만
├── .github/workflows/ai-ci.yml  # 신규 추가
└── ai/
    ├── CLAUDE.md                # AI 디렉터리 전용 작업 규칙
    ├── SPEC.md                  # 이 문서
    ├── README.md
    ├── .gitignore
    ├── .dockerignore
    ├── Dockerfile
    ├── pyproject.toml           # ruff, mypy, pytest 설정
    ├── requirements.txt
    ├── requirements-service.txt
    ├── requirements-ci.txt
    ├── rep_engine/
    │   ├── __init__.py          # ENGINE_VERSION 노출
    │   ├── schemas.py           # 모든 입출력 pydantic 모델
    │   ├── landmarks.py         # MediaPipe 33개 관절 인덱스 상수
    │   ├── config.py            # 카탈로그 설정 로드·검증
    │   ├── features/
    │   │   ├── geometry.py      # 각도·거리 계산 (종횡비 보정 포함)
    │   │   ├── filters.py       # One Euro 필터
    │   │   └── extractor.py     # 프레임 → 특징 벡터
    │   ├── counters/
    │   │   ├── base.py          # 종목 판정기 인터페이스
    │   │   └── squat.py         # 스쿼트 상태 머신
    │   ├── liveness.py          # 무작위 동작 확인
    │   ├── confidence.py        # 확신도 계산 + 보정 매핑 적용
    │   ├── summary.py           # poseSummary, 자세 오류 태그
    │   ├── anomaly.py           # 이상 징후 탐지 (L2 입력)
    │   ├── session.py           # 세션 단위 실행기 (스트리밍/배치 공용)
    │   └── recount.py           # 서버 재계산·비교·자동 승인 판정
    ├── service/
    │   └── app.py               # FastAPI 내부 API
    ├── tools/
    │   ├── download_models.py
    │   ├── extract_keypoints.py
    │   ├── webcam_demo.py
    │   ├── plot_session.py
    │   ├── evaluate.py
    │   ├── compare_models.py
    │   ├── calibrate_confidence.py
    │   ├── angle_study.py
    │   └── make_test_vectors.py
    ├── config/catalog/cat_2026-11-01.yaml
    ├── models/                  # .task 파일 (git 제외)
    ├── data/
    │   ├── videos/              # 원본 영상 (git 제외)
    │   ├── keypoints/           # 추출된 세션 JSON
    │   └── labels.csv
    ├── reports/                 # 평가 리포트 (git 제외)
    ├── test_vectors/            # 모바일 팀 공유용 (git 포함)
    ├── tests/
    └── docs/DECISIONS.md
```

`ai/.gitignore`: `.venv/`, `models/*.task`, `data/videos/`, `reports/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`. 루트 `.gitignore`는 건드리지 않는다.

`ai/pyproject.toml`의 pytest 설정은 `testpaths = ["tests"]`, `pythonpath = ["."]`로 해서 `cd ai && pytest`로 실행되게 한다. PyCharm pytest Run Configuration의 Working directory를 `ai/`로 지정하도록 README에 적는다.

### 2.1 도커·CI 연동

- `ai/Dockerfile`: `python:3.11-slim` 기반, `requirements-service.txt`만 설치, `rep_engine/`, `service/`, `config/`만 복사, `uvicorn service.app:app --host 0.0.0.0 --port 8001` 실행. `ai/.dockerignore`로 `.venv`, `data`, `models`, `reports`, `tests`, `tools`를 제외.
- 루트 `docker-compose.yml`에 추가할 블록 (기존 포트와 겹치면 비어 있는 포트로 바꾸고 DECISIONS.md에 기록):
  ```yaml
  ai:
    build: ./ai
    environment:
      - AI_INTERNAL_TOKEN=${AI_INTERNAL_TOKEN}
    ports:
      - "8001:8001"
  ```
  백엔드는 `http://ai:8001/internal/...`로 호출한다. 백엔드 쪽 연동 코드는 작성하지 말고 `ai/README.md`에 호출 예시(curl, 요청/응답 JSON)만 적는다.
- 루트 `.github/workflows/ai-ci.yml`: `on: push/pull_request` + `paths: ["ai/**"]` 트리거, `defaults.run.working-directory: ai`, Python 3.11, `pip install -r requirements-ci.txt`, `ruff check`, `mypy rep_engine`, `pytest --cov=rep_engine --cov-fail-under=90`.
- 로그는 표준 출력으로만 내보낸다(루트 `logs/`에 쓰지 않음).

---

## 3. 입력 데이터 계약

### 3.1 좌표계와 관절

- MediaPipe Pose Landmarker의 33개 관절을 쓴다. 사용할 인덱스: 0 코, 11/12 어깨(좌/우), 13/14 팔꿈치, 15/16 손목, 23/24 엉덩이, 25/26 무릎, 27/28 발목.
- 좌표는 정규화 이미지 좌표 `x, y ∈ [0, 1]`(y는 아래로 증가), `z`(상대 깊이), `visibility ∈ [0, 1]`.
- **좌우 기준: MediaPipe 인덱스의 left/right = 사용자 본인 신체 기준.** 클라이언트는 화면 표시용으로 미러링하더라도 **업로드 좌표는 미러링하지 않은 원본 추론 결과**를 보낸다. 이 규칙을 `DECISIONS.md`에 "모바일 팀 합의 필요"로 기록하고, 세션 메타에 `mirrored: bool` 필드를 두어 `true`면 엔진이 좌우 인덱스를 스왑한 뒤 처리한다.
- 정규화 좌표는 종횡비가 왜곡되어 있다. 각도·거리 계산 전 반드시 `x * imageWidth`, `y * imageHeight`로 픽셀 단위 변환한다.

### 3.2 스키마 (`schemas.py`)

JSON 필드는 camelCase(API 명세와 동일), Python 속성은 snake_case로 하고 pydantic `alias_generator`로 매핑한다. 직렬화는 항상 alias(camelCase)로 한다.

```text
Landmark { x: float, y: float, z: float, visibility: float }

Frame {
  t: int                 # 세션 시작 기준 ms, 단조 증가
  landmarks: Landmark[33] | null   # null = 사람 미검출
}

Chunk {
  sessionId: str
  seq: int               # 0부터 연속
  frames: Frame[]        # 최대 300개
}

SessionMeta {
  sessionId: str
  exerciseType: "SQUAT"
  catalogVersion: str    # 예: "cat_2026-11-01"
  fps: int               # 15
  imageWidth: int
  imageHeight: int
  mirrored: bool
  device: { platform: "IOS" | "ANDROID", modelVersion: str }
  liveness: { challengeId: str, action: LivenessAction, issuedAtT: int, expiresAtT: int } | null
}
```

검증 규칙: `t` 역순·중복 금지, landmarks 길이 33, 값 범위 확인, 청크 직렬화 크기 ≤ 262144바이트, 프레임 수 ≤ 300. 위반 시 명확한 예외 클래스(`ChunkValidationError` 등)를 던진다.

### 3.3 프레임레이트

엔진은 **15fps 입력 기준으로 설계·검증**한다. 다른 fps가 들어와도 시간 기반(ms) 규칙만 쓰고 프레임 개수 기반 규칙은 쓰지 않는다. 30fps와 15fps로 같은 동작을 넣었을 때 렙 수가 같아야 한다.

---

## 4. 특징 추출

### 4.1 각도 정의 (반드시 이 정의를 따르고 docstring에 명시)

- `kneeAngle` = 엉덩이–무릎–발목이 이루는 **내각**(도). 완전히 펴면 약 180°, 깊이 앉으면 작아진다. 판정 상태 머신은 이 값을 쓴다.
- `kneeFlexion` = `180 − kneeAngle`. 펴면 0°. **poseSummary의 `kneeFlexionDeg`는 이 값**이다. API 예시의 숫자가 어느 정의인지 불명확하므로 `DECISIONS.md`에 기록한다.
- `trunkLean` = 어깨 중점→엉덩이 중점 벡터와 수직선 사이 각도(0° = 꼿꼿이 섬).
- `hipDrop` = 서 있을 때 기준 엉덩이 높이 대비 엉덩이가 내려간 거리 ÷ 기준 다리 길이(엉덩이–발목). 정면 촬영 보조 지표.
- `kneeAsymmetry` = |왼쪽 kneeAngle − 오른쪽 kneeAngle|.

### 4.2 측면 선택

핵심 관절(엉덩이, 무릎, 발목)의 visibility가 양쪽 모두 `min_visibility` 이상이면 두 다리 각도의 평균, 한쪽만 이상이면 그쪽만, 둘 다 미달이면 해당 프레임은 **무효 프레임**. `landmarks`가 null인 프레임도 무효 프레임이다.

### 4.3 필터

- One Euro 필터를 직접 구현한다(외부 라이브러리 금지, 결정적이어야 함). 파라미터 `min_cutoff`, `beta`, `d_cutoff`는 설정 파일에서.
- 필터는 프레임의 `t` 차이로 동작한다(벽시계 사용 금지).
- 무효 프레임이 `filter_reset_gap_ms` 이상 이어지면 필터 상태를 초기화한다.

### 4.4 기준 자세 보정

세션 초반(무작위 동작 확인 이후) 서 있는 구간에서 `calibration_window_ms` 동안 유효 프레임의 kneeAngle이 `stand_angle` 이상이면, 그 구간의 엉덩이 높이와 다리 길이 중앙값을 기준값으로 저장한다. 기준이 잡히기 전에는 hipDrop을 쓰지 않는다.

---

## 5. 렙 판정 상태 머신 (`counters/squat.py`)

### 5.1 상태

`STANDING → DESCENDING → ASCENDING → STANDING`

기준값(설정 파일):
- `descent_start_angle` (가안 160°): 이 아래로 내려가면 하강 시작.
- `attempt_angle` (가안 145°): 이 아래까지 내려가야 "렙 시도"로 본다. 그보다 얕은 움직임은 잡음으로 무시하고 아무것도 기록하지 않는다.
- `depth_accept_angle` (가안 100°): 렙 중 최저 kneeAngle이 이 이하여야 깊이 인정.
- `stand_angle` (가안 160°): kneeAngle이 이 이상이 되면 렙 종료.

깊이 판정 모드 `depth_mode`: `"angle"`(기본) 또는 `"angle_or_hip_drop"`. 후자일 때 hipDrop ≥ `hip_drop_accept`(가안 0.25)이면 각도가 미달이어도 깊이 인정한다(정면 촬영 대응).

### 5.2 전이 규칙

- STANDING: kneeAngle < descent_start_angle → DESCENDING, `startT` = 해당 프레임 t.
- DESCENDING: 최저 각도와 그 시각을 계속 갱신. 각도가 최저값보다 `bottom_hysteresis_deg`(가안 8°) 이상 다시 커지면 → ASCENDING, `bottomT` = 최저 시각.
- ASCENDING: kneeAngle ≥ stand_angle → 렙 종료, `endT` = 해당 프레임 t, STANDING으로. 다시 내려가 최저값을 갱신하면 DESCENDING으로 복귀.
- 하강 시작 후 최저각이 attempt_angle 아래로 한 번도 가지 않고 서면: 렙 기록 없이 STANDING으로.
- 렙 진행 시간이 `max_rep_ms`(가안 10000)를 넘으면 렙을 폐기하고, kneeAngle이 stand_angle 이상이 될 때까지 대기한 뒤 STANDING으로.

### 5.3 미인정 사유 (우선순위 순서로 하나만 부여)

1. `OUT_OF_FRAME`: 렙 구간(startT~endT) 중 무효 프레임 비율 > `max_invalid_ratio_in_rep`(가안 0.2), 또는 연속 무효 구간 > `max_gap_in_rep_ms`(가안 1000). 연속 무효 구간이 이 값을 넘는 순간 렙을 즉시 OUT_OF_FRAME으로 종료한다(endT = 마지막 유효 프레임 t).
2. `TOO_FAST`: endT − startT < `min_rep_ms`(가안 800), 또는 하강 시간(bottomT − startT) < `min_descent_ms`(가안 300).
3. `SHALLOW_DEPTH`: 깊이 인정 조건 미충족.

사유가 없으면 `accepted = true`.

### 5.4 출력

```text
RepEvent {
  index: int             # 1부터, 시도로 기록된 모든 렙(인정+미인정)에 부여
  startT: int, bottomT: int, endT: int
  accepted: bool
  reason: "SHALLOW_DEPTH" | "TOO_FAST" | "OUT_OF_FRAME" | null
  minKneeAngle: float, maxHipDrop: float | null
  trunkLeanAtBottom: float, kneeAsymmetryAtBottom: float
  invalidRatio: float
}
```

판정기는 `update(frame_features) -> list[RepEvent]` 스트리밍 인터페이스와, 실시간 UI용 `state`, `current_angle`, `accepted_count` 속성을 제공한다. 배치 처리는 스트리밍을 반복 호출하는 것으로만 구현해서 두 경로의 결과가 절대 달라지지 않게 한다.

---

## 6. 무작위 동작 확인 (`liveness.py`)

### 6.1 동작 종류

`RAISE_LEFT_HAND`, `RAISE_RIGHT_HAND`, `RAISE_BOTH_HANDS`. 지시 문구(한국어)도 상수로 둔다 (예: "왼손을 머리 위로 들어 주세요").

동작 선택 함수 `issue_challenge()`는 `secrets` 모듈로 무작위 선택한다. 판정 함수와 분리해서, 판정은 결정적으로 유지한다.

### 6.2 판정

- "손을 들었다" = 손목 y(픽셀)가 코 y보다 `hand_above_head_margin` × 어깨 너비(픽셀) 이상 위, 그리고 손목 visibility ≥ `min_visibility`.
- 지시된 조건이 `liveness_hold_ms`(가안 1000) 이상 연속 유지되면 PASSED.
- 반대 손만 든 상태는 통과로 치지 않는다(계속 대기). 반대 손을 `wrong_hand_hold_ms` 이상 든 경우는 결과의 `evidence`에 기록한다. `RAISE_LEFT_HAND` 지시에 양손을 들면 통과로 본다.
- `expiresAtT`까지 통과하지 못하면 EXPIRED, 해당 구간의 유효 프레임 비율이 0.3 미만이면 FAILED_NO_PERSON.

```text
LivenessResult {
  challengeId: str, action: str
  status: "PASSED" | "EXPIRED" | "FAILED_NO_PERSON"
  passedAtT: int | null
  evidence: { maxHoldMs: int, wrongHandMaxHoldMs: int, validFrameRatio: float }
}
```

실패 시 세션을 재시작할지(정책 A) 제출은 허용하고 자동 승인만 막을지는 기획 미정이므로, 엔진은 결과만 내고 정책은 `recount.py`의 설정값 `liveness_policy: "restart" | "review"`로 분기한다.

---

## 7. 확신도 (`confidence.py`)

### 7.1 원시 점수

세션의 "활성 구간"(liveness 통과 시각, 없으면 첫 프레임 ~ 마지막 렙 endT, 렙이 없으면 마지막 프레임)에 대해 다음을 0~1로 계산한다.
- `c_vis`: 유효 프레임의 핵심 관절 평균 visibility
- `c_valid`: 유효 프레임 비율
- `c_track`: 1 − (무효 연속 구간 총 시간 / 활성 구간 시간)
- `c_consistency`: 인정 렙들의 렙 시간 변동계수(CV)와 최저 각도 표준편차를 각각 `exp(-k·x)` 형태로 0~1로 바꿔 평균(k는 설정값). 인정 렙이 3개 미만이면 0.5.
- `c_unaccepted`: 1 − (시도 렙 중 OUT_OF_FRAME 비율). 시도 렙이 0개면 0.5.

`raw = Σ wᵢ·cᵢ` (가중치는 설정 파일, 합 1이 아니면 로드 실패). liveness가 PASSED가 아니면 `raw`에 `liveness_penalty`(가안 0.5)를 곱한다.

### 7.2 보정

`raw`를 그대로 내보내지 않는다. 설정 파일의 `confidence.calibration` 구간 선형 매핑(점 목록 `[[raw, calibrated], ...]`, raw 오름차순)을 적용해 최종 `aiConfidence`를 낸다. 초기값은 항등 매핑 `[[0,0],[1,1]]`.

`tools/calibrate_confidence.py`가 정답 라벨 데이터로 "렙 수를 정확히 맞혔는가(0/1)"를 타깃으로 isotonic regression을 학습해 이 점 목록을 생성한다. 즉 보정 후 0.9는 "이 확신도의 세션은 약 90% 확률로 렙 수가 정확하다"는 의미가 되어야 한다.

결과에 원시 점수 구성요소를 모두 포함해서(디버깅·검수용) 반환한다.

---

## 8. 자세 요약·오류 태그·이상 징후

### 8.1 poseSummary (`summary.py`, L4 입력)

인정된 렙의 최저점 기준:
```text
poseSummary {
  kneeFlexionDeg: { avg, min, max }      # 180 − minKneeAngle
  trunkLeanDeg: { avg, max }
  kneeAsymmetryDeg: { avg }
  repDurationMs: { avg, std }
  depthConsistencyDeg: float              # 최저각 표준편차
  formTags: FormTag[]
}
```
소수점 1자리 반올림. 인정 렙이 0개면 수치 필드는 null.

### 8.2 자세 오류 태그 (LLM이 수치 없이도 코멘트할 수 있게)

설정 가능한 기준으로 다음 태그를 부여:
- `SHALLOW_DEPTH_FREQUENT`: 시도 렙 중 SHALLOW_DEPTH 비율 > 0.3
- `DEPTH_INCONSISTENT`: depthConsistencyDeg > 12
- `TRUNK_LEAN_EXCESSIVE`: trunkLean 평균 > 45
- `KNEE_ASYMMETRY`: kneeAsymmetry 평균 > 15
- `TEMPO_TOO_FAST`: TOO_FAST 비율 > 0.2
- `FREQUENT_OUT_OF_FRAME`: OUT_OF_FRAME 비율 > 0.2

### 8.3 이상 징후 (`anomaly.py`, L2 입력)

규칙 기반으로 다음을 탐지하고 `{ code, severity: "LOW"|"MEDIUM"|"HIGH", detail }` 목록을 낸다. 기준값은 설정 파일 `anomaly` 섹션에 둔다.
- `REP_TIMING_TOO_REGULAR` (HIGH): 인정 렙 5개 이상이고 렙 시간 표준편차 < 40ms (재생·매크로 의심)
- `LANDMARKS_FROZEN` (HIGH): 유효 프레임에서 관절 좌표 변화량이 거의 0인 구간 > 2000ms
- `ZERO_JITTER` (MEDIUM): 정지 구간의 미세 떨림이 비현실적으로 0에 가까움
- `BODY_PROPORTION_SHIFT` (HIGH): 세션 중 상체/하체 길이 비율이 기준 대비 20% 이상 변함 (사람 교체 의심)
- `MULTIPLE_RESETS` (LOW): 1초 이상 무효 구간 후 재등장이 3회 이상
- `UNREALISTIC_PACE` (MEDIUM): 인정 렙 평균 시간 < 1000ms

---

## 9. 서버 재계산·자동 승인·내부 API

### 9.1 세션 실행기 (`session.py`)

`run_session(meta, chunks, config) -> SessionResult`:
1. 청크 완결성 검사: seq가 0..N−1로 빠짐없이 있어야 함. 빠지면 `MissingChunksError(missing_seq=[...])`.
2. 프레임을 t 순으로 이어 붙이고 3.2 규칙 검증.
3. `catalogVersion`에 해당하는 설정 파일 로드(없으면 에러). 세션 도중 기준값이 바뀌지 않는다.
4. 특징 추출 → liveness 판정(구간: issuedAtT~expiresAtT) → 렙 판정(liveness 통과 이후 구간, liveness가 없으면 전체) → 확신도 → 요약 → 이상 징후.

```text
SessionResult {
  engineVersion: str, catalogVersion: str
  reps: RepEvent[]
  recognizedReps: int          # accepted 개수
  attemptedReps: int
  liveness: LivenessResult | null
  aiConfidence: float, confidenceComponents: {...}
  poseSummary: {...}
  anomalies: [...]
}
```

### 9.2 재계산 비교 (`recount.py`)

입력: `SessionResult`(서버 계산) + 클라이언트 제출값(API-026: `clientRepCount`, `reps[]`, `aiConfidence`, `poseSummary`) + 선택 `userReducedCount`.

- `mismatch = |server − client| / max(client, 1) > recount_tolerance` (가안 0.10) → `SERVER_RECOUNT_MISMATCH`.
- 렙 단위 대조: 서버/클라이언트 렙을 시간 겹침(IoU ≥ 0.5)으로 매칭해 `matchedReps`, `clientOnlyReps`, `serverOnlyReps`, `acceptedDisagreements`를 보고.
- **인정량은 항상 서버 값**이다. 클라이언트가 더 많이 주장해도 서버 값을 넘을 수 없다.
- R12: 사용자는 횟수를 줄일 수만 있다. `userReducedCount`가 서버 인정량보다 크면 거부(`INVALID_REDUCTION`), 작거나 같으면 그 값을 최종 인정량으로.
- **확신도도 서버 값으로 판정한다.** 클라이언트 `aiConfidence`는 기록·비교용으로만 쓴다(조작 가능하므로). 차이가 `confidence_diff_warn`(가안 0.15) 이상이면 이상 징후 `CLIENT_CONFIDENCE_DIVERGENCE`(MEDIUM) 추가.

### 9.3 자동 승인 판정

`decide_approval(result, comparison, config) -> ApprovalDecision`:
- liveness 미통과이고 `liveness_policy == "restart"`면 REJECT_RESTART.
- AUTO_APPROVE: 서버 aiConfidence ≥ `auto_approve_threshold`(가안 0.90) 그리고 liveness PASSED 그리고 mismatch 없음 그리고 severity HIGH 이상 징후 없음.
- 그 외: HUMAN_REVIEW, 사유 코드 목록 포함 (`LOW_CONFIDENCE`, `LIVENESS_NOT_PASSED`, `RECOUNT_MISMATCH`, `ANOMALY_HIGH`).

결과에 `approvalPath`("AUTO" | "HUMAN_REVIEW" | "RESTART")와 판단 근거 수치를 모두 넣는다.

### 9.4 내부 API (`service/app.py`, FastAPI)

백엔드 서버가 호출하는 내부 서비스다. 인증은 `X-Internal-Token` 헤더를 환경변수 `AI_INTERNAL_TOKEN`과 비교한다(불일치·누락 시 401). 기존 `backend/`에 AI 호출 계약이 있으면 그것을 우선한다.
- `GET /internal/health` → `{ status, engineVersion, catalogVersions: [...] }` (토큰 불필요)
- `POST /internal/recount` → body: `{ meta, chunks, client: {clientRepCount, reps, aiConfidence, poseSummary}, userReducedCount? }` → `{ result: SessionResult, comparison, decision }`
- `POST /internal/liveness/evaluate` → body: `{ meta, frames }` → `LivenessResult`
- `POST /internal/liveness/issue` → `{ action, instruction, challengeId }`
- 에러는 API 명세 형식 `{ code, message, details }`로: `VALIDATION_FAILED`(details.missingSeq 포함)는 400. `SERVER_RECOUNT_MISMATCH`는 HTTP 200으로 comparison에 담아 반환하고 최종 에러 처리는 백엔드가 하게 한다.
- 요청 하나당 처리 시간을 로그로 남긴다. 10분 세션(15fps, 9000프레임) 재계산이 1초 안에 끝나야 한다.

---

## 10. 개발 도구 (`tools/`)

모든 도구는 `argparse` CLI, `--help` 지원, `cd ai && python -m tools.<이름>`으로 실행 가능해야 하고, PyCharm Run Configuration(Working directory: `ai/`) 예시를 README에 적는다.

1. `download_models.py`: MediaPipe Pose Landmarker `lite`, `full`, `heavy` `.task` 파일을 `models/`에 받는다. URL은 MediaPipe 공식 문서에서 확인한 최신 경로를 쓰고, 이미 있으면 건너뛴다.
2. `extract_keypoints.py`: 영상(또는 폴더) → 세션 JSON. MediaPipe Tasks API `PoseLandmarker`(VIDEO 모드) 사용, `--model lite|full|heavy`, `--fps 15`로 다운샘플링, `--mirrored` 옵션, 결과를 3.2 스키마의 `SessionMeta` + `Chunk[]`(300프레임 단위)로 `data/keypoints/`에 저장. 청크 크기 제한 검사 포함. 사람이 여러 명이면 첫 번째 사람만.
3. `webcam_demo.py`: 웹캠 실시간 데모. 화면에 스켈레톤, 현재 kneeAngle, 상태, 인정/미인정 카운트, 마지막 미인정 사유, 실시간 각도 그래프(최근 5초), FPS 표시. 키: `L` liveness 모드 시작(무작위 동작 지시 후 판정 결과 표시), `R` 리셋, `S` 현재 세션을 JSON으로 저장, `Q` 종료. **판정은 반드시 `rep_engine`을 그대로 호출**한다(데모 전용 로직 금지).
4. `plot_session.py`: 세션 JSON → kneeAngle 시계열 그래프 PNG. 기준선, 렙 구간 음영(인정 초록/미인정 빨강 + 사유 라벨), 무효 프레임 구간 회색.
5. `evaluate.py`: `data/labels.csv`의 모든 세션 평가. 지표: 세션 정확 일치율, 평균 절대 오차, 사유별 정밀도/재현율(라벨에 있을 때), 촬영 각도·거리별 분해. 결과를 콘솔 표 + `reports/eval_<날짜>.md` + CSV로 저장. `--config`로 다른 카탈로그 비교 가능.
6. `compare_models.py`: 같은 영상에 lite/full/heavy로 추출·평가해 정확도와 프레임당 추론 시간(ms) 비교표 출력.
7. `calibrate_confidence.py`: 평가 결과로 isotonic 보정 학습 → 7.2의 점 목록 출력, 보정 전후 신뢰도 곡선(reliability diagram) PNG, 기준값 0.80~0.95 각각에서 "자동 승인 비율 / 자동 승인 중 오류율" 표.
8. `angle_study.py`: labels.csv의 `view`, `distance` 열 기준으로 촬영 조건별 정확도를 비교해 권장 촬영 각도 근거 리포트 생성 (JN-012 튜토리얼 문구 근거).
9. `make_test_vectors.py`: 합성 + 실제 세션 일부로 `test_vectors/*.json` 생성. 각 파일 = `{ meta, chunks, expected: SessionResult }`. 모바일 팀이 자기 구현 결과와 비교할 수 있게 README에 비교 규칙(렙 수·사유는 정확 일치, 시각은 ±1프레임 허용) 작성.

`data/labels.csv` 열: `session_file, view(front|diag45|side), distance(near|far), subject, expected_accepted, expected_shallow, expected_too_fast, expected_out_of_frame, notes`.

---

## 11. 설정 파일 (`config/catalog/cat_2026-11-01.yaml`)

모든 기준값은 코드에 하드코딩하지 않고 여기서 읽는다. pydantic으로 스키마 검증하고 누락·범위 오류 시 로드 실패시킨다.

```yaml
catalog_version: cat_2026-11-01
exercise: SQUAT
features:
  min_visibility: 0.5
  one_euro: { min_cutoff: 1.0, beta: 0.05, d_cutoff: 1.0 }
  filter_reset_gap_ms: 500
  calibration_window_ms: 1000
squat:
  descent_start_angle: 160
  attempt_angle: 145
  depth_accept_angle: 100
  stand_angle: 160
  bottom_hysteresis_deg: 8
  depth_mode: angle            # angle | angle_or_hip_drop
  hip_drop_accept: 0.25
  min_rep_ms: 800
  min_descent_ms: 300
  max_rep_ms: 10000
  max_invalid_ratio_in_rep: 0.2
  max_gap_in_rep_ms: 1000
liveness:
  hand_above_head_margin: 0.2
  liveness_hold_ms: 1000
  wrong_hand_hold_ms: 1000
  min_valid_ratio: 0.3
confidence:
  weights: { vis: 0.25, valid: 0.25, track: 0.2, consistency: 0.15, unaccepted: 0.15 }
  consistency_k: { duration_cv: 3.0, depth_std: 0.1 }
  liveness_penalty: 0.5
  calibration: [[0.0, 0.0], [1.0, 1.0]]
form_tags:
  shallow_ratio: 0.3
  depth_std_deg: 12
  trunk_lean_deg: 45
  asymmetry_deg: 15
  too_fast_ratio: 0.2
  out_of_frame_ratio: 0.2
anomaly:
  regular_timing_min_reps: 5
  regular_timing_std_ms: 40
  frozen_ms: 2000
  proportion_shift_ratio: 0.2
  reset_gap_ms: 1000
  reset_count: 3
  min_avg_rep_ms: 1000
recount:
  recount_tolerance: 0.10
  confidence_diff_warn: 0.15
  auto_approve_threshold: 0.90
  liveness_policy: restart      # restart | review
```

---

## 12. 테스트 요구사항 (`tests/`)

실제 데이터가 없어도 모든 로직을 검증할 수 있게 **합성 스쿼트 생성기** `tests/synth.py`를 먼저 만든다. 서 있는 사람의 관절 좌표를 만들고, 무릎 각도를 시간에 따라 바꿔(코사인 곡선 등) 엉덩이·무릎·발목 좌표를 기하학적으로 계산한다. 파라미터: 렙 수, 렙별 최저 각도, 렙 시간, 렙 간 휴식, 가우시안 잡음(시드 고정), 무효 프레임 구간 주입, 손 들기 구간 주입, fps, 미러링, 사람 비율 변경, 이미지 크기.

반드시 포함할 테스트:
- 기하: 알려진 좌표의 각도 계산, 종횡비 보정 유무에 따른 차이
- 필터: 결정성, 리셋 동작
- 정상 10회 → 인정 10
- 최저각 120° 5회 → SHALLOW_DEPTH 5, 인정 0
- 최저각 150°(attempt 미만) 움직임 → 렙 기록 0
- 렙 시간 500ms → TOO_FAST
- 렙 도중 1.5초 무효 → OUT_OF_FRAME
- 사유 우선순위 (얕고 빠르고 가려진 렙 → OUT_OF_FRAME)
- 경계값 부근 ±5° 잡음 → 이중 카운트 없음
- 상승 중 재하강 → 렙 1개로 처리
- max_rep_ms 초과 → 폐기
- 15fps와 30fps 같은 동작 → 같은 렙 수, 시각 차이 ≤ 1프레임
- 같은 입력 2회 실행 → 출력 JSON 바이트 단위 동일
- 스트리밍 경로와 배치 경로 결과 동일
- angle_or_hip_drop 모드에서 정면 촬영 시뮬레이션
- 미러링 플래그 → 좌우 스왑 후 동일 결과
- liveness: 정답 손 통과, 양손 통과, 반대 손만 → 미통과, 유지 시간 부족, 만료, 사람 없음
- 확신도: 0~1 범위, 무효 프레임이 많을수록 감소, liveness 실패 시 패널티, 보정 매핑 적용
- poseSummary 값과 각 formTag 발동 조건
- 각 anomaly 발동/미발동
- 청크: 누락 seq → MissingChunksError에 정확한 목록, 크기 초과, t 역순
- recount: 허용 오차 경계, 클라이언트 과다 주장 시 서버 값 사용, R12 감소 허용·증가 거부, 렙 매칭, 확신도 괴리 경고
- 자동 승인 판정의 모든 분기
- 설정 파일 검증 실패 케이스(가중치 합, 누락 필드, 매핑 순서)
- FastAPI `TestClient`로 모든 엔드포인트 계약(필드명 camelCase, 에러 형식, 토큰 없을 때 401)
- 성능: 9000프레임 세션 run_session < 1초
- 의존성 경계: `rep_engine` 안의 모든 모듈이 mediapipe, cv2를 import하지 않는지 검사

커버리지 목표: `rep_engine` 90% 이상.

---

## 13. 작업 순서와 완료 기준

각 단계 끝에 `cd ai && ruff check && mypy rep_engine && pytest`가 모두 통과해야 다음 단계로 간다.

1. **기반**: 0장의 루트 파일 확인, `ai/` 구조 생성, `ai/CLAUDE.md`(아래 부록 내용), `.gitignore`, requirements 3종, pyproject, README 골격, `schemas.py`, `landmarks.py`, `config.py` + 설정 파일, 스키마·설정 테스트.
2. **특징**: geometry, One Euro 필터, extractor, 측면 선택, 기준 자세 보정, 합성 생성기, 관련 테스트.
3. **판정**: 스쿼트 상태 머신, 미인정 사유, 스트리밍/배치 인터페이스, 12장의 판정 테스트 전부.
4. **무작위 동작 확인**: liveness 모듈과 테스트.
5. **확신도·요약·이상 징후**: confidence, summary, anomaly와 테스트.
6. **세션 실행기·재계산·승인**: session, recount, 승인 판정과 테스트.
7. **내부 API·배포**: FastAPI 앱, API 계약 테스트, 성능 테스트, `Dockerfile`, `.dockerignore`, 루트 `docker-compose.yml`에 ai 블록 추가, 루트 `.github/workflows/ai-ci.yml` 추가.
8. **도구**: download_models → extract_keypoints → webcam_demo → plot_session → evaluate → compare_models → calibrate_confidence → angle_study → make_test_vectors. 각 도구는 합성 데이터 또는 샘플 영상 1개로 실행 확인. 실데이터가 없으면 합성 세션 JSON을 `data/keypoints/sample/`에 만들고 그에 맞는 `data/labels.csv` 샘플 행을 넣어 evaluate·calibrate가 끝까지 돌아가는지 확인한다.
9. **문서**: `ai/README.md` 완성(설치, PyCharm 설정, 각 도구 사용 예시, 도커 실행, 백엔드 호출 예시, 데이터 수집 가이드: 촬영 조건 조합 정면/45°/측면 × 가까이/멀리, 정상·반쪽·빠른 반복·화면 이탈 포함, labels.csv 작성법), 루트 `README.md`에 링크 한 줄 추가, `ai/docs/DECISIONS.md` 완성.

`ai/docs/DECISIONS.md`에 최소한 다음을 "팀 합의 필요" 항목으로 기록한다: 좌표 좌우·미러링 규칙, kneeFlexionDeg 정의, 서버 확신도 사용(클라이언트 값 불신), 재계산 허용 오차, 인정 깊이 기준값, liveness 실패 정책, 자동 승인 기준 0.90의 보정 근거, formTag 추가에 따른 poseSummary 확장, ai 서비스 포트, 루트 규칙과의 충돌 사항.

**완료 기준**: 위 9단계가 모두 끝나고, `cd ai && pytest` 전부 통과(커버리지 90% 이상), 웹캠 데모에서 실제로 스쿼트를 세며, 영상 1개를 extract → evaluate → plot까지 돌릴 수 있고, `ai/test_vectors/`가 생성되어 있고, `docker compose up ai` 후 `GET /internal/health`가 응답하는 상태. `ai/` 밖에서 변경한 파일은 0장의 허용 목록에 있는 것뿐이어야 한다.

### 코딩 규칙

- 모든 함수에 타입 힌트, 공개 함수에 docstring(한국어 가능). 단위(도, ms, 픽셀)를 변수명이나 docstring에 명시.
- 핵심 엔진에 전역 상태, 벽시계(`time.time` 등), 무작위성 금지(liveness 동작 발급 제외).
- 매직 넘버 금지. 기준값은 전부 설정 파일.
- 부동소수 결과는 출력 시 일관되게 반올림(각도 소수 1자리, 확신도 소수 3자리).
- `print` 대신 `logging`, 출력은 표준 출력.
- 모바일 포팅을 고려해 상태 머신은 단순한 if/else와 숫자 연산만으로 작성하고, numpy 고급 기능에 의존하지 않는다.

### 최종 보고

작업을 마치면 다음을 보고하라: 구현한 내용 요약, 테스트 결과(통과 수, 커버리지), `ai/` 밖에서 변경한 파일 목록, 루트·backend·mobile에 필요하다고 판단했지만 하지 않은 변경 제안, 남은 미정 사항.

---

## 부록: `ai/CLAUDE.md`에 넣을 내용

```markdown
# ai/ 작업 규칙

- 이 디렉터리는 전운시 AI 렙 판정 엔진이다. 전체 명세는 `ai/SPEC.md`를 따른다.
- 모든 명령은 `ai/`에서 실행한다. 가상환경은 `ai/.venv`.
- `ai/` 밖은 SPEC.md 0장의 허용 목록 외에는 수정하지 않는다.
- `rep_engine/`은 numpy, pydantic, pyyaml만 import한다. mediapipe, opencv는 `tools/`에서만.
- 기준값은 `config/catalog/*.yaml`에만 둔다. 코드에 매직 넘버 금지.
- 엔진은 결정적이어야 한다: 벽시계, 무작위성, 전역 상태 금지.
- 변경 후 반드시 `ruff check && mypy rep_engine && pytest` 통과.
- 팀 합의가 필요한 결정은 `docs/DECISIONS.md`에 기록한다.
```
