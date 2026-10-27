from __future__ import annotations

from server.agent.tools.schemas import TrainingFactIssue
from server.schemas.training_read import RecentTrainingRead


def check_recent_training_facts(
    recent: RecentTrainingRead, *, visible_limit: int
) -> tuple[bool, list[TrainingFactIssue]]:
    """Check one canonical range without inventing a replacement metric."""

    issues: list[TrainingFactIssue] = []
    details_complete = recent.total_sessions <= visible_limit
    if not details_complete:
        issues.append(TrainingFactIssue(
            code="TRAINING_DETAILS_TRUNCATED",
            message="汇总覆盖完整时间范围，但明细受展示上限限制，不能用可见明细重新计算汇总。",
            affected_metrics=["total_sessions", "total_distance_km"],
        ))
    if recent.start_date and recent.end_date:
        if any(not (recent.start_date <= item.date <= recent.end_date) for item in recent.items):
            issues.append(TrainingFactIssue(
                code="TRAINING_DATE_OUTSIDE_RANGE",
                message="训练明细中存在超出统计时间范围的日期，相关汇总暂不用于确定性结论。",
                affected_metrics=["total_sessions", "total_distance_km", "plan_execution"],
            ))
    if details_complete and len(recent.items) != recent.total_sessions:
        issues.append(TrainingFactIssue(
            code="SESSION_SUMMARY_DETAIL_MISMATCH",
            message="训练次数汇总与完整明细数量不一致。",
            affected_metrics=["total_sessions"],
        ))
    distances = [item.distance_km for item in recent.items]
    if (
        details_complete
        and recent.total_distance_km is not None
        and distances
        and all(value is not None for value in distances)
        and abs(sum(float(value) for value in distances if value is not None) - recent.total_distance_km) > 0.02
    ):
        issues.append(TrainingFactIssue(
            code="DISTANCE_SUMMARY_DETAIL_MISMATCH",
            message="跑量汇总与相同区间的完整明细加总不一致。",
            affected_metrics=["total_distance_km"],
        ))
    if recent.unresolved_activity_count:
        issues.append(TrainingFactIssue(
            code="UNRESOLVED_ACTIVITIES_PRESENT",
            message=f"该时间范围内有 {recent.unresolved_activity_count} 条设备活动尚待确认关联。",
            affected_metrics=["plan_execution", "completion_rate"],
        ))
    if recent.duplicate_candidate_count:
        issues.append(TrainingFactIssue(
            code="DUPLICATE_ACTIVITY_CANDIDATES",
            message="检测到可能重复的稳定活动标识，相关汇总不应用于确定性结论。",
            affected_metrics=["total_sessions", "total_distance_km"],
        ))
    if recent.cross_date_association_count:
        issues.append(TrainingFactIssue(
            code="CROSS_DATE_ASSOCIATIONS_PRESENT",
            message=f"有 {recent.cross_date_association_count} 次训练的实际日期与计划日期不同，已分别保留。",
            affected_metrics=["plan_execution"],
        ))
    return details_complete, issues
