from __future__ import annotations

from planner_core.enums import TrainingStatus
from server.domain import review_thresholds as thresholds
from server.schemas.weekly_review import TrainingStatusResult, WeeklyReviewMetrics


def evaluate_training_status(metrics: WeeklyReviewMetrics) -> TrainingStatusResult:
    missing = list(metrics.missing_fields)
    if metrics.valid_log_count == 0:
        return TrainingStatusResult(
            status=TrainingStatus.insufficient_data,
            reasons=["本周没有有效训练日志，当前只能展示计划与基础统计。"],
            signals=[],
            missing_data=missing,
        )
    if metrics.logged_workout_ratio < thresholds.MIN_LOGGED_WORKOUT_RATIO:
        return TrainingStatusResult(
            status=TrainingStatus.insufficient_data,
            reasons=["训练日志填写比例较低，现有数据不足以形成可靠训练状态判断。"],
            signals=[{"code": "low_log_coverage", "level": "data", "message": "训练日志覆盖率较低"}],
            missing_data=missing,
        )

    signals: list[dict[str, str]] = []

    def add(code: str, level: str, message: str) -> None:
        signals.append({"code": code, "level": level, "message": message})

    if metrics.load_change_percentage is not None:
        if metrics.load_change_percentage >= thresholds.LOAD_INCREASE_STRONG_PERCENT:
            add("rapid_load_increase", "strong", "最近 7 天跑量较近 28 天周均明显增加")
        elif metrics.load_change_percentage >= thresholds.LOAD_INCREASE_WATCH_PERCENT:
            add("load_increase", "watch", "最近 7 天跑量增幅偏高")
    if metrics.key_workout_avg_rpe is not None:
        if metrics.key_workout_avg_rpe >= thresholds.VERY_HIGH_RPE:
            add("very_high_key_rpe", "strong", "关键课平均 RPE 很高")
        elif metrics.key_workout_avg_rpe >= thresholds.HIGH_RPE:
            add("high_key_rpe", "watch", "关键课平均 RPE 偏高")
    if metrics.max_pain_level is not None:
        if metrics.max_pain_level >= thresholds.PAIN_STRONG_LEVEL:
            add("pain_increase", "strong", "记录到较明显疼痛，应优先保守处理")
        elif metrics.max_pain_level >= thresholds.PAIN_WATCH_LEVEL:
            add("mild_pain", "watch", "记录到轻度疼痛，需要持续观察")
    if metrics.completed_adjusted_count >= thresholds.MULTIPLE_ADJUSTED_COUNT:
        add("multiple_adjusted", "watch", "本周多次降级完成训练")
    if metrics.missed_count + metrics.skipped_count >= thresholds.MULTIPLE_MISSED_COUNT:
        add("multiple_missed", "watch", "本周多次未完成或跳过训练")
    if metrics.completion_rate < thresholds.VERY_LOW_COMPLETION_RATE:
        add("very_low_completion", "strong", "本周跑量完成率明显偏低")
    elif metrics.completion_rate < thresholds.LOW_COMPLETION_RATE:
        add("low_completion", "watch", "本周跑量完成率偏低")
    if metrics.consecutive_high_intensity_days:
        add("consecutive_intensity", "watch", "存在连续两天完成高强度训练")
    if metrics.avg_sleep_hours is not None and metrics.avg_sleep_hours < thresholds.LOW_SLEEP_HOURS:
        add("low_sleep", "watch", "已记录的平均睡眠时长偏少")

    strong_count = sum(item["level"] == "strong" for item in signals)
    watch_count = sum(item["level"] == "watch" for item in signals)
    has_pain = any(item["code"] == "pain_increase" for item in signals)
    has_effort_or_load = any(
        item["code"] in {"rapid_load_increase", "very_high_key_rpe", "very_low_completion", "multiple_adjusted"}
        for item in signals
    )

    if (has_pain and has_effort_or_load) or strong_count >= 2 or (strong_count >= 1 and watch_count >= 2):
        status = TrainingStatus.reduce_load
        reasons = ["多个较强异常信号同时出现，下一周建议降低负荷并优先关注恢复。"]
    elif watch_count >= 2 or strong_count >= 1:
        status = TrainingStatus.watch
        reasons = ["出现多个需要关注的训练或恢复信号，下一周应保持保守并观察变化。"]
    else:
        status = TrainingStatus.normal
        reasons = ["现有训练记录未显示需要明显降负荷的组合信号。"]

    reasons.extend(item["message"] for item in signals)
    if missing:
        reasons.append("部分恢复数据缺失，判断仅基于当前已有记录。")
    return TrainingStatusResult(status=status, reasons=reasons, signals=signals, missing_data=missing)
