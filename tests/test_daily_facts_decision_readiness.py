from server.services.training_facts.daily_facts import _data_limited


def test_missing_recovery_fields_do_not_globally_block_today_decision() -> None:
    facts = {
        "recovery": {
            "sleep_hours": None,
            "leg_feel": None,
            "subjective_fatigue": None,
        },
        "recent_training": {
            "missing_data": ["duration_or_rpe", "recovery_checkins"],
        },
    }

    assert _data_limited(facts) is False


def test_missing_training_logs_remain_a_core_today_blocker() -> None:
    assert _data_limited({"recent_training": {"missing_data": ["training_logs"]}}) is True


def test_failed_load_collection_remains_a_core_today_blocker() -> None:
    assert _data_limited({"recent_training": {"core_data_unavailable": True}}) is True
