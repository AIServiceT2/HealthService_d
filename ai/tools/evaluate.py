"""라벨 CSV의 모든 세션을 평가한다.

지표: 세션 정확 일치율(인정 렙 수가 정확히 같음), 평균 절대 오차, 사유별 정밀도·재현율
(세션별 개수 기반: TP = min(예측, 정답)), 촬영 각도·거리별 분해.
결과: 콘솔 표 + reports/eval_<날짜>[_태그].md + .csv

    python -m tools.evaluate                                  # data/labels.csv
    python -m tools.evaluate --labels data/labels_sample.csv  # 합성 샘플
    python -m tools.evaluate --config config/catalog/cat_2026-11-01.yaml --tag base

라벨 CSV 열: session_file(라벨 파일 기준 상대 경로), view(front|diag45|side), distance(near|far),
subject, expected_accepted, expected_shallow, expected_too_fast, expected_out_of_frame, notes
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from rep_engine.config import Catalog, load_catalog, parse_catalog
from rep_engine.schemas import RepReason
from rep_engine.session import run_session
from tools.common import DATA_DIR, REPORTS_DIR, load_session, setup_logging

REASON_FIELDS = {
    RepReason.SHALLOW_DEPTH: "shallow",
    RepReason.TOO_FAST: "too_fast",
    RepReason.OUT_OF_FRAME: "out_of_frame",
}


@dataclass
class LabelRow:
    session_file: str
    view: str
    distance: str
    subject: str
    expected_accepted: int
    expected_shallow: int | None
    expected_too_fast: int | None
    expected_out_of_frame: int | None
    notes: str


@dataclass
class SessionEval:
    session_file: str
    view: str
    distance: str
    subject: str
    expected_accepted: int
    pred_accepted: int
    abs_error: int
    exact: bool
    expected_shallow: int | None
    pred_shallow: int
    expected_too_fast: int | None
    pred_too_fast: int
    expected_out_of_frame: int | None
    pred_out_of_frame: int
    ai_confidence: float
    raw_confidence: float


def _opt_int(v: str) -> int | None:
    return int(v) if v.strip() != "" else None


def load_labels(path: Path) -> list[LabelRow]:
    with path.open(encoding="utf-8") as f:
        return [
            LabelRow(
                session_file=r["session_file"],
                view=r["view"],
                distance=r["distance"],
                subject=r.get("subject", ""),
                expected_accepted=int(r["expected_accepted"]),
                expected_shallow=_opt_int(r.get("expected_shallow", "")),
                expected_too_fast=_opt_int(r.get("expected_too_fast", "")),
                expected_out_of_frame=_opt_int(r.get("expected_out_of_frame", "")),
                notes=r.get("notes", ""),
            )
            for r in csv.DictReader(f)
        ]


def load_config(value: str | None) -> Catalog | None:
    """`--config`: 카탈로그 YAML 경로 또는 catalogVersion. 없으면 세션 메타의 버전을 쓴다."""
    if value is None:
        return None
    path = Path(value)
    if path.suffix in {".yaml", ".yml"}:
        with path.open(encoding="utf-8") as f:
            return parse_catalog(yaml.safe_load(f))
    return load_catalog(value)


def evaluate_rows(
    rows: Sequence[LabelRow], base_dir: Path, catalog: Catalog | None = None
) -> list[SessionEval]:
    out: list[SessionEval] = []
    for row in rows:
        meta, chunks, _ = load_session(base_dir / row.session_file)
        if catalog is not None:  # 다른 카탈로그로 비교: 메타의 버전을 바꿔 실행
            meta = meta.model_copy(update={"catalog_version": catalog.version})
        res = run_session(meta, chunks, catalog)
        counts = {f: sum(1 for e in res.reps if e.reason is r) for r, f in REASON_FIELDS.items()}
        out.append(
            SessionEval(
                session_file=row.session_file,
                view=row.view,
                distance=row.distance,
                subject=row.subject,
                expected_accepted=row.expected_accepted,
                pred_accepted=res.recognized_reps,
                abs_error=abs(res.recognized_reps - row.expected_accepted),
                exact=res.recognized_reps == row.expected_accepted,
                expected_shallow=row.expected_shallow,
                pred_shallow=counts["shallow"],
                expected_too_fast=row.expected_too_fast,
                pred_too_fast=counts["too_fast"],
                expected_out_of_frame=row.expected_out_of_frame,
                pred_out_of_frame=counts["out_of_frame"],
                ai_confidence=res.ai_confidence,
                raw_confidence=res.confidence_components.raw,
            )
        )
    return out


def group_metrics(evals: Sequence[SessionEval]) -> dict[str, float]:
    n = len(evals)
    if n == 0:
        return {"n": 0, "exact_rate": 0.0, "mae": 0.0, "mean_confidence": 0.0}
    return {
        "n": n,
        "exact_rate": sum(e.exact for e in evals) / n,
        "mae": sum(e.abs_error for e in evals) / n,
        "mean_confidence": sum(e.ai_confidence for e in evals) / n,
    }


def reason_metrics(evals: Sequence[SessionEval]) -> dict[str, dict[str, float | None]]:
    """사유별 개수 기반 정밀도·재현율 (라벨이 있는 세션만)."""
    out: dict[str, dict[str, float | None]] = {}
    for field in REASON_FIELDS.values():
        tp = pred = exp = 0
        for e in evals:
            expected = getattr(e, f"expected_{field}")
            if expected is None:
                continue
            p = getattr(e, f"pred_{field}")
            tp += min(p, expected)
            pred += p
            exp += expected
        out[field] = {
            "precision": tp / pred if pred else None,
            "recall": tp / exp if exp else None,
            "predicted": float(pred),
            "expected": float(exp),
        }
    return out


def by_group(evals: Iterable[SessionEval], *keys: str) -> dict[tuple[str, ...], dict[str, float]]:
    groups: dict[tuple[str, ...], list[SessionEval]] = defaultdict(list)
    for e in evals:
        groups[tuple(getattr(e, k) for k in keys)].append(e)
    return {k: group_metrics(v) for k, v in sorted(groups.items())}


def _fmt(v: float | None, pct: bool = False) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%" if pct else f"{v:.2f}"


def report_markdown(evals: Sequence[SessionEval], labels: Path, config: str | None) -> str:
    overall = group_metrics(evals)
    synthetic = bool(evals) and all(e.subject == "synthetic" for e in evals)
    lines = [
        f"# 렙 판정 평가 ({dt.date.today().isoformat()})",
        "",
        f"- 라벨: `{labels}` · 카탈로그: `{config or '세션 메타의 catalogVersion'}`",
        f"- 세션 {overall['n']:.0f}개, 정확 일치율 {_fmt(overall['exact_rate'], True)}, "
        f"평균 절대 오차 {_fmt(overall['mae'])}렙",
    ]
    if synthetic:
        lines.append("- **합성 데이터 결과다. 실제 정확도나 권장값의 근거로 쓰지 않는다.**")
    lines += [
        "",
        "## 사유별 (개수 기반)",
        "",
        "| 사유 | 예측 | 정답 | 정밀도 | 재현율 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field, m in reason_metrics(evals).items():
        lines.append(
            f"| {field} | {m['predicted']:.0f} | {m['expected']:.0f} | "
            f"{_fmt(m['precision'], True)} | {_fmt(m['recall'], True)} |"
        )
    for title, keys in (
        ("촬영 각도별", ("view",)),
        ("거리별", ("distance",)),
        ("각도 × 거리", ("view", "distance")),
    ):
        lines += [
            "",
            f"## {title}",
            "",
            "| 조건 | 세션 | 정확 일치율 | 평균 절대 오차 | 평균 확신도 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for k, m in by_group(evals, *keys).items():
            lines.append(
                f"| {' / '.join(k)} | {m['n']:.0f} | {_fmt(m['exact_rate'], True)} | "
                f"{_fmt(m['mae'])} | {_fmt(m['mean_confidence'])} |"
            )
    return "\n".join(lines) + "\n"


def write_csv(evals: Sequence[SessionEval], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        fields = list(asdict(evals[0]).keys()) if evals else list(SessionEval.__annotations__)
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in evals:
            w.writerow(asdict(e))


def run_evaluation(labels: Path, config: str | None) -> list[SessionEval]:
    return evaluate_rows(load_labels(labels), labels.parent, load_config(config))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="라벨 세션 전체 평가")
    p.add_argument("--labels", type=Path, default=DATA_DIR / "labels.csv")
    p.add_argument("--config", default=None, help="카탈로그 YAML 경로 또는 catalogVersion")
    p.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    p.add_argument("--tag", default="", help="출력 파일 이름 꼬리표")
    a = p.parse_args(argv)
    log = setup_logging()
    evals = run_evaluation(a.labels, a.config)
    if not evals:
        log.warning("라벨에 세션이 없음: %s", a.labels)
        return 1
    md = report_markdown(evals, a.labels, a.config)
    stem = f"eval_{dt.date.today().isoformat()}" + (f"_{a.tag}" if a.tag else "")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    write_csv(evals, a.out_dir / f"{stem}.csv")
    print(md)  # noqa: T201  (콘솔 표 출력이 이 도구의 목적)
    log.info("저장: %s/%s.md, .csv", a.out_dir, stem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
