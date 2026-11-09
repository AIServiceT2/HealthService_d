"""서버 재계산 비교와 자동 승인 판정 (SPEC 9.2·9.3).

- 인정량은 항상 서버 값이다. 클라이언트가 더 많이 주장해도 서버 값을 넘을 수 없다.
- R12: 사용자는 횟수를 줄일 수만 있다. `userReducedCount` > 서버 인정량이면 `InvalidReductionError`.
- 확신도도 서버 값으로 판정한다. 클라이언트 확신도는 기록·비교용 (조작 가능하므로).
- 이 모듈은 판정만 낸다. 제출건 상태(`PREPARED → APPROVED` 등)는 백엔드가 바꾼다.
"""

from __future__ import annotations

from collections.abc import Sequence

from rep_engine.config import EngineConfig, RecountCfg
from rep_engine.errors import InvalidReductionError
from rep_engine.rounding import r_ratio
from rep_engine.schemas import (
    Anomaly,
    AnomalyCode,
    ApprovalDecision,
    ApprovalEvidence,
    ApprovalReason,
    ClientRep,
    ClientSubmission,
    LivenessStatus,
    RecountComparison,
    RepEvent,
    SessionResult,
    Severity,
)


def interval_iou(a0: int, a1: int, b0: int, b1: int) -> float:
    """시간 구간 [a0, a1]과 [b0, b1]의 IoU (0~1)."""
    inter = max(0, min(a1, b1) - max(a0, b0))
    union = max(a1, b1) - min(a0, b0)
    return inter / union if union > 0 else 0.0


def match_reps(
    server: Sequence[RepEvent], client: Sequence[ClientRep], min_iou: float
) -> list[tuple[int, int]]:
    """서버·클라이언트 렙을 시간 겹침으로 1:1 매칭한다 (결정적 탐욕 매칭).

    서버 렙 순서대로, 아직 안 쓴 클라이언트 렙 중 IoU가 가장 큰 것(같으면 앞쪽)을 고른다.
    Returns: (서버 인덱스, 클라이언트 인덱스) 목록
    """
    used: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for si, s in enumerate(server):
        best: tuple[float, int] | None = None
        for ci, c in enumerate(client):
            if ci in used:
                continue
            iou = interval_iou(s.start_t, s.end_t, c.start_t, c.end_t)
            if iou >= min_iou and (best is None or iou > best[0]):
                best = (iou, ci)
        if best is not None:
            used.add(best[1])
            pairs.append((si, best[1]))
    return pairs


def compare(
    result: SessionResult,
    client: ClientSubmission,
    cfg: RecountCfg,
    user_reduced_count: int | None = None,
) -> RecountComparison:
    """서버 결과와 클라이언트 제출값을 비교한다."""
    server_count = result.recognized_reps
    if user_reduced_count is not None and (
        user_reduced_count < 0 or user_reduced_count > server_count
    ):
        raise InvalidReductionError(
            f"줄인 횟수({user_reduced_count})가 서버 인정량({server_count})보다 큼",
            {"userReducedCount": user_reduced_count, "serverRepCount": server_count},
        )
    ratio = abs(server_count - client.client_rep_count) / max(client.client_rep_count, 1)
    mismatch = ratio > cfg.recount_tolerance
    pairs = match_reps(result.reps, client.reps, cfg.rep_match_iou)
    disagreements = sum(
        1 for si, ci in pairs if result.reps[si].accepted != client.reps[ci].accepted
    )
    diff = abs(result.ai_confidence - client.ai_confidence)
    extra: list[Anomaly] = []
    if diff >= cfg.confidence_diff_warn:
        extra.append(
            Anomaly(
                code=AnomalyCode.CLIENT_CONFIDENCE_DIVERGENCE,
                severity=Severity.MEDIUM,
                detail=(
                    f"클라이언트 확신도 {client.ai_confidence}와 "
                    f"서버 확신도 {result.ai_confidence}의 차이 {r_ratio(diff)}"
                ),
            )
        )
    return RecountComparison(
        server_rep_count=server_count,
        client_rep_count=client.client_rep_count,
        user_reduced_count=user_reduced_count,
        final_rep_count=server_count if user_reduced_count is None else user_reduced_count,
        mismatch=mismatch,
        mismatch_ratio=r_ratio(ratio),
        error_code="SERVER_RECOUNT_MISMATCH" if mismatch else None,
        matched_reps=len(pairs),
        client_only_reps=len(client.reps) - len(pairs),
        server_only_reps=len(result.reps) - len(pairs),
        accepted_disagreements=disagreements,
        server_confidence=result.ai_confidence,
        client_confidence=client.ai_confidence,
        confidence_diff=r_ratio(diff),
        anomalies=extra,
    )


def decide_approval(
    result: SessionResult, comparison: RecountComparison, cfg: EngineConfig
) -> ApprovalDecision:
    """자동 승인 판정.

    - 무작위 동작 미통과 + `liveness_policy == "restart"` → REJECT_RESTART
    - 서버 확신도 ≥ 기준, 무작위 동작 통과, 불일치 없음, HIGH 이상 징후 없음 → AUTO_APPROVE
    - 그 외 → HUMAN_REVIEW (사유 코드 포함)
    """
    rc = cfg.recount
    liveness_status = result.liveness.status if result.liveness is not None else None
    passed = liveness_status is LivenessStatus.PASSED
    high = sorted(
        {a.code for a in [*result.anomalies, *comparison.anomalies] if a.severity is Severity.HIGH}
    )
    reasons: list[ApprovalReason] = []
    if result.ai_confidence < rc.auto_approve_threshold:
        reasons.append(ApprovalReason.LOW_CONFIDENCE)
    if not passed:
        reasons.append(ApprovalReason.LIVENESS_NOT_PASSED)
    if comparison.mismatch:
        reasons.append(ApprovalReason.RECOUNT_MISMATCH)
    if high:
        reasons.append(ApprovalReason.ANOMALY_HIGH)
    evidence = ApprovalEvidence(
        server_confidence=result.ai_confidence,
        auto_approve_threshold=rc.auto_approve_threshold,
        liveness_status=liveness_status,
        liveness_policy=rc.liveness_policy,
        mismatch=comparison.mismatch,
        high_anomalies=high,
    )
    if not passed and rc.liveness_policy == "restart":
        return ApprovalDecision(
            decision="REJECT_RESTART",
            approval_path="RESTART",
            reason_codes=reasons,
            evidence=evidence,
        )
    if not reasons:
        return ApprovalDecision(
            decision="AUTO_APPROVE", approval_path="AI_AUTO", reason_codes=[], evidence=evidence
        )
    return ApprovalDecision(
        decision="HUMAN_REVIEW",
        approval_path="HUMAN_REVIEW",
        reason_codes=reasons,
        evidence=evidence,
    )
