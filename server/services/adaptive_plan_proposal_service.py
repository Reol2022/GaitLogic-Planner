from __future__ import annotations

from datetime import datetime, timezone

from planner_core.adaptive_plan.schemas import (
    PlanAdjustmentChange,
    PlanAdjustmentProposal,
    ProposalCandidateChange,
    TargetPlanFact,
)
from planner_core.enums import PlanAdjustmentAction
from planner_core.weekly_review.enums import (
    WeeklyClassificationStatus,
    WeeklyDataQualityLevel,
)
from planner_core.weekly_review.schemas import WeeklyFacts
from server.common.exceptions import BadRequestError
from server.domain.review_thresholds import HIGH_INTENSITY_TYPES
from server.services.plan_adjustment_validation_service import (
    INTENSITY_RANK,
    MAX_WEEKLY_INCREASE_RATIO,
)


class AdaptivePlanProposalService:
    """Validate and materialize a proposal without opening a DB transaction."""

    def create_proposal(
        self,
        *,
        user_id: int,
        weekly_facts: WeeklyFacts,
        target_plans: list[TargetPlanFact],
        candidates: list[ProposalCandidateChange],
    ) -> PlanAdjustmentProposal:
        by_id = {item.plan_id: item for item in target_plans}
        if len(by_id) != len(target_plans):
            raise BadRequestError("Target plan facts contain duplicate IDs.")
        if any(item.user_id != user_id for item in target_plans):
            raise BadRequestError("Target plans must belong to the authenticated user.")
        if weekly_facts.data_quality.level in {
            WeeklyDataQualityLevel.INSUFFICIENT,
            WeeklyDataQualityLevel.CONFLICTED,
        } and candidates:
            raise BadRequestError("Insufficient or conflicted facts cannot produce deterministic adjustments.")

        changes: list[PlanAdjustmentChange] = []
        seen: set[int] = set()
        for candidate in candidates:
            if candidate.plan_id in seen:
                raise BadRequestError("A plan may only be adjusted once per proposal.")
            seen.add(candidate.plan_id)
            target = by_id.get(candidate.plan_id)
            if target is None:
                raise BadRequestError("Proposal references a plan outside the target week.")
            if target.is_locked or target.is_completed:
                raise BadRequestError("Locked or completed plans cannot be proposed for change.")
            self._validate_change(weekly_facts, target, candidate)
            changes.append(
                PlanAdjustmentChange(
                    date=target.workout_date,
                    plan_id=target.plan_id,
                    action=candidate.action,
                    before=target.value,
                    after=candidate.after,
                    reason=candidate.reason,
                    rule_evidence=candidate.rule_evidence,
                )
            )

        self._validate_resulting_week(weekly_facts, target_plans, changes)
        limitations = list(weekly_facts.classification.limitations)
        if not changes:
            limitations.append("NO_RULE_VALIDATED_PLAN_CHANGE")
        return PlanAdjustmentProposal(
            user_id=user_id,
            week_start=weekly_facts.period.week_start,
            week_end=weekly_facts.period.week_end,
            reason_codes=weekly_facts.classification.rule_codes,
            changes=changes,
            warnings=weekly_facts.classification.warnings,
            limitations=list(dict.fromkeys(limitations)),
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _validate_change(
        facts: WeeklyFacts,
        target: TargetPlanFact,
        candidate: ProposalCandidateChange,
    ) -> None:
        before = target.value
        after = candidate.after
        if candidate.action == PlanAdjustmentAction.keep and after != before:
            raise BadRequestError("Keep must preserve the original plan.")
        if candidate.action == PlanAdjustmentAction.reduce:
            if before.distance_km is None or after.distance_km is None:
                raise BadRequestError("A distance reduction requires structured distances.")
            if after.distance_km > before.distance_km:
                raise BadRequestError("A reduce action cannot increase distance.")
        if candidate.action == PlanAdjustmentAction.rest and (
            after.distance_km not in {0, 0.0} or after.main_type != "rest"
        ):
            raise BadRequestError("A rest action must use rest with zero distance.")
        fatigue = facts.runner_state_trend.fatigue_level
        if fatigue in {"ELEVATED", "HIGH"}:
            if (after.distance_km or 0) > (before.distance_km or 0):
                raise BadRequestError("Elevated fatigue cannot increase planned distance.")
            if INTENSITY_RANK.get(after.main_type, 99) > INTENSITY_RANK.get(before.main_type, 99):
                raise BadRequestError("Elevated fatigue cannot increase workout intensity.")

    @staticmethod
    def _validate_resulting_week(
        facts: WeeklyFacts,
        targets: list[TargetPlanFact],
        changes: list[PlanAdjustmentChange],
    ) -> None:
        by_id = {item.plan_id: item.after for item in changes}
        before_total = sum(item.value.distance_km or 0 for item in targets)
        after_values = [by_id.get(item.plan_id, item.value) for item in targets]
        after_total = sum(item.distance_km or 0 for item in after_values)
        if before_total and after_total > before_total * MAX_WEEKLY_INCREASE_RATIO:
            raise BadRequestError("Proposal exceeds the existing weekly increase boundary.")
        status = facts.classification.primary_status
        if status in {
            WeeklyClassificationStatus.RECOVERY_CONCERN,
            WeeklyClassificationStatus.OVER_COMPLETED,
        } and after_total > before_total:
            raise BadRequestError("Recovery or over-completion concern cannot increase next-week volume.")
        ordered = sorted(
            (
                target.workout_date,
                by_id.get(target.plan_id, target.value).main_type,
            )
            for target in targets
        )
        high_dates = [day for day, kind in ordered if kind in HIGH_INTENSITY_TYPES]
        if any((right - left).days == 1 for left, right in zip(high_dates, high_dates[1:])):
            raise BadRequestError("Proposal cannot create consecutive high-intensity days.")
