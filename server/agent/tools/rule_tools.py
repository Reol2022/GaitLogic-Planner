from __future__ import annotations

from planner_core.training_knowledge.rule_engine import DEFAULT_RULESET_VERSION

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext, AgentNotice
from server.agent.tool import AgentTool
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.schemas import (
    EmptyToolInput,
    TodayEvaluationOutput,
    TodayEvaluationRuleHit,
    TrainingDataStatus,
    TrainingRulesInput,
    TrainingRulesOutput,
    TrainingRuleSummaryRead,
)
from server.services.weekly_review_stats_service import local_today

_SCOPE_MAP = {
    "TODAY": "daily_adjustment",
    "WEEK": "weekly_review",
    "RUNNER_STATE": "runner_state",
    "GENERAL": "generic",
}


def _clean(value: str | None, limit: int = 300) -> str | None:
    cleaned = " ".join(value.split()) if value else ""
    return cleaned[:limit] or None


def _notice(code: str, message: str) -> AgentNotice:
    return AgentNotice(code=code, message=message)


class GetTrainingRulesTool(AgentTool):
    name = "get_training_rules"
    description = "Read enabled public rule summaries for one fixed training scope."
    input_model = TrainingRulesInput
    output_model = TrainingRulesOutput
    allowed_intents = (
        AgentIntent.TODAY_RECOMMENDATION,
        AgentIntent.WEEKLY_REVIEW,
        AgentIntent.EXPLAIN_RUNNER_STATE,
        AgentIntent.GENERAL_TRAINING_QUESTION,
    )

    def __init__(self, dependencies: CoachAgentToolDependencies, *, rule_limit: int = 20) -> None:
        self.dependencies = dependencies
        self.rule_limit = rule_limit

    def execute(self, arguments: TrainingRulesInput, context: AgentContext) -> TrainingRulesOutput:
        del context
        rules, total = self.dependencies.training_rules(
            _SCOPE_MAP[arguments.scope], self.rule_limit
        )
        limitations = []
        if arguments.scope == "RUNNER_STATE" and not rules:
            limitations.append(
                _notice(
                    "RUNNER_STATE_RULE_SCOPE_UNAVAILABLE",
                    "No enabled public rule package uses the runner_state scope.",
                )
            )
        if total > self.rule_limit:
            limitations.append(_notice("RULE_LIST_TRIMMED", "Rule summaries were truncated."))
        return TrainingRulesOutput(
            data_status=(TrainingDataStatus.AVAILABLE if rules else TrainingDataStatus.NOT_FOUND),
            rules=[
                TrainingRuleSummaryRead(
                    rule_id=rule.code,
                    name=_clean(rule.name, 160) or rule.code,
                    category=rule.category,
                    summary=_clean(rule.description),
                    severity=rule.severity,
                    evidence_required=(rule.evidence_refs_json or [])[:20],
                )
                for rule in rules[: self.rule_limit]
            ],
            source_version=DEFAULT_RULESET_VERSION,
            limitations=limitations,
        )


class EvaluateTodayWorkoutTool(AgentTool):
    name = "evaluate_today_workout"
    description = "Run the existing public daily rule evaluation without persisting results or drafts."
    input_model = EmptyToolInput
    output_model = TodayEvaluationOutput
    allowed_intents = (AgentIntent.TODAY_RECOMMENDATION,)

    def __init__(self, dependencies: CoachAgentToolDependencies, *, item_limit: int = 20) -> None:
        self.dependencies = dependencies
        self.item_limit = item_limit

    def execute(self, arguments: EmptyToolInput, context: AgentContext) -> TodayEvaluationOutput:
        del arguments
        response = self.dependencies.evaluate_today(context.user_id, local_today())
        if response.data_limited:
            data_status = TrainingDataStatus.UNKNOWN
            decision = "UNKNOWN"
        else:
            data_status = TrainingDataStatus.AVAILABLE
            decision = response.validation_status
        counts = response.summary
        risk_level = (
            "UNKNOWN"
            if response.data_limited
            else "HIGH"
            if counts.blocking or counts.high
            else "MODERATE"
            if counts.caution
            else "LOW"
        )
        hits = response.evaluation.matched_rules[: self.item_limit]
        limitations = []
        if response.data_limited:
            limitations.append(
                _notice(
                    "DAILY_EVALUATION_DATA_LIMITED",
                    "The existing daily facts report insufficient data; no decision was inferred.",
                )
            )
        if len(response.evaluation.matched_rules) > self.item_limit:
            limitations.append(_notice("RULE_HITS_TRIMMED", "Rule hits were truncated."))
        return TodayEvaluationOutput(
            data_status=data_status,
            decision=decision,
            risk_level=risk_level,
            rule_hits=[
                TodayEvaluationRuleHit(
                    rule_code=hit.rule_code,
                    severity=hit.severity,
                    action=hit.action,
                    explanation=_clean(hit.explanation) or "Rule matched.",
                )
                for hit in hits
            ],
            evidence=[item for hit in hits for item in [*(hit.output.get("evidence", []) or [])] if isinstance(item, str)][: self.item_limit],
            warnings=(
                [_notice("TRAINING_REVIEW_RECOMMENDED", _clean(response.message) or "Review the current training context.")]
                if risk_level in {"MODERATE", "HIGH"}
                else []
            ),
            limitations=limitations,
        )
