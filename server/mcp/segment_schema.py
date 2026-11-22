"""Discoverable JSON contracts retaining plain dicts for existing consumers."""
from typing import Literal
from typing_extensions import TypedDict


class SegmentValidation(TypedDict, total=False):
    detail_status: Literal['UNAVAILABLE', 'SUMMARY_ONLY', 'PARTIAL', 'COMPLETE', 'CONFLICTED']
    raw_row_count: int
    normalized_row_count: int
    distance_consistent: bool | None
    time_consistent: bool | None
    overlapping_segments: bool
    structure_complete: bool
    confidence: Literal['VALIDATED_STRUCTURE', 'INCOMPLETE']
    excluded_summary_count: int
    deduplicated_count: int
    raw_laps_truncated: bool
    conflicting_duplicate: bool
    context_truncated: bool


class SegmentComponent(TypedDict):
    type: str
    lap_index: int
    distance_m: float
    duration_seconds: int | None


class ActivityClassification(TypedDict, total=False):
    primary_type: str
    components: list[SegmentComponent]
    confidence: str
    evidence_source: str
    requires_confirmation: bool
    scope: Literal['SELECTED_ACTIVITY']
    claim_type: Literal['DETERMINISTIC_DERIVATION', 'UNKNOWN', 'PROVIDER_RECORDED']
    confirmation_status: Literal['NOT_USER_CONFIRMED', 'UNCONFIRMED', 'NOT_INDEPENDENTLY_VERIFIED']
    event_type: str
    event_type_source: str


class SegmentStorage(TypedDict, total=False):
    version: int
    decision: str
    reason: str
    current_detail_count: int
    candidate_detail_count: int
    checked_at: str
    requires_review: bool
