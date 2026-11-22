"""Half-marathon-shaped SYNTHETIC response, not a runner's race fixture."""
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace as Row
from unittest.mock import Mock

import pytest
from server.integrations.activity_provider.garmin import GarminActivityProvider, _activity_from_payload, _laps_from_payload
from server.services.training_segment_facts import normalize_segments, classify_segments
from server.services.activity_event_facts import event_evidence
from server.services.lap_storage_policy import replacement_decision


def payloads(event='uncategorized'):
    # Entirely synthetic 21 x 1000m plus 250m, 6375s. Not the real race values.
    summary = {'activityId': 'synthetic-race-laps', 'activityTypeDTO': {'typeKey': 'running'},
        'activityName': 'Synthetic Half Marathon', 'startTimeLocal': '2026-07-21 08:00:00',
        'eventTypeDTO': {'typeKey': event}, 'summaryDTO': {'distance': 21250, 'duration': 6375},
        'splitSummaries': [{'splitType': kind, 'distance': 21250, 'duration': 6375}
            for kind in ('INTERVAL_ACTIVE', 'RWD_RUN')]}
    details = {'lapDTOs': [{'lapIndex': index+1, 'distance': 1000 if index < 21 else 250,
        'duration': 300 if index < 21 else 75,
        'startTimeGMT': (datetime(2026, 7, 21)+timedelta(seconds=index*300)).isoformat()}
        for index in range(22)]}
    return summary, details


def test_summary_plus_real_lap_container_prefers_individual_rows_without_typed_fallback():
    summary, details = payloads()
    provider = GarminActivityProvider()
    provider._client = Row(garth=Row(timeout=120), get_activity=Mock(return_value=summary),
        get_activity_splits=Mock(return_value=details), get_activity_typed_splits=Mock(side_effect=AssertionError('Unnecessary request')))
    result = provider.fetch_activity_summary('synthetic-race-laps')
    assert result.laps_fetched and len(result.laps) == 22
    assert len(result.raw_payload['splitSummaries']) == 2
    assert len(result.raw_payload['garmin_splits']['lapDTOs']) == 22
    normalized, validation = normalize_segments(result, result.laps)
    assert len(normalized) == 22 and validation['structure_complete']
    assert normalized[-1].distance_m == Decimal('250')  # Never pad the final lap.
    provider._client.get_activity_typed_splits.assert_not_called()


def test_list_rollups_cannot_replace_existing_kilometre_laps():
    summary, details = payloads()
    activity = Row(distance_m=21250, duration_seconds=6375, timer_time_seconds=6375)
    old = _laps_from_payload(details)
    candidate = _laps_from_payload(summary)
    accepted, reason, before, after = replacement_decision(activity, old, activity, candidate)
    assert not accepted and reason == 'COARSER_REPRESENTATION'
    assert before['detail_count'] == 22 and after['detail_count'] == 0


def test_rollups_remain_summary_only_not_missing_or_invented_twenty_two_laps():
    summary, _ = payloads()
    laps = _laps_from_payload(summary)
    normalized, validation = normalize_segments(Row(distance_m=21250, duration_seconds=6375), laps)
    assert normalized == [] and validation['detail_status'] == 'SUMMARY_ONLY'
    assert validation['distance_consistent'] is None and validation['time_consistent'] is None
    assert validation['raw_row_count'] == 2 and validation['normalized_row_count'] == 0


@pytest.mark.parametrize('event,expected', [('race','race'), ('uncategorized','UNKNOWN'), ('training','UNKNOWN')])
def test_race_requires_explicit_provider_label_not_half_distance_or_title(event, expected):
    summary, details = payloads(event)
    normalized, valid = normalize_segments(Row(distance_m=21250, duration_seconds=6375), _laps_from_payload(details))
    classified = classify_segments(normalized, valid, event_evidence=event_evidence(summary))
    assert classified['primary_type'] == expected
    assert classified['event_type'] == event
    if expected == 'race':
        assert classified['claim_type'] == 'PROVIDER_RECORDED'
        assert classified['confirmation_status'] == 'NOT_INDEPENDENTLY_VERIFIED'


def test_race_label_and_lap_completeness_are_independent():
    summary, _ = payloads('race')
    normalized, valid = normalize_segments(Row(distance_m=21250, duration_seconds=6375), _laps_from_payload(summary))
    assert classify_segments(normalized, valid, event_evidence=event_evidence(summary))['primary_type'] == 'race'
    assert valid['detail_status'] == 'SUMMARY_ONLY' and not valid['structure_complete']


def test_malformed_event_does_not_become_race():
    assert event_evidence({'eventTypeDTO': {'typeKey': ['race']}}) == {}
