from __future__ import annotations

from enum import Enum


class KnowledgeStatus(str, Enum):
    draft = "draft"
    active = "active"
    deprecated = "deprecated"
    archived = "archived"


class EvidenceLevel(str, Enum):
    product_rule = "product_rule"
    reference_summary = "reference_summary"
    consensus = "consensus"
    unknown = "unknown"
    high = "high"
    moderate = "moderate"
    limited = "limited"
    expert_consensus = "expert_consensus"
    product_assumption = "product_assumption"
    not_applicable = "not_applicable"


class RuleSeverity(str, Enum):
    info = "info"
    notice = "notice"
    caution = "caution"
    high = "high"
    blocking = "blocking"


class RuleSourceType(str, Enum):
    scientific_reference = "scientific_reference"
    product_rule = "product_rule"
    safety_boundary = "safety_boundary"
    system_default = "system_default"
    peer_reviewed_article = "peer_reviewed_article"
    systematic_review = "systematic_review"
    meta_analysis = "meta_analysis"
    consensus_statement = "consensus_statement"
    textbook = "textbook"
    official_guideline = "official_guideline"
    public_dataset = "public_dataset"
    expert_practice = "expert_practice"


class RuleLifecycleStatus(str, Enum):
    draft = "draft"
    in_review = "in_review"
    approved = "approved"
    published = "published"
    deprecated = "deprecated"
    retired = "retired"
    rejected = "rejected"


class RuleEvaluationStatus(str, Enum):
    matched = "matched"
    not_matched = "not_matched"
    not_applicable = "not_applicable"
    insufficient_data = "insufficient_data"
    error = "error"


class RuleAction(str, Enum):
    no_action = "no_action"
    show_info = "show_info"
    keep_plan = "keep_plan"
    monitor = "monitor"
    adjust_recommended = "adjust_recommended"
    downgrade_recommended = "downgrade_recommended"
    rest_recommended = "rest_recommended"
    require_user_review = "require_user_review"
    block_auto_apply = "block_auto_apply"
    workout_completed_as_planned = "workout_completed_as_planned"
    workout_completed_with_adjustment = "workout_completed_with_adjustment"
    workout_load_higher_than_planned = "workout_load_higher_than_planned"
    workout_load_lower_than_planned = "workout_load_lower_than_planned"
    workout_incomplete = "workout_incomplete"
    recovery_attention_recommended = "recovery_attention_recommended"
    next_workout_review_required = "next_workout_review_required"


class ConditionOperator(str, Enum):
    eq = "eq"
    neq = "neq"
    gt = "gt"
    gte = "gte"
    lt = "lt"
    lte = "lte"
    in_ = "in"
    not_in = "not_in"
    exists = "exists"
    between = "between"


KNOWLEDGE_CATEGORIES = [
    "training_type",
    "training_component",
    "ability_dimension",
    "training_phase",
    "load_indicator",
    "recovery_indicator",
    "race_distance",
    "plan_structure",
    "risk_signal",
    "decision_action",
]

CONTEXT_TYPES = {
    "generic",
    "plan_validation",
    "daily_adjustment",
    "workout_review",
    "weekly_review",
}

SEVERITY_WEIGHT = {
    RuleSeverity.info.value: 10,
    RuleSeverity.notice.value: 20,
    RuleSeverity.caution.value: 30,
    RuleSeverity.high.value: 40,
    RuleSeverity.blocking.value: 50,
}

ACTION_STRICTNESS = {
    RuleAction.no_action.value: 0,
    RuleAction.show_info.value: 10,
    RuleAction.keep_plan.value: 20,
    RuleAction.monitor.value: 30,
    RuleAction.adjust_recommended.value: 40,
    RuleAction.downgrade_recommended.value: 50,
    RuleAction.rest_recommended.value: 60,
    RuleAction.require_user_review.value: 70,
    RuleAction.block_auto_apply.value: 80,
    RuleAction.workout_completed_as_planned.value: 20,
    RuleAction.workout_completed_with_adjustment.value: 30,
    RuleAction.workout_load_higher_than_planned.value: 40,
    RuleAction.workout_load_lower_than_planned.value: 30,
    RuleAction.workout_incomplete.value: 50,
    RuleAction.recovery_attention_recommended.value: 50,
    RuleAction.next_workout_review_required.value: 60,
}
