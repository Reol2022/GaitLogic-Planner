from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import exp, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from planner_core.database.models import PaceProfile, PaceRule, PaceZone
from planner_core.enums import PaceZoneCode, RaceDistance
from server.common.exceptions import BadRequestError, NotFoundError

ALGORITHM_VERSION = "approx_vdot_v1"

DISTANCE_METERS: dict[RaceDistance, int] = {
    RaceDistance.m1500: 1500,
    RaceDistance.m3000: 3000,
    RaceDistance.m5000: 5000,
    RaceDistance.m10000: 10000,
    RaceDistance.half_marathon: 21097,
    RaceDistance.marathon: 42195,
}


@dataclass(frozen=True)
class PaceZoneResult:
    zone_code: PaceZoneCode
    zone_name: str
    pace_min_seconds_per_km: int
    pace_max_seconds_per_km: int
    target_pace_text: str
    description: str
    sort_order: int


ZONE_DEFINITIONS: tuple[tuple[PaceZoneCode, str, float, float, str], ...] = (
    (PaceZoneCode.REC, "恢复跑", 0.58, 0.63, "恢复跑，用于低强度恢复和双跑第二跑"),
    (PaceZoneCode.E, "轻松跑", 0.63, 0.72, "轻松跑，用于有氧基础建设"),
    (PaceZoneCode.M, "稳态 / 马拉松强度", 0.76, 0.82, "稳态跑，接近马拉松强度"),
    (PaceZoneCode.T1, "稳阈值", 0.83, 0.86, "稳阈值，比标准阈值稍慢"),
    (PaceZoneCode.T2, "高阈值", 0.86, 0.89, "高阈值，接近标准阈值强度"),
    (PaceZoneCode.I, "间歇", 0.95, 1.00, "VO2max 间歇训练"),
    (PaceZoneCode.R, "短速度", 1.03, 1.08, "神经速度和跑姿经济性训练"),
)


def parse_race_result_seconds(value: str | int | float) -> int:
    if isinstance(value, int):
        seconds = value
    elif isinstance(value, float):
        seconds = int(value)
    else:
        text = str(value).strip()
        if not text:
            raise BadRequestError("Race result is required.")
        if text.isdigit():
            seconds = int(text)
        else:
            parts = text.split(":")
            if len(parts) == 2:
                minutes, seconds_part = _parse_time_parts(parts)
                seconds = minutes * 60 + seconds_part
            elif len(parts) == 3:
                hours, minutes, seconds_part = _parse_time_parts(parts)
                seconds = hours * 3600 + minutes * 60 + seconds_part
            else:
                raise BadRequestError("Race result format is invalid.")

    if seconds <= 0:
        raise BadRequestError("Race result must be greater than 0 seconds.")
    return seconds


def _parse_time_parts(parts: list[str]) -> list[int]:
    try:
        values = [int(part.strip()) for part in parts]
    except ValueError as exc:
        raise BadRequestError("Race result format is invalid.") from exc
    if any(value < 0 for value in values):
        raise BadRequestError("Race result format is invalid.")
    if len(values) >= 2 and values[-1] >= 60:
        raise BadRequestError("Seconds must be less than 60.")
    if len(values) == 3 and values[1] >= 60:
        raise BadRequestError("Minutes must be less than 60.")
    return values


def calculate_vdot(distance_meters: int, race_result_seconds: int) -> float:
    if distance_meters <= 0:
        raise BadRequestError("Race distance is invalid.")
    if race_result_seconds <= 0:
        raise BadRequestError("Race result must be greater than 0 seconds.")

    time_minutes = race_result_seconds / 60
    velocity = distance_meters / time_minutes
    vo2 = -4.60 + 0.182258 * velocity + 0.000104 * velocity * velocity
    percent_vo2max = (
        0.8
        + 0.1894393 * exp(-0.012778 * time_minutes)
        + 0.2989558 * exp(-0.1932605 * time_minutes)
    )
    return round(vo2 / percent_vo2max, 1)


def velocity_for_vo2(vo2: float) -> float:
    a = 0.182258
    b = 0.000104
    c = -(vo2 + 4.60)
    return (-a + sqrt(a * a - 4 * b * c)) / (2 * b)


def format_pace(seconds_per_km: int | float) -> str:
    seconds = int(round(seconds_per_km))
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}:{rest:02d}/km"


def generate_pace_zones(vdot: float) -> list[PaceZoneResult]:
    if vdot <= 0:
        raise BadRequestError("VDOT must be greater than 0.")

    vvo2max = velocity_for_vo2(vdot)
    zones: list[PaceZoneResult] = []
    for index, (code, name, low_ratio, high_ratio, description) in enumerate(ZONE_DEFINITIONS, start=1):
        fast_seconds = round((1000 / (vvo2max * high_ratio)) * 60)
        slow_seconds = round((1000 / (vvo2max * low_ratio)) * 60)
        zones.append(
            PaceZoneResult(
                zone_code=code,
                zone_name=name,
                pace_min_seconds_per_km=fast_seconds,
                pace_max_seconds_per_km=slow_seconds,
                target_pace_text=f"{format_pace(fast_seconds).removesuffix('/km')}-{format_pace(slow_seconds)}",
                description=description,
                sort_order=index,
            )
        )
    return zones


def calculate_from_race(distance: RaceDistance | str, result: str | int | float) -> dict:
    race_distance = RaceDistance(distance)
    result_seconds = parse_race_result_seconds(result)
    vdot = calculate_vdot(DISTANCE_METERS[race_distance], result_seconds)
    zones = generate_pace_zones(vdot)
    return {
        "race_distance": race_distance,
        "race_result_seconds": result_seconds,
        "vdot": vdot,
        "zones": zones,
    }


def create_pace_profile(
    db: Session,
    *,
    user_id: int,
    name: str,
    race_distance: RaceDistance,
    race_result: str,
) -> PaceProfile:
    result = calculate_from_race(race_distance, race_result)
    profile = PaceProfile(
        user_id=user_id,
        name=name,
        race_distance=result["race_distance"],
        race_result_seconds=result["race_result_seconds"],
        vdot=Decimal(str(result["vdot"])),
        algorithm_version=ALGORITHM_VERSION,
        zones=[
            PaceZone(
                zone_code=zone.zone_code,
                zone_name=zone.zone_name,
                pace_min_seconds_per_km=zone.pace_min_seconds_per_km,
                pace_max_seconds_per_km=zone.pace_max_seconds_per_km,
                target_pace_text=zone.target_pace_text,
                description=zone.description,
                sort_order=zone.sort_order,
            )
            for zone in result["zones"]
        ],
    )
    db.add(profile)
    db.commit()
    return get_pace_profile(db, profile.id, user_id)


def list_pace_profiles(db: Session, user_id: int) -> list[PaceProfile]:
    return list(
        db.scalars(
            select(PaceProfile)
            .where(PaceProfile.user_id == user_id)
            .order_by(PaceProfile.created_at.desc(), PaceProfile.id.desc())
        )
    )


def get_pace_profile(db: Session, profile_id: int, user_id: int) -> PaceProfile:
    profile = db.scalar(
        select(PaceProfile)
        .options(selectinload(PaceProfile.zones))
        .where(PaceProfile.id == profile_id, PaceProfile.user_id == user_id)
    )
    if profile is None:
        raise NotFoundError("Pace profile not found.")
    profile.zones.sort(key=lambda zone: zone.sort_order)
    return profile


def delete_pace_profile(db: Session, profile_id: int, user_id: int) -> None:
    profile = get_pace_profile(db, profile_id, user_id)
    db.delete(profile)
    db.commit()


def apply_profile_to_pace_rules(db: Session, profile_id: int, user_id: int) -> int:
    profile = get_pace_profile(db, profile_id, user_id)
    updated_count = 0
    for zone in profile.zones:
        rule = db.scalar(select(PaceRule).where(PaceRule.user_id == user_id, PaceRule.code == zone.zone_code.value))
        if rule is None:
            rule = PaceRule(
                user_id=user_id,
                code=zone.zone_code.value,
                name=zone.zone_name,
                sort_order=zone.sort_order,
            )
            db.add(rule)
        rule.target_pace_text = zone.target_pace_text
        rule.physiological_purpose = zone.description
        rule.note = f"来自配速档案：{profile.name}，VDOT {float(profile.vdot):.1f}"
        updated_count += 1
    db.commit()
    return updated_count
