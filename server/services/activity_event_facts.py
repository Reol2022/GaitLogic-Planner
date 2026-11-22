"""Provider event labels, not inferred race results or physiological intensity."""

EVENT_TYPES = frozenset({'race', 'training', 'recreation', 'uncategorized', 'specialEvent',
    'transportation', 'touring', 'geocaching', 'fitness'})


def event_evidence(payload):
    if not isinstance(payload, dict):
        return {}
    event = payload.get('eventTypeDTO')
    if not isinstance(event, dict) or not isinstance(event.get('typeKey'), str) or event['typeKey'] not in EVENT_TYPES:
        return {}
    return {'event_type': event['typeKey'], 'source': 'GARMIN_EVENT_TYPE',
        'source_field': 'eventTypeDTO.typeKey', 'verification': 'PROVIDER_LABEL_NOT_INDEPENDENTLY_VERIFIED'}
