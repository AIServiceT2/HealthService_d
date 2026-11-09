"""실데이터가 없을 때 평가 도구를 끝까지 돌려 보기 위한 **합성** 세션과 라벨을 만든다.

- 세션: data/keypoints/sample/syn_XXX.json
- 라벨: data/labels_sample.csv (실데이터용 data/labels.csv와 섞지 않음, DECISIONS D-52)

라벨은 엔진 출력이 아니라 **생성 의도**로 붙인다: 정상 렙(최저 72~95°, 1.7~2.6초) → 인정,
얕은 렙(112~135°) → SHALLOW, 빠른 렙(0.45~0.65초) → TOO_FAST, 바닥을 1.5초 가린 렙 → OUT_OF_FRAME.
그래서 정면·45° 촬영처럼 엔진이 틀리는 경우가 실제로 생긴다. 숫자는 실측이 아니다.

    python -m tools.make_sample_data --n 40
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

from rep_engine.schemas import LivenessAction
from tools.common import DATA_DIR, save_session, setup_logging, split_chunks
from tools.synth import RepSpec, SynthConfig, View, challenge, rep_windows, synth_frames, synth_meta

LABEL_FIELDS = [
    "session_file",
    "view",
    "distance",
    "subject",
    "expected_accepted",
    "expected_shallow",
    "expected_too_fast",
    "expected_out_of_frame",
    "notes",
]
DISTANCE_SCALE = {"near": 0.5, "far": 0.25}
VIEWS: tuple[View, ...] = ("side", "diag45", "front")


def make_session(i: int, seed: int) -> tuple[SynthConfig, dict[str, object]]:
    rng = random.Random(seed * 1000 + i)
    view = VIEWS[i % len(VIEWS)]
    distance = "near" if (i // len(VIEWS)) % 2 == 0 else "far"
    kinds = (
        ["ok"] * rng.randint(4, 10)
        + ["shallow"] * rng.randint(0, 3)
        + ["fast"] * rng.randint(0, 2)
        + ["oof"] * rng.randint(0, 2)
    )
    rng.shuffle(kinds)
    reps: list[RepSpec] = []
    for k in kinds:
        rest = rng.randint(600, 1400)
        if k == "ok":
            reps.append(RepSpec(rng.uniform(72, 95), rng.randint(1700, 2600), rest))
        elif k == "shallow":
            reps.append(RepSpec(rng.uniform(112, 135), rng.randint(1800, 2400), rest))
        elif k == "fast":
            reps.append(RepSpec(rng.uniform(80, 90), rng.randint(450, 650), rest))
        else:
            reps.append(RepSpec(rng.uniform(75, 90), 2600, rest))
    sc = SynthConfig(
        reps=reps,
        view=view,
        person_scale=DISTANCE_SCALE[distance],
        noise_px=rng.uniform(1.0, 5.0),
        seed=seed * 1000 + i,
        lead_in_ms=4000,
        hand_raises=[(500, 2000, "LEFT")],
        session_id=f"syn_{i:03d}",
        liveness=challenge(LivenessAction.RAISE_LEFT_HAND, 0, 3000),
    )
    sc.invalid_ranges = [
        (start + 500, start + 2000)
        for (start, _, _), k in zip(rep_windows(sc), kinds, strict=True)
        if k == "oof"
    ]
    label: dict[str, object] = {
        "view": view,
        "distance": distance,
        "subject": "synthetic",
        "expected_accepted": kinds.count("ok"),
        "expected_shallow": kinds.count("shallow"),
        "expected_too_fast": kinds.count("fast"),
        "expected_out_of_frame": kinds.count("oof"),
        "notes": f"합성(실측 아님) seed={sc.seed} noise={sc.noise_px:.1f}px",
    }
    return sc, label


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="합성 샘플 세션·라벨 생성 (실데이터 아님)")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--out", type=Path, default=DATA_DIR / "keypoints" / "sample")
    p.add_argument("--labels", type=Path, default=DATA_DIR / "labels_sample.csv")
    a = p.parse_args(argv)
    log = setup_logging()
    rows = []
    for i in range(a.n):
        sc, label = make_session(i, a.seed)
        path = a.out / f"{sc.session_id}.json"
        save_session(path, synth_meta(sc), split_chunks(sc.session_id, synth_frames(sc)))
        rows.append({"session_file": path.relative_to(a.labels.parent).as_posix(), **label})
    a.labels.parent.mkdir(parents=True, exist_ok=True)
    with a.labels.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    log.info("합성 세션 %d개 → %s, 라벨 → %s", a.n, a.out, a.labels)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
