from server.domain.decision_readiness import (
    DecisionReadiness,
    LimitationClass,
    assess_runner_state_domains,
    classify_limitation,
    overall_readiness,
)


def test_known_limitations_have_stable_categories() -> None:
    assert classify_limitation("rpe_incomplete_7d") == LimitationClass.SOFT_LIMITATION
    assert classify_limitation("training_phase_unavailable_no_structured_cycle_phase") == LimitationClass.SOFT_LIMITATION
    assert classify_limitation("recovery_day_fatigue_rule_disabled_v1") == LimitationClass.CAPABILITY_LIMITATION
    assert classify_limitation("near_zero_volume_baseline_cutoff_not_defined") == LimitationClass.CAPABILITY_LIMITATION
    assert classify_limitation("intensity_distance_uses_main_workout_type") == LimitationClass.SOFT_LIMITATION
    assert classify_limitation("structured_segments_unavailable") == LimitationClass.SOFT_LIMITATION
    assert classify_limitation("garmin_recovery_partial") == LimitationClass.SOFT_LIMITATION
    assert classify_limitation("TODAY_CONTEXT_INCOMPLETE") == LimitationClass.HARD_BLOCKER


def test_soft_missing_rpe_does_not_globally_block_training_analysis() -> None:
    domains = assess_runner_state_domains(valid_workouts=5, limitations=["rpe_incomplete_7d"])
    assert next(item for item in domains if item.domain == "training_load").readiness == DecisionReadiness.READY
    assert overall_readiness(domains) == DecisionReadiness.PARTIAL


def test_no_training_facts_is_blocked() -> None:
    domains = assess_runner_state_domains(valid_workouts=0, limitations=[])
    assert overall_readiness(domains) == DecisionReadiness.BLOCKED
