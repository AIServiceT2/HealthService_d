"""규칙 기반 이상 징후 (SPEC 8.3, L2 입력). 기준값은 카탈로그 `anomaly` 섹션.

움직임 측정: 연속한 두 사람 검출 프레임에서, 두 프레임 모두 보이는 관절의 평균 이동 거리(픽셀)를
이미지 대각선으로 나눈 값(`motion`, 프레임당). 속도(`speed`) = motion ÷ 시간 간격(초).

- REP_TIMING_TOO_REGULAR (HIGH): 인정 렙 ≥ regular_timing_min_reps 이고
  렙 시간 표준편차 < regular_timing_std_ms
- LANDMARKS_FROZEN (HIGH): motion ≤ frozen_motion_ratio 인 연속 구간 > frozen_ms
- ZERO_JITTER (MEDIUM): 정지 구간(speed < stationary_speed_ratio, 길이 ≥ zero_jitter_min_ms)의
  motion 중앙값 < zero_jitter_ratio. LANDMARKS_FROZEN이 이미 잡히면 중복으로 내지 않는다
- BODY_PROPORTION_SHIFT (HIGH): 쉬는 자세 프레임(스쿼트: 서 있음, 푸시업: 팔을 폄,
  윗몸 일으키기: 누움)의 상체/하체 비율이, 첫 기준 구간 중앙값 대비
  proportion_shift_ratio 넘게 바뀐 구간이 있음 (구간 길이 = features.calibration_window_ms)
- MULTIPLE_RESETS (LOW): reset_gap_ms 이상 무효 구간 후 재등장이 reset_count 회 이상
- UNREALISTIC_PACE (MEDIUM): 인정 렙 평균 시간 < min_avg_rep_ms
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol, TypeVar

from rep_engine.adapters import SkeletonFrame
from rep_engine.config import EngineConfig
from rep_engine.features.extractor import FrameFeatures
from rep_engine.rounding import r_ms, r_ratio
from rep_engine.schemas import Anomaly, AnomalyCode, AnyRepEvent, Severity
from rep_engine.stats import mean, median, pstdev

_MS_PER_S = 1000.0
#: 비율 비교에 필요한 최소 표본 수 (구간 중앙값이 프레임 1~2개에 흔들리지 않게)
MIN_WINDOW_SAMPLES = 3


class FeatureLike(Protocol):
    """이상 징후 검사에 필요한 프레임 특징 (FrameFeatures·ChainFeatures 공통)."""

    @property
    def t(self) -> int: ...

    @property
    def valid(self) -> bool: ...

    @property
    def torso_leg_ratio(self) -> float | None: ...


F = TypeVar("F", bound=FeatureLike)


def squat_rest(stand_angle: float) -> Callable[[FrameFeatures], bool]:
    """스쿼트의 쉬는 자세 = 필터 전 무릎 각도가 서기 각도 이상."""

    def is_rest(f: FrameFeatures) -> bool:
        return f.knee_angle_raw is not None and f.knee_angle_raw >= stand_angle

    return is_rest


def _motions(
    frames: Sequence[SkeletonFrame], min_vis: float, diag: float
) -> list[tuple[int, int, float]]:
    """(이전 t, 현재 t, motion) 목록. 사이에 미검출 프레임이 있으면 이어지지 않는다."""
    out: list[tuple[int, int, float]] = []
    prev: SkeletonFrame | None = None
    for fr in frames:
        if fr.joints is None:
            prev = None
            continue
        if prev is not None and prev.joints is not None:
            ds = [
                ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
                for a, b in zip(prev.joints, fr.joints, strict=True)
                if a is not None and b is not None and a.vis >= min_vis and b.vis >= min_vis
            ]
            if ds:
                out.append((prev.t, fr.t, mean(ds) / diag))
        prev = fr
    return out


def _runs(
    motions: Sequence[tuple[int, int, float]], *, keep: list[bool]
) -> list[tuple[int, int, list[float]]]:
    """keep[i]가 참인 연속 구간 → (시작 t, 끝 t, motion 목록). 이어지지 않는 간격에서 끊는다."""
    runs: list[tuple[int, int, list[float]]] = []
    cur: tuple[int, int, list[float]] | None = None
    for (t0, t1, m), k in zip(motions, keep, strict=True):
        if k and cur is not None and cur[1] == t0:
            cur = (cur[0], t1, [*cur[2], m])
        elif k:
            if cur is not None:
                runs.append(cur)
            cur = (t0, t1, [m])
        else:
            if cur is not None:
                runs.append(cur)
            cur = None
    if cur is not None:
        runs.append(cur)
    return runs


def _proportion_shift(
    feats: Sequence[F], is_rest: Callable[[F], bool], window_ms: int
) -> float | None:
    """기준 대비 최대 상대 변화량. 비교할 표본이 부족하면 None."""
    samples = [
        (f.t, f.torso_leg_ratio)
        for f in feats
        if f.valid and f.torso_leg_ratio is not None and is_rest(f)
    ]
    if not samples:
        return None
    windows: list[list[float]] = []
    start = samples[0][0]
    for t, r in samples:
        if not windows or t - start >= window_ms:
            windows.append([])
            start = t
        windows[-1].append(r)
    windows = [w for w in windows if len(w) >= MIN_WINDOW_SAMPLES]
    if len(windows) < 2:
        return None
    base = median(windows[0])
    if base <= 0:
        return None
    return max(abs(median(w) / base - 1.0) for w in windows[1:])


def detect_anomalies(
    frames: Sequence[SkeletonFrame],
    feats: Sequence[F],
    reps: Sequence[AnyRepEvent],
    cfg: EngineConfig,
    image_diag_px: float,
    is_rest: Callable[[F], bool] | None = None,
) -> list[Anomaly]:
    """이상 징후 목록 (AnomalyCode 정의 순서).

    `is_rest`(쉬는 자세 판별)를 주지 않으면 스쿼트 기준(`squat_rest`)을 쓴다.
    """
    a = cfg.anomaly
    out: list[Anomaly] = []
    acc = [e for e in reps if e.accepted]
    durations = [float(e.end_t - e.start_t) for e in acc]

    if len(acc) >= a.regular_timing_min_reps:
        std = pstdev(durations)
        if std < a.regular_timing_std_ms:
            out.append(
                Anomaly(
                    code=AnomalyCode.REP_TIMING_TOO_REGULAR,
                    severity=Severity.HIGH,
                    detail=f"인정 렙 {len(acc)}개의 렙 시간 표준편차 {r_ms(std)}ms",
                )
            )

    motions = _motions(frames, cfg.features.min_visibility, image_diag_px)
    frozen_runs = _runs(motions, keep=[m <= a.frozen_motion_ratio for _, _, m in motions])
    longest = max((r[1] - r[0] for r in frozen_runs), default=0)
    frozen = longest > a.frozen_ms
    if frozen:
        out.append(
            Anomaly(
                code=AnomalyCode.LANDMARKS_FROZEN,
                severity=Severity.HIGH,
                detail=f"관절 좌표가 {longest}ms 동안 거의 변하지 않음",
            )
        )

    speeds = [m / ((t1 - t0) / _MS_PER_S) for t0, t1, m in motions]
    still = _runs(motions, keep=[s < a.stationary_speed_ratio for s in speeds])
    jitter = [m for t0, t1, ms in still if t1 - t0 >= a.zero_jitter_min_ms for m in ms]
    if not frozen and jitter and median(jitter) < a.zero_jitter_ratio:
        out.append(
            Anomaly(
                code=AnomalyCode.ZERO_JITTER,
                severity=Severity.MEDIUM,
                detail=f"정지 구간의 미세 떨림 중앙값 {median(jitter):.6f} (대각선 비율)",
            )
        )

    rest: Callable[[F], bool] = is_rest or squat_rest(cfg.squat.stand_angle)  # type: ignore[assignment]
    shift = _proportion_shift(feats, rest, cfg.features.calibration_window_ms)
    if shift is not None and shift > a.proportion_shift_ratio:
        out.append(
            Anomaly(
                code=AnomalyCode.BODY_PROPORTION_SHIFT,
                severity=Severity.HIGH,
                detail=f"상체/하체 비율이 기준 대비 {r_ratio(shift)} 변함",
            )
        )

    resets = 0
    gap_start: int | None = None
    for f in feats:
        if not f.valid:
            gap_start = f.t if gap_start is None else gap_start
        else:
            if gap_start is not None and f.t - gap_start >= a.reset_gap_ms:
                resets += 1
            gap_start = None
    if resets >= a.reset_count:
        out.append(
            Anomaly(
                code=AnomalyCode.MULTIPLE_RESETS,
                severity=Severity.LOW,
                detail=f"{a.reset_gap_ms}ms 이상 사라졌다 다시 나타난 횟수 {resets}회",
            )
        )

    if acc and mean(durations) < a.min_avg_rep_ms:
        out.append(
            Anomaly(
                code=AnomalyCode.UNREALISTIC_PACE,
                severity=Severity.MEDIUM,
                detail=f"인정 렙 평균 시간 {r_ms(mean(durations))}ms",
            )
        )
    return out
