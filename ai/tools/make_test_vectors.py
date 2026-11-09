"""모바일 팀 공유용 테스트 벡터 생성.

test_vectors/<이름>.json = {meta, chunks, expected, description}

- 합성 시나리오(정상·얕음·빠름·화면 이탈·무작위 동작 실패·미러링·MoveNet 등)를 만든다.
- `--real <세션 JSON>`으로 실제 추출 세션의 앞부분(`--real-seconds`)을 추가할 수 있다.
- 크기를 줄이려고 좌표는 소수 5자리, 가시도는 3자리로 반올림하고, 기대 결과는 **반올림한 입력**으로
  계산한다. 엔진이나 카탈로그가 바뀌면 다시 만들어야 한다 (tests/test_vectors.py가 확인).
- 비교 규칙은 test_vectors/README.md.

    python -m tools.make_test_vectors
    python -m tools.make_test_vectors --real data/keypoints/squat01.json --real-seconds 30
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from rep_engine import ENGINE_VERSION
from rep_engine.schemas import Frame, Landmark, LivenessAction, SessionMeta
from rep_engine.session import run_session
from tools.common import (
    AI_ROOT,
    all_frames,
    load_session,
    save_session,
    setup_logging,
    split_chunks,
)
from tools.synth import RepSpec, SynthConfig, challenge, rep_windows, synth_frames, synth_meta

OUT_DIR = AI_ROOT / "test_vectors"
COORD_DECIMALS = 5
VIS_DECIMALS = 3
MS_PER_S = 1000


def _live(**kw: object) -> SynthConfig:
    base: dict[str, object] = {
        "lead_in_ms": 3500,
        "tail_ms": 1000,
        "noise_px": 1.5,
        "hand_raises": [(500, 1900, "LEFT")],
        "liveness": challenge(LivenessAction.RAISE_LEFT_HAND, 0, 3000),
    }
    base.update(kw)
    return SynthConfig(**base)  # type: ignore[arg-type]


def _reps(*specs: tuple[float, int]) -> list[RepSpec]:
    return [
        RepSpec(bottom_angle=a, duration_ms=d, rest_ms=700 + 90 * i)
        for i, (a, d) in enumerate(specs)
    ]


NORMAL = _reps((82, 2000), (90, 2300), (78, 1800), (88, 2500))


def scenarios() -> list[tuple[str, str, SynthConfig]]:
    oof = _live(reps=_reps((85, 2600), (84, 2200)), seed=5)
    start, _, _ = rep_windows(oof)[0]
    oof.invalid_ranges = [(start + 900, start + 2200)]
    return [
        ("01_normal_mediapipe", "측면 정상 4렙, 무작위 동작 통과", _live(reps=NORMAL, seed=1)),
        (
            "02_normal_movenet",
            "01과 같은 동작, MoveNet 17개 형식",
            _live(reps=NORMAL, seed=1, model="movenet"),
        ),
        (
            "03_mirrored",
            "01과 같은 동작, 미러링된 좌표 + mirrored=true",
            _live(reps=NORMAL, seed=1, mirrored=True),
        ),
        (
            "04_shallow_fast",
            "얕은 렙 2, 빠른 렙 1, 정상 1",
            _live(reps=_reps((120, 2000), (88, 550), (125, 2100), (85, 2200)), seed=2),
        ),
        ("05_out_of_frame", "첫 렙 바닥이 1.3초 가려짐", oof),
        (
            "06_liveness_expired",
            "손을 들지 않아 무작위 동작 만료",
            _live(reps=NORMAL[:2], seed=3, hand_raises=[]),
        ),
        (
            "07_liveness_wrong_hand",
            "왼손 지시에 오른손만 듦",
            _live(reps=NORMAL[:2], seed=4, hand_raises=[(500, 1900, "RIGHT")]),
        ),
        (
            "08_boundary_depth",
            "최저각이 깊이 기준(100°) 근처",
            _live(reps=_reps((98, 2100), (103, 2000), (100, 2300)), seed=6, noise_px=3.0),
        ),
        (
            "09_front_view",
            "정면 촬영 (각도 모드에서 얕음 판정)",
            _live(reps=NORMAL[:3], seed=7, view="front"),
        ),
        (
            "10_no_liveness_far",
            "무작위 동작 없음, 멀리서 촬영",
            SynthConfig(reps=NORMAL, seed=8, noise_px=2.0, person_scale=0.25),
        ),
    ]


def round_frames(frames: Sequence[Frame]) -> list[Frame]:
    out: list[Frame] = []
    for f in frames:
        if f.landmarks is None:
            out.append(f)
            continue
        out.append(
            Frame(
                t=f.t,
                landmarks=[
                    None
                    if lm is None
                    else Landmark(
                        x=round(lm.x, COORD_DECIMALS),
                        y=round(lm.y, COORD_DECIMALS),
                        z=None if lm.z is None else round(lm.z, COORD_DECIMALS),
                        visibility=round(lm.visibility, VIS_DECIMALS),
                    )
                    for lm in f.landmarks
                ],
            )
        )
    return out


def write_vector(
    name: str, description: str, meta: SessionMeta, frames: Sequence[Frame], out_dir: Path
) -> dict[str, object]:
    chunks = split_chunks(meta.session_id, round_frames(frames))
    expected = run_session(meta, chunks)
    save_session(
        out_dir / f"{name}.json",
        meta,
        chunks,
        {"description": description, "expected": expected.to_dict()},
    )
    return {
        "name": name,
        "description": description,
        "frames": len(frames),
        "recognizedReps": expected.recognized_reps,
        "attemptedReps": expected.attempted_reps,
        "aiConfidence": expected.ai_confidence,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="모바일 팀 공유용 테스트 벡터 생성")
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--real", type=Path, nargs="*", default=[], help="실제 세션 JSON (선택)")
    p.add_argument("--real-seconds", type=int, default=30)
    a = p.parse_args(argv)
    log = setup_logging()
    index: list[dict[str, object]] = []
    for name, desc, sc in scenarios():
        sc.session_id = name
        index.append(write_vector(name, f"[합성] {desc}", synth_meta(sc), synth_frames(sc), a.out))
    for path in a.real:
        meta, chunks, _ = load_session(path)
        limit = a.real_seconds * MS_PER_S
        frames = [f for f in all_frames(chunks) if f.t <= limit]
        index.append(
            write_vector(
                f"real_{path.stem}",
                f"[실제] {path.name} 앞 {a.real_seconds}초",
                meta,
                frames,
                a.out,
            )
        )
    (a.out / "index.json").write_text(
        json.dumps(
            {"engineVersion": ENGINE_VERSION, "vectors": index}, ensure_ascii=False, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    for v in index:
        log.info(
            "%s: 인정 %s / 시도 %s, 확신도 %s",
            v["name"],
            v["recognizedReps"],
            v["attemptedReps"],
            v["aiConfidence"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
