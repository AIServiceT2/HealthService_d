"""촬영 조건(view × distance)별 정확도 비교 → 권장 촬영 각도 근거 리포트 (US-01 튜토리얼 문구용).

    python -m tools.angle_study --labels data/labels.csv
    python -m tools.angle_study --labels data/labels_sample.csv   # 합성 — 근거로 쓰지 않음

권장안: 세션이 --min-n 이상인 촬영 각도 중 정확 일치율이 가장 높은 것
(같으면 평균 절대 오차가 작은 것).
조건을 만족하는 각도가 없으면 "근거 부족"으로 쓴다.
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections.abc import Sequence
from pathlib import Path

from tools.common import DATA_DIR, REPORTS_DIR, setup_logging
from tools.evaluate import SessionEval, by_group, run_evaluation

DEFAULT_MIN_N = 5


def recommend(evals: Sequence[SessionEval], min_n: int) -> tuple[str, ...] | None:
    candidates = [(k, m) for k, m in by_group(evals, "view").items() if m["n"] >= min_n]
    if not candidates:
        return None
    best = max(candidates, key=lambda km: (km[1]["exact_rate"], -km[1]["mae"]))
    return best[0]


def report(evals: Sequence[SessionEval], labels: Path, min_n: int) -> str:
    synthetic = bool(evals) and all(e.subject == "synthetic" for e in evals)
    rec = recommend(evals, min_n)
    lines = [
        f"# 촬영 조건별 정확도 ({dt.date.today().isoformat()})",
        "",
        f"- 라벨: `{labels}`, 세션 {len(evals)}개, 권장 판단 최소 세션 수 {min_n}",
    ]
    if synthetic:
        lines.append(
            "- **합성 데이터다. 합성 투영 모델의 결과라 실제 촬영 권장 근거로 쓰지 않는다.**"
        )
    lines.append(f"- 권장 촬영 각도: {rec[0] if rec else '근거 부족 (조건별 세션이 부족함)'}")
    for title, keys in (("각도", ("view",)), ("각도 × 거리", ("view", "distance"))):
        lines += [
            "",
            f"## {title}",
            "",
            "| 조건 | 세션 | 정확 일치율 | 평균 절대 오차 | 평균 확신도 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for k, m in by_group(evals, *keys).items():
            lines.append(
                f"| {' / '.join(k)} | {m['n']:.0f} | {m['exact_rate'] * 100:.1f}% | "
                f"{m['mae']:.2f} | {m['mean_confidence']:.2f} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="촬영 각도·거리별 정확도 리포트")
    p.add_argument("--labels", type=Path, default=DATA_DIR / "labels.csv")
    p.add_argument("--config", default=None)
    p.add_argument("--min-n", type=int, default=DEFAULT_MIN_N)
    p.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    a = p.parse_args(argv)
    log = setup_logging()
    evals = run_evaluation(a.labels, a.config)
    if not evals:
        log.warning("라벨에 세션이 없음: %s", a.labels)
        return 1
    md = report(evals, a.labels, a.min_n)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"angle_study_{dt.date.today().isoformat()}.md"
    out.write_text(md, encoding="utf-8")
    print(md)  # noqa: T201
    log.info("저장: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
