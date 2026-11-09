import pytest

from rep_engine.config import Catalog, EngineConfig
from rep_engine.liveness import INSTRUCTIONS, LivenessEvaluator, evaluate_liveness, issue_challenge
from rep_engine.schemas import LivenessAction, LivenessResult, LivenessStatus
from tests.featurize import skeletons
from tests.synth import Hand, SynthConfig, challenge

L, R, B = (
    LivenessAction.RAISE_LEFT_HAND,
    LivenessAction.RAISE_RIGHT_HAND,
    LivenessAction.RAISE_BOTH_HANDS,
)


def run(
    cfg: EngineConfig,
    action: LivenessAction,
    raises: list[tuple[int, int, Hand]],
    invalid: list[tuple[int, int]] | None = None,
    issued: int = 0,
    expires: int = 5000,
    **kw: object,
) -> LivenessResult:
    sc = SynthConfig(
        view="front",
        reps=[],
        lead_in_ms=6000,
        tail_ms=0,
        hand_raises=raises,
        invalid_ranges=invalid or [],
        **kw,  # type: ignore[arg-type]
    )
    ch = challenge(action, issued, expires)
    return evaluate_liveness(ch, skeletons(sc), cfg.liveness, cfg.features.min_visibility)


@pytest.mark.parametrize(("action", "hand"), [(L, "LEFT"), (R, "RIGHT"), (B, "BOTH")])
def test_correct_hand_passes(cfg: EngineConfig, action: LivenessAction, hand: Hand) -> None:
    res = run(cfg, action, [(1000, 3000, hand)])
    assert res.status is LivenessStatus.PASSED
    assert res.passed_at_t is not None and 2000 <= res.passed_at_t <= 2100
    assert res.evidence.max_hold_ms >= cfg.liveness.liveness_hold_ms
    assert res.evidence.valid_frame_ratio == 1.0


@pytest.mark.parametrize("action", [L, R])
def test_both_hands_pass_single_hand_instruction(cfg: EngineConfig, action: LivenessAction) -> None:
    assert run(cfg, action, [(1000, 3000, "BOTH")]).status is LivenessStatus.PASSED


@pytest.mark.parametrize(("action", "wrong"), [(L, "RIGHT"), (R, "LEFT")])
def test_wrong_hand_only_does_not_pass(
    cfg: EngineConfig, action: LivenessAction, wrong: Hand
) -> None:
    res = run(cfg, action, [(1000, 3000, wrong)])
    assert res.status is LivenessStatus.EXPIRED and res.passed_at_t is None
    assert res.evidence.wrong_hand_max_hold_ms >= cfg.liveness.wrong_hand_hold_ms
    assert res.evidence.wrong_hand_detected
    assert res.evidence.max_hold_ms == 0


def test_one_hand_for_both_instruction_fails(cfg: EngineConfig) -> None:
    res = run(cfg, B, [(1000, 3000, "LEFT")])
    assert res.status is LivenessStatus.EXPIRED
    assert not res.evidence.wrong_hand_detected


def test_hold_too_short(cfg: EngineConfig) -> None:
    res = run(cfg, L, [(1000, 1800, "LEFT"), (2500, 3200, "LEFT")])
    assert res.status is LivenessStatus.EXPIRED
    assert 0 < res.evidence.max_hold_ms < cfg.liveness.liveness_hold_ms


def test_invalid_frame_breaks_hold(cfg: EngineConfig) -> None:
    res = run(cfg, L, [(1000, 2500, "LEFT")], invalid=[(1500, 1600)])
    assert res.status is LivenessStatus.EXPIRED


def test_expired_when_raise_after_deadline(cfg: EngineConfig) -> None:
    res = run(cfg, L, [(4500, 6000, "LEFT")], expires=5000)
    assert res.status is LivenessStatus.EXPIRED


def test_no_person(cfg: EngineConfig) -> None:
    res = run(cfg, L, [(1000, 3000, "LEFT")], invalid=[(0, 4000)])
    assert res.status is LivenessStatus.FAILED_NO_PERSON
    assert res.evidence.valid_frame_ratio < cfg.liveness.min_valid_ratio


def test_window_respects_issued_at(cfg: EngineConfig) -> None:
    # 발급 전에 든 손은 세지 않는다
    res = run(cfg, L, [(0, 1500, "LEFT")], issued=1000, expires=4000)
    assert res.status is LivenessStatus.EXPIRED


def test_mirrored_upload_still_left(cfg: EngineConfig) -> None:
    assert run(cfg, L, [(1000, 3000, "LEFT")], mirrored=True).status is LivenessStatus.PASSED
    assert run(cfg, R, [(1000, 3000, "LEFT")], mirrored=True).status is LivenessStatus.EXPIRED


def test_movenet_adapter(catalog: Catalog) -> None:
    cfg = catalog.for_model("movenet")
    assert run(cfg, R, [(1000, 3000, "RIGHT")], model="movenet").status is LivenessStatus.PASSED


def test_streaming_matches_batch_and_stops(cfg: EngineConfig) -> None:
    sc = SynthConfig(
        view="front", reps=[], lead_in_ms=6000, tail_ms=0, hand_raises=[(1000, 3000, "BOTH")]
    )
    sks = skeletons(sc)
    ch = challenge(B, 0, 5000)
    ev = LivenessEvaluator(ch, cfg.liveness, cfg.features.min_visibility)
    out = None
    for s in sks:
        out = ev.update(s)
        if out is not None:
            break
    assert ev.done and out == evaluate_liveness(ch, sks, cfg.liveness, cfg.features.min_visibility)
    assert ev.update(sks[-1]) == out


def test_empty_window_is_no_person(cfg: EngineConfig) -> None:
    ch = challenge(L, 0, 1000)
    res = evaluate_liveness(ch, [], cfg.liveness, cfg.features.min_visibility)
    assert res.status is LivenessStatus.FAILED_NO_PERSON
    assert res.to_dict()["evidence"]["validFrameRatio"] == 0.0


def test_issue_challenge() -> None:
    seen = set()
    for _ in range(60):
        c = issue_challenge()
        assert c.instruction == INSTRUCTIONS[c.action]
        assert len(c.challenge_id) == 24
        seen.add(c.action)
    assert seen == set(LivenessAction)
