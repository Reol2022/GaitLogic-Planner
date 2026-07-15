from __future__ import annotations

from typing import Any

from planner_core.training_knowledge.condition_evaluator import ConditionEvaluator
from planner_core.training_knowledge.conflict_resolver import resolve_conflicts
from planner_core.training_knowledge.enums import RuleEvaluationStatus
from planner_core.training_knowledge.explanation import render_explanation
from planner_core.training_knowledge.governance import applicability_status
from planner_core.training_knowledge.schemas import EngineEvaluationResult, RuleEvaluationTrace, RuleHit, TrainingRuleDefinition

ENGINE_VERSION = "1.0.0"
DEFAULT_RULESET_VERSION = "1.0.0"


class TrainingRuleEngine:
    def __init__(
        self,
        evaluator: ConditionEvaluator | None = None,
        engine_version: str = ENGINE_VERSION,
        ruleset_version: str = DEFAULT_RULESET_VERSION,
    ) -> None:
        self.evaluator = evaluator or ConditionEvaluator()
        self.engine_version = engine_version
        self.ruleset_version = ruleset_version

    def evaluate(
        self,
        facts: dict[str, Any],
        rules: list[TrainingRuleDefinition],
        context_type: str,
    ) -> EngineEvaluationResult:
        matched_hits: list[RuleHit] = []
        traces: list[RuleEvaluationTrace] = []
        status_counts = {status.value: 0 for status in RuleEvaluationStatus}
        scoped = [
            rule
            for rule in rules
            if rule.enabled and rule.lifecycle_status.value == "published" and (rule.scope in {context_type, "generic", "all"})
        ]
        for rule in sorted(scoped, key=lambda item: (-item.priority, item.code)):
            applicability, reason, applicability_missing = applicability_status(rule, facts)
            if applicability in {RuleEvaluationStatus.not_applicable, RuleEvaluationStatus.insufficient_data}:
                status_counts[applicability.value] += 1
                traces.append(
                    RuleEvaluationTrace(
                        rule_code=rule.code,
                        rule_version=rule.version,
                        status=applicability,
                        reason=reason,
                        missing_fields=applicability_missing,
                    )
                )
                continue
            condition_result = self.evaluator.evaluate(rule.conditions, facts)
            if not condition_result.matched:
                status_counts[condition_result.status.value] += 1
                traces.append(
                    RuleEvaluationTrace(
                        rule_code=rule.code,
                        rule_version=rule.version,
                        status=condition_result.status,
                        missing_fields=condition_result.missing_fields,
                        errors=condition_result.errors,
                    )
                )
                continue
            status_counts[RuleEvaluationStatus.matched.value] += 1
            traces.append(
                RuleEvaluationTrace(
                    rule_code=rule.code,
                    rule_version=rule.version,
                    status=RuleEvaluationStatus.matched,
                    missing_fields=condition_result.missing_fields,
                    errors=condition_result.errors,
                )
            )
            output = rule.result.model_dump(mode="json")
            hit = RuleHit(
                rule_code=rule.code,
                rule_version=rule.version,
                matched=True,
                severity=rule.severity.value,
                priority=rule.priority,
                action=rule.result.action.value,
                recommendation=rule.result.recommendation,
                output=output,
                explanation=render_explanation(rule.explanation_template, facts),
                missing_fields=condition_result.missing_fields,
                errors=condition_result.errors,
            )
            matched_hits.append(hit)
        result = resolve_conflicts(
            context_type=context_type,
            hits=matched_hits,
            engine_version=self.engine_version,
            ruleset_version=self.ruleset_version,
        )
        result.rule_status_counts = status_counts
        result.rule_traces = traces
        return result
