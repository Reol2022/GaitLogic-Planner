from planner_core.enums import PaceZoneCode, RaceDistance
from pydantic import ValidationError
import pytest
from server.schemas.pace_calculator import PaceCalculationRequest
from server.services.pace_calculator_service import (
    build_age_reference,
    calculate_age_reference,
    calculate_from_race,
    calculate_vdot,
    format_pace,
    generate_pace_zones,
    parse_race_result_seconds,
)


def test_parse_race_result_seconds() -> None:
    assert parse_race_result_seconds("16:24") == 984
    assert parse_race_result_seconds("1:12:32") == 4352
    assert parse_race_result_seconds("4352") == 4352
    assert parse_race_result_seconds(4352) == 4352


def test_calculate_vdot_half_marathon() -> None:
    vdot = calculate_vdot(21097, 4352)
    assert 64 <= vdot <= 67


def test_calculate_vdot_5000m_reasonable() -> None:
    vdot = calculate_vdot(5000, parse_race_result_seconds("16:24"))
    assert 58 <= vdot <= 64


def test_format_pace() -> None:
    assert format_pace(290) == "4:50/km"


def test_generate_pace_zones() -> None:
    zones = generate_pace_zones(65.3)
    assert len(zones) == 7
    assert [zone.zone_code for zone in zones] == [
        PaceZoneCode.REC,
        PaceZoneCode.E,
        PaceZoneCode.M,
        PaceZoneCode.T1,
        PaceZoneCode.T2,
        PaceZoneCode.I,
        PaceZoneCode.R,
    ]
    assert all(zone.target_pace_text for zone in zones)
    assert all(zone.pace_min_seconds_per_km < zone.pace_max_seconds_per_km for zone in zones)


def test_race_distance_enum_values() -> None:
    assert RaceDistance.half_marathon.value == "half_marathon"
    assert RaceDistance.m5000.value == "5000m"


def test_age_reference_does_not_change_original_vdot() -> None:
    baseline = calculate_from_race(RaceDistance.half_marathon, "1:12:32")
    with_age = calculate_from_race(RaceDistance.half_marathon, "1:12:32")
    assert with_age["vdot"] == baseline["vdot"]
    assert with_age["zones"][0].target_pace_text == baseline["zones"][0].target_pace_text

    age_reference = calculate_age_reference(
        42,
        "male",
        RaceDistance.half_marathon,
        with_age["race_result_seconds"],
    )
    assert age_reference is not None
    assert age_reference.age_grade_percent > 0
    assert age_reference.age_graded_seconds > 0
    assert age_reference.source == "gaitlogic_age_grade_v1"

    text = build_age_reference(42, "male", RaceDistance.half_marathon, with_age["race_result_seconds"])
    assert text is not None
    assert "训练配速仍按实际比赛成绩推算" in text


def test_age_reference_is_optional() -> None:
    assert build_age_reference(None, "unknown") is None
    assert calculate_age_reference(None, "unknown", RaceDistance.m5000, 984) is None


def test_age_reference_requires_supported_age_and_known_sex() -> None:
    assert calculate_age_reference(16, "male", RaceDistance.m5000, 984) is None
    assert calculate_age_reference(42, "unknown", RaceDistance.m5000, 984) is None
    assert "覆盖 18-100 岁" in (build_age_reference(16, "female", RaceDistance.m5000, 984) or "")


def test_invalid_sex_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PaceCalculationRequest(race_distance=RaceDistance.m5000, race_result="16:24", sex="other")
