"""확신도 보정 학습 (SPEC 7.2).

평가 결과의 원시 확신도(raw)로 "인정 렙 수를 정확히 맞혔는가(0/1)"를 예측하도록
isotonic regression을 학습해 카탈로그 `confidence.calibration` 점 목록을 만든다.
보정 후 0.9 = "이 확신도의 세션은 약 90% 확률로 렙 수가 정확하다".

출력: 점 목록(YAML), 보정 전후 신뢰도 곡선 PNG, 기준값 0.80~0.95별
"자동 승인 비율 / 자동 승인 중 오류율" 표 → reports/calibration_<날짜>.md

    python -m tools.calibrate_confidence --labels data/labels_sample.csv
    python -m tools.calibrate_confidence --eval-csv reports/eval_2026-11-09.csv

주의: 학습한 데이터로 표를 계산하므로(표본 내 평가) 낙관적이다. 표본이 적으면 과적합된다.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402

from rep_engine.confidence import apply_calibration  # noqa: E402
from rep_engine.config import ConfidenceCfg, load_catalog  # noqa: E402
from rep_engine.rounding import r_ratio  # noqa: E402
from tools.common import REPORTS_DIR, setup_logging  # noqa: E402
from tools.evaluate import run_evaluation  # noqa: E402

THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
N_BINS = 10
DEFAULT_CATALOG = "cat_2026-11-01"


@dataclass
class Sample:
    raw: float
    current: float  # 현재 카탈로그 보정 적용 확신도
    correct: bool
    synthetic: bool


def fit_points(raw: Sequence[float], correct: Sequence[bool]) -> list[tuple[float, float]]:
    """isotonic 학습 → raw 0과 1을 포함하고 raw가 엄격히 증가하는 점 목록 (소수 3자리)."""
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, increasing=True, out_of_bounds="clip")
    iso.fit(np.asarray(raw, dtype=float), np.asarray(correct, dtype=float))
    xs = [0.0, *[float(x) for x in iso.X_thresholds_], 1.0]
    ys = [float(y) for y in iso.predict(np.asarray(xs))]
    points: dict[float, float] = {}
    for x, y in zip(xs, ys, strict=True):
        points[r_ratio(min(1.0, max(0.0, x)))] = r_ratio(y)
    out: list[tuple[float, float]] = []
    best = 0.0
    for x in sorted(points):
        best = max(best, points[x])  # 반올림 뒤에도 감소하지 않게
        out.append((x, best))
    return out


def validate_points(points: list[tuple[float, float]], catalog_version: str) -> None:
    """카탈로그 검증 규칙을 그대로 통과하는지 확인한다."""
    base = load_catalog(catalog_version).base.confidence
    ConfidenceCfg.model_validate({**base.model_dump(), "calibration": points})


def threshold_table(
    conf: Sequence[float], correct: Sequence[bool]
) -> list[tuple[float, float, float | None]]:
    """(기준, 자동 승인 비율, 자동 승인 중 오류율)."""
    rows: list[tuple[float, float, float | None]] = []
    n = len(conf)
    for thr in THRESHOLDS:
        picked = [c for v, c in zip(conf, correct, strict=True) if v >= thr]
        rate = len(picked) / n if n else 0.0
        err = (sum(not c for c in picked) / len(picked)) if picked else None
        rows.append((thr, rate, err))
    return rows


def reliability(ax: plt.Axes, conf: Sequence[float], correct: Sequence[bool], label: str) -> None:
    edges = np.linspace(0.0, 1.0, N_BINS + 1)
    xs, ys = [], []
    for lo, hi in zip(edges, edges[1:], strict=False):
        idx = [i for i, v in enumerate(conf) if lo <= v < hi or (hi == 1.0 and v == 1.0)]
        if idx:
            xs.append(float(np.mean([conf[i] for i in idx])))
            ys.append(float(np.mean([correct[i] for i in idx])))
    ax.plot(xs, ys, marker="o", label=label)


def load_samples(eval_csv: Path | None, labels: Path | None, config: str | None) -> list[Sample]:
    if eval_csv is not None:
        with eval_csv.open(encoding="utf-8") as f:
            return [
                Sample(
                    float(r["raw_confidence"]),
                    float(r["ai_confidence"]),
                    r["exact"] == "True",
                    r.get("subject") == "synthetic",
                )
                for r in csv.DictReader(f)
            ]
    assert labels is not None
    return [
        Sample(e.raw_confidence, e.ai_confidence, e.exact, e.subject == "synthetic")
        for e in run_evaluation(labels, config)
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="확신도 isotonic 보정 학습")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--labels", type=Path, help="라벨 CSV (평가를 직접 실행)")
    src.add_argument("--eval-csv", type=Path, help="tools.evaluate가 만든 CSV")
    p.add_argument("--config", default=None, help="평가에 쓸 카탈로그 (evaluate와 같음)")
    p.add_argument("--catalog", default=DEFAULT_CATALOG, help="검증 기준 카탈로그")
    p.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    a = p.parse_args(argv)
    log = setup_logging()
    samples = load_samples(a.eval_csv, a.labels, a.config)
    if len(samples) < 2 or len({s.correct for s in samples}) < 2:
        log.error("보정하려면 정답·오답 세션이 모두 필요함 (세션 %d개)", len(samples))
        return 1
    raw = [s.raw for s in samples]
    correct = [s.correct for s in samples]
    points = fit_points(raw, correct)
    validate_points(points, a.catalog)
    calibrated = [apply_calibration(x, points) for x in raw]
    current = [s.current for s in samples]

    stamp = dt.date.today().isoformat()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    png = a.out_dir / f"calibration_{stamp}.png"
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], ls="--", color="gray", label="ideal")
    reliability(ax, current, correct, "before (current catalog)")
    reliability(ax, calibrated, correct, "after (isotonic)")
    ax.set_xlabel("confidence")
    ax.set_ylabel("fraction exact")
    ax.legend()
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    plt.close(fig)

    synthetic = all(s.synthetic for s in samples)
    yaml_line = "calibration: [" + ", ".join(f"[{x}, {y}]" for x, y in points) + "]"
    lines = [
        f"# 확신도 보정 ({stamp})",
        "",
        f"- 세션 {len(samples)}개, 정확 일치 {sum(correct)}개",
        "- 표본 내 평가(학습 데이터로 표를 계산)라 실제보다 낙관적이다.",
    ]
    if synthetic:
        lines.append("- **합성 데이터 결과다. 카탈로그에 반영하지 않는다.**")
    lines += [
        "",
        "## 카탈로그 점 목록 (confidence.calibration)",
        "",
        "```yaml",
        yaml_line,
        "```",
        "",
        f"![reliability]({png.name})",
        "",
        "## 자동 승인 기준별 (보정 후)",
        "",
        "| 기준 | 자동 승인 비율 | 자동 승인 중 오류율 "
        "| (보정 전) 자동 승인 비율 | (보정 전) 오류율 |",
        "| --- | --- | --- | --- | --- |",
    ]
    before = threshold_table(current, correct)
    for (thr, rate, err), (_, b_rate, b_err) in zip(
        threshold_table(calibrated, correct), before, strict=True
    ):
        fmt = lambda v: "-" if v is None else f"{v * 100:.1f}%"  # noqa: E731
        lines.append(f"| {thr:.2f} | {fmt(rate)} | {fmt(err)} | {fmt(b_rate)} | {fmt(b_err)} |")
    md = "\n".join(lines) + "\n"
    (a.out_dir / f"calibration_{stamp}.md").write_text(md, encoding="utf-8")
    print(md)  # noqa: T201
    log.info("저장: %s, %s", png, a.out_dir / f"calibration_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
