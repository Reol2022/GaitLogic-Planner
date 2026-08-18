from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class LimitationClass(str, Enum):
    HARD_BLOCKER = "HARD_BLOCKER"
    SOFT_LIMITATION = "SOFT_LIMITATION"
    CAPABILITY_LIMITATION = "CAPABILITY_LIMITATION"


class DecisionReadiness(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


CAPABILITY_LIMITATIONS = frozenset({
    "recovery_day_fatigue_rule_disabled_v1",
    "near_zero_volume_baseline_cutoff_not_defined",
})

HARD_BLOCKER_CODES = frozenset({
    "TODAY_CONTEXT_INCOMPLETE",
    "TODAY_DATA_INSUFFICIENT",
    "WEEKLY_CORE_FACTS_UNAVAILABLE",
})

SOFT_LIMITATION_PREFIXES = (
    "rpe_incomplete_",
    "heart_rate_incomplete_",
    "training_phase_unavailable_",
    "intensity_distance_uses_",
    "high_intensity_composite_segments_",
    "composite_workout_intensity_segments_",
    "structured_segments_",
    "recovery_coverage_",
    "garmin_recovery_",
)


def classify_limitation(code: str) -> LimitationClass:
    if code in HARD_BLOCKER_CODES:
        return LimitationClass.HARD_BLOCKER
    if code in CAPABILITY_LIMITATIONS:
        return LimitationClass.CAPABILITY_LIMITATION
    if code.startswith(SOFT_LIMITATION_PREFIXES):
        return LimitationClass.SOFT_LIMITATION
    return LimitationClass.SOFT_LIMITATION


class DomainReadiness(BaseModel):
    domain: str
    readiness: DecisionReadiness
    limitations: list[str] = Field(default_factory=list)


def assess_runner_state_domains(*, valid_workouts: int, limitations: list[str]) -> list[DomainReadiness]:
    training = DecisionReadiness.READY if valid_workouts else DecisionReadiness.BLOCKED
    soft = [item for item in limitations if classify_limitation(item) == LimitationClass.SOFT_LIMITATION]
    capability = [item for item in limitations if classify_limitation(item) == LimitationClass.CAPABILITY_LIMITATION]
    return [
        DomainReadiness(domain="training_load", readiness=training),
        DomainReadiness(domain="intensity_distribution", readiness=DecisionReadiness.PARTIAL if soft else training, limitations=soft),
        DomainReadiness(domain="recovery", readiness=DecisionReadiness.PARTIAL if soft else DecisionReadiness.NOT_APPLICABLE, limitations=soft),
        DomainReadiness(domain="subjective_fatigue", readiness=DecisionReadiness.BLOCKED if any(item.startswith("rpe_incomplete") for item in soft) else training),
        DomainReadiness(domain="training_phase", readiness=DecisionReadiness.BLOCKED, limitations=[item for item in soft if item.startswith("training_phase_")]),
        DomainReadiness(domain="system_capability", readiness=DecisionReadiness.NOT_APPLICABLE, limitations=capability),
    ]


def overall_readiness(domains: list[DomainReadiness]) -> DecisionReadiness:
    usable = [item.readiness for item in domains if item.readiness in {DecisionReadiness.READY, DecisionReadiness.PARTIAL}]
    if not usable:
        return DecisionReadiness.BLOCKED
    return DecisionReadiness.PARTIAL if DecisionReadiness.PARTIAL in usable or any(item.readiness == DecisionReadiness.BLOCKED for item in domains) else DecisionReadiness.READY
