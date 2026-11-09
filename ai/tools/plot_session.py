"""세션 JSON → kneeAngle 시계열 그래프 PNG.

그래프 글자는 OS별 한글 글꼴 차이를 피하려고 영문으로 쓴다.
기준선(하강 시작·시도·깊이·서기 각도), 렙 구간 음영(인정 초록 / 미인정 빨강 + 사유),
무효 프레임 구간(회색), 무작위 동작 구간(파랑)을 그린다. 판정은 rep_engine을 그대로 돌린다.

    python -m tools.plot_session data/keypoints/sample/syn_000.json
    python -m tools.plot_session a.json --out reports/a.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from rep_engine.config import load_catalog  # noqa: E402
from rep_engine.session import SessionRunner  # noqa: E402
from tools.common import REPORTS_DIR, all_frames, load_session, setup_logging  # noqa: E402

MS_PER_S = 1000.0


def plot(session: Path, out: Path) -> Path:
    meta, chunks, _ = load_session(session)
    runner = SessionRunner(meta, load_catalog(meta.catalog_version))
    for fr in all_frames(chunks):
        runner.push(fr)
    result = runner.finish()
    feats = runner.features
    sq = runner.cfg.squat

    fig, ax = plt.subplots(figsize=(14, 5))
    ts = [f.t / MS_PER_S for f in feats if f.knee_angle is not None]
    ax.plot(
        ts,
        [f.knee_angle for f in feats if f.knee_angle is not None],
        lw=1.4,
        label="kneeAngle (filtered)",
        color="tab:blue",
    )
    ax.plot(
        [f.t / MS_PER_S for f in feats if f.knee_angle_raw is not None],
        [f.knee_angle_raw for f in feats if f.knee_angle_raw is not None],
        lw=0.6,
        alpha=0.5,
        label="kneeAngle (raw)",
        color="tab:gray",
    )
    x_right = feats[-1].t / MS_PER_S if feats else 0.0
    for value, name, style, x, ha in (
        (sq.stand_angle, "stand", "-", 0.0, "left"),
        (sq.descent_start_angle, "descent", "--", x_right, "right"),  # stand와 같으면 겹치지 않게
        (sq.attempt_angle, "attempt", "-.", 0.0, "left"),
        (sq.depth_accept_angle, "depth", ":", 0.0, "left"),
    ):
        ax.axhline(value, ls=style, lw=0.8, color="black")
        ax.text(x, value + 1, f"{name} {value:g}°", fontsize=8, ha=ha)
    gap_start: float | None = None
    for f in feats:
        if not f.valid and gap_start is None:
            gap_start = f.t / MS_PER_S
        elif f.valid and gap_start is not None:
            ax.axvspan(gap_start, f.t / MS_PER_S, color="gray", alpha=0.3)
            gap_start = None
    if gap_start is not None and feats:
        ax.axvspan(gap_start, feats[-1].t / MS_PER_S, color="gray", alpha=0.3)
    if meta.liveness is not None:
        ax.axvspan(
            meta.liveness.issued_at_t / MS_PER_S,
            meta.liveness.expires_at_t / MS_PER_S,
            color="tab:blue",
            alpha=0.08,
        )
    for e in result.reps:
        color = "tab:green" if e.accepted else "tab:red"
        ax.axvspan(e.start_t / MS_PER_S, e.end_t / MS_PER_S, color=color, alpha=0.18)
        label = f"#{e.index}" + ("" if e.accepted else f"\n{e.reason.value if e.reason else ''}")
        ax.text(
            e.bottom_t / MS_PER_S, e.min_knee_angle - 8, label, fontsize=7, ha="center", color=color
        )
    lv = result.liveness.status.value if result.liveness else "none"
    ax.set_title(
        f"{meta.session_id} | accepted {result.recognized_reps}/{result.attempted_reps} | "
        f"confidence {result.ai_confidence:.3f} | liveness {lv}"
    )
    ax.set_xlabel("time (s)")
    ax.set_ylabel("knee angle (deg)")
    ax.set_ylim(40, 190)
    ax.legend(loc="lower right", fontsize=8)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="세션 kneeAngle 그래프 PNG")
    p.add_argument("session", type=Path)
    p.add_argument("--out", type=Path, default=None, help="기본 reports/<세션 이름>.png")
    a = p.parse_args(argv)
    out = plot(a.session, a.out or REPORTS_DIR / f"{a.session.stem}.png")
    setup_logging().info("저장: %s", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
