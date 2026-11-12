"""Versioned Garmin self-evaluation facts, never inferred from training intensity."""
from datetime import datetime, timezone
import math


def normalize_rpe(payload: dict, *, fetched_at: datetime | None = None) -> dict:
    """Garmin directWorkoutRpe uses tenths of the displayed 1–10 scale.

    Only this known field is supported. Unknown aliases/scales are not guessed.
    References: python-garminconnect discussion #198 and garminconnect-js source.
    """
    summary = payload.get("summaryDTO")
    source = summary if isinstance(summary, dict) else payload
    path = "summaryDTO.directWorkoutRpe" if isinstance(summary, dict) else "directWorkoutRpe"
    raw = source.get("directWorkoutRpe")
    number = float(raw) if type(raw) in (int, float) else None
    valid = number is not None and math.isfinite(number) and 10 <= number <= 100 and number % 10 == 0
    return {
        "schema_version": 1, "source": "garmin", "raw_field": path,
        "fact_kind": "USER_REPORTED_VIA_GARMIN",
        "raw_value": raw if number is not None and math.isfinite(number) else None,
        "raw_scale": "10_100", "normalized_scale": "1_10",
        "value": int(number / 10) if valid else None,
        "missing_reason": None if valid else "NOT_PROVIDED" if raw is None else "INVALID_VALUE",
        "fetched_at": (fetched_at or datetime.now(timezone.utc)).isoformat(),
    }


def activity_rpe(activity) -> dict:
    evidence = (getattr(activity, "field_sources_json", None) or {}).get("rpe_evidence")
    return safe_evidence(evidence)


def safe_evidence(evidence) -> dict:
    if not isinstance(evidence, dict):
        return {"value": None, "missing_reason": "DETAILS_NOT_FETCHED"}
    value = evidence.get("value")
    result = {"value": value if type(value) is int and 1 <= value <= 10 else None,
        "missing_reason": None if type(value) is int and 1 <= value <= 10 else "DETAILS_NOT_FETCHED"}
    enums = {"source": {"garmin"}, "raw_field": {"summaryDTO.directWorkoutRpe", "directWorkoutRpe"},
        "fact_kind": {"USER_REPORTED_VIA_GARMIN"},
        "raw_scale": {"10_100"}, "normalized_scale": {"1_10"},
        "missing_reason": {None,"NOT_PROVIDED","INVALID_VALUE","DETAIL_FETCH_FAILED","DETAILS_NOT_FETCHED",
            "MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING"}}
    for key, allowed in enums.items():
        if key in evidence and (evidence.get(key) is None or isinstance(evidence.get(key), str)) and evidence.get(key) in allowed:
            result[key] = evidence.get(key)
    if evidence.get("schema_version") == 1:
        result["schema_version"] = 1
    raw = evidence.get("raw_value")
    if type(raw) in (int,float) and math.isfinite(raw):
        result["raw_value"] = raw
    try:
        result["fetched_at"] = datetime.fromisoformat(evidence["fetched_at"]).isoformat()
    except (KeyError,TypeError,ValueError):
        pass
    return result


def apply_log_rpe(log, activities) -> None:
    """Manual wins. Multi-activity RPE is not an average or a sum."""
    sources = dict(log.field_sources_json or {})
    evidence = activity_rpe(activities[0]) if len(activities) == 1 else {
        "value": None, "missing_reason": "MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING"
    }
    latest = (activities[0].field_sources_json or {}).get("rpe_last_attempt") if len(activities)==1 else None
    sources["garmin_rpe_evidence"] = safe_evidence(latest) if latest else evidence
    manual = sources.get("rpe") in {"manual", "manual_edit", "excel_import"} or (log.rpe is not None and sources.get("rpe") not in {"garmin", "garmin_sync"})
    if not manual:
        value = evidence.get("value")
        if len(activities) > 1:
            # A previously single activity may later become one component of
            # a session. Its effort must not remain the whole-session rating.
            log.rpe = None
            sources['rpe_evidence'] = evidence
        elif type(value) is int and 1 <= value <= 10:
            log.rpe = value
            sources["rpe"] = "garmin"
            sources["rpe_evidence"] = evidence
        # Missing or failed fetch never erases an earlier effective value.
    log.field_sources_json = sources


def effective_log_rpe(log, *, linked_activity_count=None):
    sources = getattr(log, 'field_sources_json', None) or {}
    if sources.get('rpe') in {'garmin', 'garmin_sync'}:
        count = linked_activity_count if linked_activity_count is not None else getattr(log, '_rpe_linked_activity_count', None)
        multi = (sources.get('garmin_rpe_evidence') or {}).get('missing_reason') == 'MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING'
        if (count is not None and count > 1) or multi:
            return None
    return log.rpe


def log_rpe_metadata(log, *, linked_activity_count=None) -> dict:
    sources = log.field_sources_json or {}
    evidence = safe_evidence(sources.get("rpe_evidence"))
    garmin = sources.get("rpe") in {"garmin", "garmin_sync"}
    effective = effective_log_rpe(log, linked_activity_count=linked_activity_count)
    value = effective if type(effective) is int and 1 <= effective <= 10 else None
    latest = safe_evidence(sources.get("garmin_rpe_evidence"))
    source = "GARMIN" if garmin else "IMPORT" if "import" in str(sources.get("rpe", "")) else "MANUAL" if sources.get('rpe') in {'manual','manual_edit'} else "UNKNOWN"
    ambiguous = garmin and log.rpe is not None and effective is None
    return {"source": source,
        "scope": "ACTIVITY" if garmin else "SESSION" if value is not None and source in {'MANUAL','IMPORT'} else "UNKNOWN",
        "fetched_at": evidence.get("fetched_at") if garmin else None,
        "missing_reason": 'MULTIPLE_ACTIVITIES_REQUIRE_SESSION_RATING' if ambiguous else None if value is not None else latest.get("missing_reason", "NOT_RECORDED"),
        "latest_sync_missing_reason": latest.get("missing_reason")}
