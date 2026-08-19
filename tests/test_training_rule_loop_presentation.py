from datetime import datetime

from server.schemas.training_rules import TrainingRuleEvaluateResponse
from server.services.training_rule_loop_service import _as_app_timezone, _message


def test_naive_database_timestamp_is_presented_in_application_timezone() -> None:
    value = _as_app_timezone(datetime(2026, 8, 19, 5, 14, 2))

    assert value is not None
    assert value.isoformat() == "2026-08-19T13:14:02+08:00"


def test_no_action_message_discloses_partially_unevaluable_rules() -> None:
    evaluation = TrainingRuleEvaluateResponse(
        context_type="daily_adjustment",
        final_action="no_action",
        conflict_resolution={},
        rule_status_counts={"not_matched": 8, "insufficient_data": 1},
        engine_version="1.0.0",
        ruleset_version="1.0.0",
    )

    assert _message(evaluation) == "已完成可用数据范围内的评估，未触发需要调整的规则；部分指标因数据不足未参与判断。"
