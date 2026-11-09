# 테스트 벡터 (모바일 팀 공유용)

Python 엔진 `rep_engine`(정답 구현)이 만든 입력·기대 결과 쌍입니다. 모바일 구현이 같은 입력에서 같은 판정을 내는지 확인할 때 씁니다.

- 만든 도구: `python -m tools.make_test_vectors` (ai/에서)
- 목록: [`index.json`](index.json) (엔진 버전, 벡터별 인정·시도 렙 수, 확신도)
- 지금 있는 벡터는 모두 **합성 데이터**입니다(`description`이 `[합성]`으로 시작). 실제 촬영 세션은 아직 없습니다.

## 파일 형식

```json
{
  "meta": { "sessionId": "...", "catalogVersion": "cat_2026-11-01", "device": { "modelVersion": "mediapipe-pose-full@0.10" }, "...": "..." },
  "chunks": [ { "sessionId": "...", "seq": 0, "frames": [ { "t": 0, "landmarks": [ null, "...", { "x": 0.5, "y": 0.5, "z": 0.0, "visibility": 0.9 } ] } ] } ],
  "description": "[합성] ...",
  "expected": { "reps": [], "recognizedReps": 4, "liveness": {}, "aiConfidence": 0.925, "poseSummary": {}, "anomalies": [] }
}
```

- `landmarks`는 모델 원본 순서입니다(MediaPipe 33 / MoveNet 17). 얼굴 인덱스는 항상 null입니다.
- 좌표는 소수 5자리, 가시도는 3자리로 반올림돼 있습니다. `expected`는 **반올림된 입력**으로 계산했습니다.

## 비교 규칙

| 항목 | 규칙 |
| --- | --- |
| `recognizedReps`, `attemptedReps` | 정확히 일치 |
| 렙별 `accepted`, `reason` | 순서대로 정확히 일치 |
| 렙별 `startT`, `bottomT`, `endT` | ±1프레임 (15fps면 ±67ms) |
| `liveness.status` | 정확히 일치. `passedAtT`는 ±1프레임 |
| 각도 값(`minKneeAngle` 등, 도) | ±1.0° (필터 구현 차이 허용) — 제안값, 모바일 팀과 합의 필요 |
| `aiConfidence` | ±0.01 — 제안값, 합의 필요 (승인 판단은 서버 값만 씀, DECISIONS D-36) |
| `poseSummary.formTags`, `anomalies[].code` | 집합이 같음 |

반올림은 0.5 올림(half-up)입니다(DECISIONS D-20). 시각 비교에 ±1프레임을 허용하는 이유는 필터(One Euro)의 부동소수 계산 순서가 플랫폼마다 조금 다를 수 있어서입니다.

## 주의

- 엔진이나 카탈로그가 바뀌면 벡터를 다시 만들어야 합니다. `tests/test_vectors.py`가 어긋남을 잡습니다.
- `09_front_view`는 인정 0인데 확신도가 0.9입니다. 엔진의 현재 한계를 보여 주는 벡터입니다(DECISIONS D-54).
