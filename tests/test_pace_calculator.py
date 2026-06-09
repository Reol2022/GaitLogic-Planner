from planner_core.enums import PaceZoneCode, RaceDistance
from server.services.pace_calculator_service import (
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
