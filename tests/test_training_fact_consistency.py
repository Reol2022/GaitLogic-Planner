from datetime import date

from server.agent.training_fact_consistency import check_recent_training_facts
from server.schemas.training_read import RecentTrainingRead, RecentTrainingSessionRead


def _session(day: date, distance: float) -> RecentTrainingSessionRead:
    return RecentTrainingSessionRead(
        date=day,
        training_type="easy",
        planned_or_unplanned="UNPLANNED",
        completion_status="completed_normal",
        distance_km=distance,
        source="GARMIN",
    )


def test_detects_same_range_summary_conflicts_without_replacing_the_value() -> None:
    facts = RecentTrainingRead(
        as_of_date=date(2026, 10, 26),
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 26),
        window_days=26,
        items=[_session(date(2026, 10, 20), 8), _session(date(2026, 10, 21), 10)],
        total_sessions=2,
        total_distance_km=25,
        completed_key_sessions=0,
        rest_days=0,
    )
    complete, issues = check_recent_training_facts(facts, visible_limit=20)
    assert complete is True
    assert {item.code for item in issues} == {"DISTANCE_SUMMARY_DETAIL_MISMATCH"}
    assert facts.total_distance_km == 25


def test_flags_window_leak_and_local_association_gaps_without_discarding_other_facts() -> None:
    facts = RecentTrainingRead(
        as_of_date=date(2026, 10, 26),
        start_date=date(2026, 10, 20),
        end_date=date(2026, 10, 26),
        window_days=7,
        items=[_session(date(2026, 10, 19), 8)],
        total_sessions=1,
        total_distance_km=8,
        completed_key_sessions=0,
        rest_days=0,
        unresolved_activity_count=1,
    )
    _complete, issues = check_recent_training_facts(facts, visible_limit=20)
    assert {item.code for item in issues} == {
        "TRAINING_DATE_OUTSIDE_RANGE",
        "UNRESOLVED_ACTIVITIES_PRESENT",
    }
