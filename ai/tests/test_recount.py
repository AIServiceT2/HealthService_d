import pytest

from rep_engine.config import Catalog, EngineConfig
from rep_engine.errors import InvalidReductionError
from rep_engine.recount import compare, decide_approval, interval_iou, match_reps
from rep_engine.schemas import (
    Anomaly,
    AnomalyCode,
    ApprovalReason,
    ClientRep,
    ClientSubmission,
    LivenessStatus,
    SessionResult,
    Severity,
)
from rep_engine.session import run_session
from tests.synth import LivenessAction, SynthConfig, challenge, synth_session, varied_squats


@pytest.fixture(scope="module")
def result(catalog: Catalog) -> SessionResult:
    sc = SynthConfig(
        reps=varied_squats(10, seed=11),
        lead_in_ms=4000,
        noise_px=1.5,
        hand_raises=[(500, 2000, "LEFT")],
        liveness=challenge(LivenessAction.RAISE_LEFT_HAND, 0, 3000),
    )
    meta, chunks = synth_session(sc)
    res = run_session(meta, chunks, catalog)
    assert res.recognized_reps == 10 and res.ai_confidence >= 0.9
    return res


def client_from(
    res: SessionResult, count: int | None = None, conf: float | None = None, shift: int = 30
) -> ClientSubmission:
    reps = [
        ClientRep(start_t=e.start_t + shift, end_t=e.end_t + shift, accepted=e.accepted)
        for e in res.reps
    ]
    return ClientSubmission(
        client_rep_count=res.recognized_reps if count is None else count,
        reps=reps,
        ai_confidence=res.ai_confidence if conf is None else conf,
    )


@pytest.mark.parametrize(
    ("client_count", "mismatch"),
    [(10, False), (11, False), (9, True), (12, True), (0, True)],
)
def test_tolerance_boundary(
    result: SessionResult, cfg: EngineConfig, client_count: int, mismatch: bool
) -> None:
    cmp = compare(result, client_from(result, client_count), cfg.recount)
    assert cmp.mismatch is mismatch
    assert cmp.error_code == ("SERVER_RECOUNT_MISMATCH" if mismatch else None)


def test_exact_tolerance_is_not_mismatch(result: SessionResult, cfg: EngineConfig) -> None:
    nine = result.model_copy(update={"recognized_reps": 9})
    assert compare(nine, client_from(result, 10), cfg.recount).mismatch_ratio == 0.1
    assert not compare(nine, client_from(result, 10), cfg.recount).mismatch


def test_client_overclaim_uses_server(result: SessionResult, cfg: EngineConfig) -> None:
    cmp = compare(result, client_from(result, 15), cfg.recount)
    assert cmp.final_rep_count == 10 and cmp.server_rep_count == 10


def test_user_reduction_r12(result: SessionResult, cfg: EngineConfig) -> None:
    assert compare(result, client_from(result), cfg.recount, 8).final_rep_count == 8
    assert compare(result, client_from(result), cfg.recount, 10).final_rep_count == 10
    for bad in (11, -1):
        with pytest.raises(InvalidReductionError) as ei:
            compare(result, client_from(result), cfg.recount, bad)
        assert ei.value.code == "INVALID_REDUCTION"


def test_rep_matching(result: SessionResult, cfg: EngineConfig) -> None:
    base = client_from(result)
    cmp = compare(result, base, cfg.recount)
    assert (cmp.matched_reps, cmp.client_only_reps, cmp.server_only_reps) == (10, 0, 0)
    reps = list(base.reps[1:])  # 하나 빠짐
    reps[0] = reps[0].model_copy(update={"accepted": False})  # 하나 판정 다름
    reps.append(ClientRep(start_t=999_000, end_t=1_000_000, accepted=True))  # 서버에 없음
    cmp = compare(result, base.model_copy(update={"reps": reps}), cfg.recount)
    assert (cmp.matched_reps, cmp.client_only_reps, cmp.server_only_reps) == (9, 1, 1)
    assert cmp.accepted_disagreements == 1


def test_match_reps_prefers_best_overlap() -> None:
    assert interval_iou(0, 10, 5, 15) == pytest.approx(5 / 15)
    assert interval_iou(0, 0, 0, 0) == 0.0
    from tests.featurize import make_rep

    server = [make_rep(1, 0, 1000), make_rep(2, 1000, 1000)]
    client = [
        ClientRep(start_t=900, end_t=2000, accepted=True),
        ClientRep(start_t=0, end_t=950, accepted=True),
    ]
    assert match_reps(server, client, 0.5) == [(0, 1), (1, 0)]


def test_client_confidence_divergence(result: SessionResult, cfg: EngineConfig) -> None:
    ok = compare(result, client_from(result, conf=result.ai_confidence - 0.1), cfg.recount)
    assert ok.anomalies == []
    far = compare(
        result, client_from(result, conf=max(0.0, result.ai_confidence - 0.2)), cfg.recount
    )
    assert [a.code for a in far.anomalies] == [AnomalyCode.CLIENT_CONFIDENCE_DIVERGENCE]
    assert far.anomalies[0].severity is Severity.MEDIUM
    # 클라이언트 확신도는 승인 판단에 쓰지 않음
    assert decide_approval(result, far, cfg).decision == "AUTO_APPROVE"


def _with_policy(cfg: EngineConfig, policy: str) -> EngineConfig:
    return cfg.model_copy(
        update={"recount": cfg.recount.model_copy(update={"liveness_policy": policy})}
    )


def test_auto_approve(result: SessionResult, cfg: EngineConfig) -> None:
    d = decide_approval(result, compare(result, client_from(result), cfg.recount), cfg)
    assert (d.decision, d.approval_path, d.reason_codes) == ("AUTO_APPROVE", "AI_AUTO", [])
    assert d.evidence.server_confidence == result.ai_confidence
    assert d.to_dict()["approvalPath"] == "AI_AUTO"


def test_low_confidence(result: SessionResult, cfg: EngineConfig) -> None:
    low = result.model_copy(update={"ai_confidence": 0.899})
    d = decide_approval(low, compare(low, client_from(low), cfg.recount), cfg)
    assert d.decision == "HUMAN_REVIEW" and d.reason_codes == [ApprovalReason.LOW_CONFIDENCE]
    at = result.model_copy(update={"ai_confidence": 0.9})
    assert decide_approval(at, compare(at, client_from(at), cfg.recount), cfg).decision == (
        "AUTO_APPROVE"
    )


@pytest.mark.parametrize("status", [LivenessStatus.EXPIRED, LivenessStatus.FAILED_NO_PERSON, None])
def test_liveness_not_passed(
    result: SessionResult, cfg: EngineConfig, status: LivenessStatus | None
) -> None:
    lv = (
        None
        if status is None
        else result.liveness.model_copy(  # type: ignore[union-attr]
            update={"status": status, "passed_at_t": None}
        )
    )
    bad = result.model_copy(update={"liveness": lv})
    cmp = compare(bad, client_from(bad), cfg.recount)
    restart = decide_approval(bad, cmp, _with_policy(cfg, "restart"))
    assert (restart.decision, restart.approval_path) == ("REJECT_RESTART", "RESTART")
    review = decide_approval(bad, cmp, _with_policy(cfg, "review"))
    assert review.decision == "HUMAN_REVIEW"
    assert review.reason_codes == [ApprovalReason.LIVENESS_NOT_PASSED]


def test_mismatch_and_high_anomaly(result: SessionResult, cfg: EngineConfig) -> None:
    d = decide_approval(result, compare(result, client_from(result, 14), cfg.recount), cfg)
    assert d.decision == "HUMAN_REVIEW" and d.reason_codes == [ApprovalReason.RECOUNT_MISMATCH]
    high = Anomaly(code=AnomalyCode.LANDMARKS_FROZEN, severity=Severity.HIGH, detail="x")
    medium = Anomaly(code=AnomalyCode.UNREALISTIC_PACE, severity=Severity.MEDIUM, detail="x")
    withhigh = result.model_copy(update={"anomalies": [high, medium]})
    d = decide_approval(withhigh, compare(withhigh, client_from(withhigh), cfg.recount), cfg)
    assert d.reason_codes == [ApprovalReason.ANOMALY_HIGH]
    assert d.evidence.high_anomalies == [AnomalyCode.LANDMARKS_FROZEN]
    medium_only = result.model_copy(update={"anomalies": [medium]})
    assert (
        decide_approval(
            medium_only, compare(medium_only, client_from(medium_only), cfg.recount), cfg
        ).decision
        == "AUTO_APPROVE"
    )


def test_multiple_reasons_in_order(result: SessionResult, cfg: EngineConfig) -> None:
    high = Anomaly(code=AnomalyCode.BODY_PROPORTION_SHIFT, severity=Severity.HIGH, detail="x")
    bad = result.model_copy(update={"ai_confidence": 0.5, "anomalies": [high], "liveness": None})
    d = decide_approval(
        bad, compare(bad, client_from(bad, 20), cfg.recount), _with_policy(cfg, "review")
    )
    assert d.reason_codes == [
        ApprovalReason.LOW_CONFIDENCE,
        ApprovalReason.LIVENESS_NOT_PASSED,
        ApprovalReason.RECOUNT_MISMATCH,
        ApprovalReason.ANOMALY_HIGH,
    ]


def test_client_submission_parsing() -> None:
    c = ClientSubmission.model_validate(
        {
            "clientRepCount": 3,
            "aiConfidence": 0.8,
            "poseSummary": {"anything": 1},
            "reps": [
                {
                    "index": 1,
                    "startT": 0,
                    "bottomT": 500,
                    "endT": 1000,
                    "accepted": True,
                    "reason": None,
                    "minKneeAngle": 80,
                }
            ],
        }
    )
    assert c.reps[0].end_t == 1000
