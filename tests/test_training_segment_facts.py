"""Synthetic structures only; not copied from a runner's session."""
from datetime import datetime, timedelta
from types import SimpleNamespace as Row
from decimal import Decimal
from server.integrations.activity_provider.garmin import _laps_from_payload
from server.services.training_segment_facts import normalize_segments, classify_segments
from server.services.garmin_sync_service import _desensitize_payload


def lap(index, *, distance=600, seconds=150, start=None, kind=None, step='ACTIVE', identity=None):
    return Row(lap_index=index, distance_m=Decimal(distance), duration_seconds=seconds,
        timer_time_seconds=seconds, start_offset_seconds=start, start_time=None,
        lap_type=kind, workout_step_type=step, classification_source='garmin_lap_dto',
        external_lap_id=identity, segment_role='unknown')


def test_classified_summary_rows_are_not_individual_segments():
    rows = _laps_from_payload({'splitSummaries':[{'splitType':'INTERVAL_ACTIVE','distance':1800,'duration':450},
        {'splitType':'RWD_RUN','distance':2100,'duration':550}]})
    assert all(r.segment_role == 'summary' for r in rows)
    normalized, valid = normalize_segments(Row(distance_m=2100,duration_seconds=550), rows)
    assert not normalized and not valid['structure_complete']
    assert valid['excluded_summary_count'] == 2


def test_legacy_rollups_without_source_tag_are_withheld():
    values = [lap(1,kind='INTERVAL_ACTIVE'),lap(2,kind='RWD_RUN')]
    for v in values:
        v.classification_source='garmin_manual_lap'
    normalized, valid = normalize_segments(Row(distance_m=600,duration_seconds=150),values)
    assert normalized == [] and not valid['structure_complete']
    assert classify_segments(normalized, valid)['primary_type'] == 'UNKNOWN'


def test_complete_work_and_recovery_structure_retains_each_actual_lap():
    values = [lap(1,start=0),lap(2,distance=100,seconds=60,start=150,step='RECOVERY'),lap(3,start=210)]
    normalized, valid = normalize_segments(Row(distance_m=1300,timer_time_seconds=360),values)
    assert valid['structure_complete'] and valid['distance_consistent'] and valid['time_consistent']
    classified=classify_segments(normalized,valid)
    assert classified['primary_type']=='interval_speed' and len(classified['components']) == 2
    assert [r['lap_index'] for r in classified['components']] == [1,3]


def test_same_distance_repetitions_are_not_deduplicated_by_distance_alone():
    values = [lap(1),lap(2),lap(3)]
    normalized, valid=normalize_segments(Row(distance_m=1800,duration_seconds=450),values)
    assert len(normalized)==3 and valid['deduplicated_count']==0


def test_duplicate_identity_is_excluded_without_mutating_raw_rows():
    values=[lap(1,start=0,identity='synthetic-lap'),lap(2,start=0,identity='synthetic-lap')]
    normalized,valid=normalize_segments(Row(distance_m=600,duration_seconds=150),values)
    assert len(values)==2 and len(normalized)==1 and valid['deduplicated_count']==1


def test_overlapping_timed_views_have_no_arbitrary_winner():
    values=[lap(1,start=0),lap(2,start=20)]
    normalized,valid=normalize_segments(Row(distance_m=1200,duration_seconds=300),values)
    assert normalized==[] and valid['overlapping_segments'] and not valid['structure_complete']


def test_duplicate_identity_with_conflicting_metrics_is_not_silently_resolved():
    values=[lap(1,start=0,identity='synthetic'),lap(2,start=0,identity='synthetic',distance=1000)]
    normalized,valid=normalize_segments(Row(distance_m=600,duration_seconds=150),values)
    assert normalized==[] and valid['conflicting_duplicate'] and not valid['structure_complete']


def test_distance_time_mismatch_and_truncation_never_verify_structure():
    for activity,truncated in [(Row(distance_m=5000,duration_seconds=300),False),
        (Row(distance_m=1200,duration_seconds=800),False),(Row(distance_m=1200,duration_seconds=300),True)]:
        normalized,valid=normalize_segments(activity,[lap(1),lap(2)],truncated=truncated)
        assert not valid['structure_complete']
        assert classify_segments(normalized,valid)['primary_type']=='UNKNOWN'


def test_summary_and_detail_coexist_but_only_details_are_additive():
    values=[lap(1,start=0),lap(2,start=150),lap(3,distance=1200,seconds=300,kind='RWD_RUN')]
    normalized,valid=normalize_segments(Row(distance_m=1200,duration_seconds=300),values)
    assert len(normalized)==2 and valid['structure_complete'] and valid['excluded_summary_count']==1


def test_raw_nested_split_storage_does_not_keep_credentials_or_gps():
    clean=_desensitize_payload({'garmin_splits':{'lapDTOs':[{'distance':600,'access_token':'PRIVATE','latitude':1}]}})
    assert clean=={'garmin_splits':{'lapDTOs':[{'distance':600}]}}
    assert _desensitize_payload({'nested':[[{'api_token':'PRIVATE','distance':600}]]}) == {'nested':[[{'distance':600}]]}


def test_actual_confirmed_type_overrides_a_different_plan_type():
    from server.services.runner_state_service import _effective_type
    from planner_core.enums import WorkoutMainTypeNormalized
    log=Row(workout_type='interval_speed',source_type='manual',field_sources_json={'workout_type':'manual'},actual_distance_km=12)
    assert _effective_type(log,Row(main_type_normalized=WorkoutMainTypeNormalized.easy)) == WorkoutMainTypeNormalized.interval_speed


def test_long_and_short_work_repetitions_require_each_individual_lap():
    values=[]; start=0
    for index, distance in enumerate([2000]*3 + [200]*6, 1):
        seconds=420 if distance==2000 else 40
        values.append(lap(index,distance=distance,seconds=seconds,start=start))
        start += seconds
    normalized,valid=normalize_segments(Row(distance_m=7200,duration_seconds=start),values)
    result=classify_segments(normalized,valid)
    assert valid['structure_complete'] and len(result['components'])==9
    assert sum(c['distance_m']==2000 for c in result['components'])==3
    assert sum(c['distance_m']==200 for c in result['components'])==6
    # The same total in a summary is not nine verified laps.
    summarized=lap(1,distance=7200,seconds=start,kind='INTERVAL_ACTIVE')
    summarized.classification_source='garmin_summary_rollup'
    normalized,valid=normalize_segments(Row(distance_m=7200,duration_seconds=start),[summarized])
    assert classify_segments(normalized,valid)['components']==[]
