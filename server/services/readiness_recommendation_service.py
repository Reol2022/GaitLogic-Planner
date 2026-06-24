from __future__ import annotations

from planner_core.enums import TrainingStatus
from server.schemas.training_readiness import ReadinessRecommendation


def build_recommendations(status: TrainingStatus, *, has_pain_signal: bool = False) -> list[ReadinessRecommendation]:
    if status == TrainingStatus.insufficient_data:
        return [
            ReadinessRecommendation(
                action="monitor",
                message="继续记录训练时长、RPE 和恢复状态，当前不建议大幅调整正式计划。",
                reason="数据不足时不默认状态正常，也不生成激进调整。",
            )
        ]
    if status == TrainingStatus.normal:
        return [
            ReadinessRecommendation(
                action="maintain_plan",
                message="按原计划执行，不额外增加计划外训练。",
                reason="现有记录未显示需要明显调整的组合信号。",
            ),
            ReadinessRecommendation(
                action="monitor",
                message="继续记录 RPE 和恢复状态。",
                reason="训练状态参考依赖连续记录。",
            ),
        ]
    if status == TrainingStatus.watch:
        recommendations = [
            ReadinessRecommendation(
                action="remove_optional_volume",
                message="暂不增加计划外跑量，取消可选附加训练。",
                reason="当前存在需要关注的负荷或恢复信号。",
            ),
            ReadinessRecommendation(
                action="monitor",
                message="下一次关键课前重新填写恢复状态。",
                reason="需要观察信号是否持续。",
            ),
        ]
        if has_pain_signal:
            recommendations.append(
                ReadinessRecommendation(
                    action="seek_professional_evaluation",
                    message="疼痛持续或加重时，请暂停高强度训练，并寻求具备资质的医疗或康复专业人员评估。",
                    reason="疼痛信号不应被其他正常指标抵消。",
                )
            )
        return recommendations
    recommendations = [
        ReadinessRecommendation(
            action="reduce_quality_volume",
            message="减少下一次高强度训练内容，必要时改为轻松跑或休息。",
            reason="当前组合信号提示应优先保守处理。",
        ),
        ReadinessRecommendation(
            action="replace_quality_with_easy",
            message="下一周调整草稿不得增加总负荷或高强度距离，所有调整需要你确认后才会应用。",
            reason="系统不能自动修改正式训练计划。",
        ),
    ]
    if has_pain_signal:
        recommendations.append(
            ReadinessRecommendation(
                action="seek_professional_evaluation",
                message="疼痛明显、持续或影响步态时，请暂停高强度训练，并寻求具备资质的医疗或康复专业人员评估。",
                reason="疼痛属于高优先级信号。",
            )
        )
    return recommendations
