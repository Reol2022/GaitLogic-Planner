from server.schemas.weekly_review import WeeklyReviewMetrics
from server.services.training_status_service import evaluate_training_status


def metrics(**overrides):
    values = dict(
        week_start_date="2026-06-08", week_end_date="2026-06-14", is_week_complete=True,
        planned_distance_km=70, actual_distance_km=66, completion_rate=0.94,
        planned_workout_days=6, completed_workout_days=6, completed_high_count=1,
        completed_normal_count=4, completed_adjusted_count=1, missed_count=0, rest_count=1,
        skipped_count=0, avg_rpe=6.5, key_workout_avg_rpe=7, max_pain_level=0,
        recent_7d_distance_km=66, recent_28d_weekly_avg_km=64, load_change_percentage=3.1,
        logged_workout_ratio=1, valid_log_count=6,
    )
    values.update(overrides)
    return WeeklyReviewMetrics(**values)


def test_no_logs_is_insufficient_data():
    assert evaluate_training_status(metrics(valid_log_count=0, logged_workout_ratio=0)).status.value == "insufficient_data"


def test_normal_week_is_normal_without_optional_recovery_data():
    result = evaluate_training_status(metrics(missing_fields=["hrv", "sleep_hours"]))
    assert result.status.value == "normal"
    assert not any("概率" in reason for reason in result.reasons)


def test_multiple_mild_signals_return_watch():
    result = evaluate_training_status(metrics(load_change_percentage=18, key_workout_avg_rpe=8.2))
    assert result.status.value == "watch"
    assert len(result.signals) >= 2


def test_pain_high_rpe_and_load_increase_return_reduce_load():
    result = evaluate_training_status(
        metrics(max_pain_level=3, key_workout_avg_rpe=9.2, load_change_percentage=30)
    )
    assert result.status.value == "reduce_load"


def test_single_mild_signal_does_not_reduce_load():
    result = evaluate_training_status(metrics(load_change_percentage=18))
    assert result.status.value == "normal"
