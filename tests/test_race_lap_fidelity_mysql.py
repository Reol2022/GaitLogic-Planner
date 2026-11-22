from sqlalchemy import delete, select
from tests.test_mcp_facts_v3_mysql import engine, sample
from tests.test_race_lap_fidelity import payloads
from server.integrations.activity_provider.garmin import _activity_from_payload, _laps_from_payload
from server.services.garmin_sync_service import _copy_activity_metrics, _replace_laps
from server.mcp.facts_v2 import read_training_detail
from planner_core.database.models import ExternalActivityLap, ExternalActivityRaw


def candidate(activity, event='uncategorized', *, details=True):
    summary, splits = payloads(event)
    summary['activityId'] = activity.external_activity_id
    value = _activity_from_payload({**summary['summaryDTO'], **summary})
    if details:
        value.laps = _laps_from_payload(splits)
        value.raw_payload['garmin_splits'] = splits
    return value


def test_provider_persistence_normalizer_mcp_and_list_refresh_preserve_22_laps(sample):
    db, users, _, activities = sample
    activity = activities[1]
    db.execute(delete(ExternalActivityLap).where(ExternalActivityLap.external_activity_id == activity.id))
    detail = candidate(activity)
    _copy_activity_metrics(activity, detail)
    _replace_laps(db, activity, detail)
    db.commit()
    expected = list(db.scalars(select(ExternalActivityLap.id).where(ExternalActivityLap.external_activity_id == activity.id)))
    assert len(expected) == 22
    # Reproduce detail import -> later list-only summaries, without deleting detail.
    _replace_laps(db, activity, candidate(activity, details=False))
    db.commit()
    result = read_training_detail(db, users[0].id, f'external_activity:{activity.id}')
    assert len(result.segments) == len(result.normalized_segments) == 22
    assert result.raw_segments_complete and result.normalized_structure_complete
    assert result.segment_distance_consistent and result.segment_validation['time_consistent']
    assert result.segment_validation['detail_status'] == 'COMPLETE'
    assert result.normalized_segments[-1].distance_m == 250
    assert result.activity_classification['primary_type'] == 'UNKNOWN'
    assert result.activity_classification['event_type'] == 'uncategorized'
    assert result.segment_storage['reason'] == 'COARSER_REPRESENTATION'
    assert not any(issue.code == 'LAP_ACTIVITY_DISTANCE_MISMATCH' for issue in result.fact_issues)
    assert list(db.scalars(select(ExternalActivityLap.id).where(ExternalActivityLap.external_activity_id == activity.id))) == expected
    from scripts.verify_stored_activity_laps import verify
    receipt = verify(db, user_id=users[0].id, activity_id=activity.id, expected_date=activity.activity_date, minimum_laps=22)
    assert receipt['status'] == 'PASS' and receipt['approximately_kilometre_rows'] == 21


def test_summary_only_and_mixed_views_have_truthful_completeness(sample):
    db, users, _, activities = sample
    activity = activities[0]
    detail = candidate(activity, details=False)
    _copy_activity_metrics(activity, detail)
    _replace_laps(db, activity, detail)
    db.commit()
    result = read_training_detail(db, users[0].id, f'external_activity:{activity.id}')
    assert result.raw_segments_complete and not result.normalized_structure_complete
    assert result.raw_segment_distance_consistent is False
    assert result.segment_distance_consistent is None
    assert result.segment_validation['detail_status'] == 'SUMMARY_ONLY'
    assert result.normalized_segments == []
    assert [issue.code for issue in result.fact_issues] == ['LAP_DETAIL_UNAVAILABLE']
    # A legacy mixed view has non-additive summaries but complete detail.
    full = candidate(activity)
    rollups = candidate(activity, details=False).laps
    for index, row in enumerate(rollups, start=23):
        row.lap_index = index
    full.laps.extend(rollups)
    _replace_laps(db, activity, full)
    db.commit()
    result = read_training_detail(db, users[0].id, f'external_activity:{activity.id}')
    assert result.raw_segment_distance_consistent is False and result.segment_distance_consistent is True
    assert result.normalized_structure_complete and len(result.normalized_segments) == 22
    assert not any(issue.code == 'LAP_ACTIVITY_DISTANCE_MISMATCH' for issue in result.fact_issues)


def test_historical_raw_event_label_is_projected_without_private_payload(sample):
    db, users, _, activities = sample
    activity = activities[0]
    raw = ExternalActivityRaw(user_id=users[0].id, connection_id=activity.connection_id, provider='garmin',
        external_activity_id=activity.external_activity_id, payload_hash='synthetic-race-label',
        raw_payload_json={'eventTypeDTO': {'typeKey':'race'}, 'description':'PRIVATE_SENTINEL', 'gps':'PRIVATE_SENTINEL'})
    db.add(raw); db.flush()
    activity.raw_activity_id = raw.id
    db.commit()
    result = read_training_detail(db, users[0].id, f'external_activity:{activity.id}')
    assert result.activity_classification['primary_type'] == 'race'
    assert result.selected_activity.actual_training_type == 'race'
    assert not result.normalized_structure_complete
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()
    # Another user's raw row cannot supply the classification.
    raw.user_id = users[1].id
    db.commit()
    assert read_training_detail(db, users[0].id, f'external_activity:{activity.id}').activity_classification['primary_type'] == 'UNKNOWN'


def test_coach_context_truncation_does_not_erase_independent_race_label(sample):
    from types import SimpleNamespace
    from server.integrations.activity_provider.base import ProviderLap
    from server.agent.tools.workout_detail import GetWorkoutDetailTool, WorkoutDetailInput
    db, users, _, activities = sample
    activity = activities[0]
    value = candidate(activity, event='race')
    value.distance_m = 22000
    value.duration_seconds = value.timer_time_seconds = 4400
    value.laps = [ProviderLap(lap_index=i+1, distance_m=500, duration_seconds=100,
        timer_time_seconds=100, start_offset_seconds=i*100, classification_source='garmin_lap_dto') for i in range(44)]
    _copy_activity_metrics(activity, value)
    _replace_laps(db, activity, value)
    db.commit()
    result = GetWorkoutDetailTool(SimpleNamespace(db=db)).execute(
        WorkoutDetailInput(record_ref=f'external_activity:{activity.id}'), SimpleNamespace(user_id=users[0].id))
    assert len(result.normalized_segments) == 24 and not result.normalized_structure_complete
    assert result.segment_validation['detail_status'] == 'PARTIAL'
    assert result.activity_classification['primary_type'] == 'race'
