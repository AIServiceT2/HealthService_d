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
| `tests/synth.py` | 합성 스쿼트 생성기 (측면·정면, MediaPipe·MoveNet, 잡음·가림·손 들기) |
