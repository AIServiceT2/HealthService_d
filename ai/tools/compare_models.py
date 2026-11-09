"""같은 영상을 MediaPipe lite/full/heavy로 추출·판정해 정확도와 프레임당 추론 시간을 비교한다.

    python -m tools.compare_models data/videos/squat01.mp4 --labels data/labels.csv

라벨 CSV에서 `session_file`의 파일 이름(확장자 제외)이 영상 이름과 같은 행을 정답으로 쓴다.
정답이 없으면 정확도 열은 비운다. 결과: 콘솔 표 + reports/compare_models_<날짜>.md
MoveNet 추출은 아직 없다 (DECISIONS D-51).
"""

from __future__ import annotations

import argparse
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from rep_engine.config import load_catalog
from rep_engine.session import run_frames
from tools.common import REPORTS_DIR, setup_logging
from tools.download_models import VARIANTS
from tools.evaluate import LabelRow, load_labels
from tools.extract_keypoints import DEFAULT_CATALOG, extract, videos_in

P95 = 0.95


@dataclass
class ModelRun:
    video: str
    model: str
    frames: int
    detected: int
    avg_ms: float
    p95_ms: float
    recognized: int
    expected: int | None
    confidence: float


def percentile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def compare(
    video: Path, models: list[str], fps: int, catalog: str, labels: dict[str, LabelRow]
) -> list[ModelRun]:
    cat = load_catalog(catalog)
    label = labels.get(video.stem)
    out: list[ModelRun] = []
    for m in models:
        ex = extract(video, m, fps, catalog_version=catalog)
        res = run_frames(ex.meta, ex.frames, cat)
        out.append(
            ModelRun(
                video=video.name,
                model=m,
                frames=len(ex.frames),
                detected=sum(f.landmarks is not None for f in ex.frames),
                avg_ms=sum(ex.infer_ms) / len(ex.infer_ms),
                p95_ms=percentile(ex.infer_ms, P95),
                recognized=res.recognized_reps,
                expected=label.expected_accepted if label else None,
                confidence=res.ai_confidence,
            )
        )
    return out


def report(runs: list[ModelRun]) -> str:
    lines = [
        f"# 자세 모델 비교 ({dt.date.today().isoformat()})",
        "",
        "| 영상 | 모델 | 프레임 | 사람 검출 | 추론 평균 ms | 추론 p95 ms "
        "| 인정 렙 | 정답 | 오차 | 확신도 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in runs:
        err = "-" if r.expected is None else str(abs(r.recognized - r.expected))
        exp = "-" if r.expected is None else str(r.expected)
        lines.append(
            f"| {r.video} | {r.model} | {r.frames} | {r.detected} | {r.avg_ms:.1f} | "
            f"{r.p95_ms:.1f} | {r.recognized} | {exp} | {err} | {r.confidence:.3f} |"
        )
    lines.append("")
    lines.append("추론 시간은 이 도구를 실행한 PC 기준이다. 폰에서의 속도가 아니다.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="MediaPipe lite/full/heavy 비교")
    p.add_argument("input", type=Path, help="영상 파일 또는 폴더")
    p.add_argument("--models", nargs="+", choices=VARIANTS, default=list(VARIANTS))
    p.add_argument("--fps", type=int, default=15)
    p.add_argument("--catalog", default=DEFAULT_CATALOG)
    p.add_argument("--labels", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    a = p.parse_args(argv)
    log = setup_logging()
    labels = {Path(r.session_file).stem: r for r in load_labels(a.labels)} if a.labels else {}
    runs = [r for v in videos_in(a.input) for r in compare(v, a.models, a.fps, a.catalog, labels)]
    md = report(runs)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"compare_models_{dt.date.today().isoformat()}.md"
    out.write_text(md, encoding="utf-8")
    print(md)  # noqa: T201
    log.info("저장: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
