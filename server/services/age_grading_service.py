from __future__ import annotations

from dataclasses import dataclass

from planner_core.enums import RaceDistance

AGE_GRADING_SOURCE = "gaitlogic_age_grade_v1"

# Open standards are used only as a comparison baseline for age reference.
# They do not affect VDOT or training pace zones.
OPEN_STANDARDS_SECONDS: dict[str, dict[RaceDistance, float]] = {
    "male": {
        RaceDistance.m1500: 206.0,
        RaceDistance.m3000: 437.5,
        RaceDistance.m5000: 755.4,
        RaceDistance.m10000: 1571.0,
        RaceDistance.half_marathon: 3447.0,
        RaceDistance.marathon: 7295.0,
    },
    "female": {
        RaceDistance.m1500: 229.0,
        RaceDistance.m3000: 486.1,
        RaceDistance.m5000: 840.2,
        RaceDistance.m10000: 1734.1,
        RaceDistance.half_marathon: 3772.0,
        RaceDistance.marathon: 7913.0,
    },
}

# The table intentionally stores factors, not corrected VDOT. A result can be
# compared against the age standard, while the actual training ability remains
# the race-result-based VDOT calculated by pace_calculator_service.
AGE_FACTOR_ANCHORS: dict[str, tuple[tuple[int, float], ...]] = {
    "male": (
        (18, 1.000),
        (35, 1.000),
        (40, 0.970),
        (45, 0.940),
        (50, 0.900),
        (55, 0.855),
        (60, 0.800),
        (65, 0.735),
        (70, 0.665),
        (75, 0.585),
        (80, 0.500),
        (85, 0.420),
        (90, 0.340),
        (95, 0.270),
        (100, 0.210),
    ),
    "female": (
        (18, 1.000),
        (35, 1.000),
        (40, 0.975),
        (45, 0.945),
        (50, 0.905),
        (55, 0.855),
        (60, 0.795),
        (65, 0.725),
        (70, 0.645),
        (75, 0.560),
        (80, 0.470),
        (85, 0.380),
        (90, 0.300),
        (95, 0.230),
        (100, 0.170),
    ),
}

SEX_LABELS = {
    "male": "男性",
    "female": "女性",
    "unknown": "未指定性别",
}


@dataclass(frozen=True)
class AgeGradingReference:
    age: int
    sex: str
    source: str
    age_factor: float
    age_standard_seconds: int
    age_graded_seconds: int
    age_grade_percent: float
    level_label: str
    note: str


def calculate_age_grading_reference(
    *,
    age: int | None,
    sex: str,
    race_distance: RaceDistance,
    race_result_seconds: int,
) -> AgeGradingReference | None:
    if age is None or sex not in ("male", "female"):
        return None
    if age < 18 or age > 100:
        return None
    if race_result_seconds <= 0:
        return None

    distance = RaceDistance(race_distance)
    open_standard = OPEN_STANDARDS_SECONDS[sex][distance]
    age_factor = AGE_FACTORS_BY_SEX[sex][age]
    age_standard_seconds = round(open_standard / age_factor)
    age_graded_seconds = round(race_result_seconds * age_factor)
    age_grade_percent = round((age_standard_seconds / race_result_seconds) * 100, 1)

    return AgeGradingReference(
        age=age,
        sex=sex,
        source=AGE_GRADING_SOURCE,
        age_factor=round(age_factor, 3),
        age_standard_seconds=age_standard_seconds,
        age_graded_seconds=age_graded_seconds,
        age_grade_percent=age_grade_percent,
        level_label=_performance_level(age_grade_percent),
        note="年龄参考分析仅用于横向表现水平参考，不会改变原始 VDOT 或训练配速区间。",
    )


def build_age_reference_text(
    *,
    age: int | None,
    sex: str,
    race_distance: RaceDistance | None = None,
    race_result_seconds: int | None = None,
) -> str | None:
    if age is None and sex == "unknown":
        return None
    if age is None:
        return "已记录性别；如需年龄参考分析，请同时填写年龄。训练配速仍按实际比赛成绩推算。"
    if sex == "unknown":
        return "已记录年龄；如需年龄参考分析，请选择男性或女性。训练配速仍按实际比赛成绩推算。"
    if age < 18 or age > 100:
        return "当前年龄参考表覆盖 18-100 岁；本次不会输出年龄等级。训练配速仍按实际比赛成绩推算。"
    if race_distance is None or race_result_seconds is None:
        sex_text = SEX_LABELS.get(sex, "未指定性别")
        return f"已记录 {age} 岁、{sex_text}；年龄参考分析将在计算比赛成绩后展示。"

    reference = calculate_age_grading_reference(
        age=age,
        sex=sex,
        race_distance=race_distance,
        race_result_seconds=race_result_seconds,
    )
    if reference is None:
        return None
    return (
        f"年龄等级 {reference.age_grade_percent:.1f}%（{reference.level_label}），"
        f"公开组等效成绩 {format_duration(reference.age_graded_seconds)}。"
        "训练配速仍按实际比赛成绩推算。"
    )


def format_duration(seconds: int) -> str:
    hour, rest = divmod(seconds, 3600)
    minute, second = divmod(rest, 60)
    if hour:
        return f"{hour}:{minute:02d}:{second:02d}"
    return f"{minute}:{second:02d}"


def _interpolate_age_factor(age: int, anchors: tuple[tuple[int, float], ...]) -> float:
    if age <= anchors[0][0]:
        return anchors[0][1]
    if age >= anchors[-1][0]:
        return anchors[-1][1]

    for index in range(1, len(anchors)):
        left_age, left_factor = anchors[index - 1]
        right_age, right_factor = anchors[index]
        if age <= right_age:
            ratio = (age - left_age) / (right_age - left_age)
            return left_factor + (right_factor - left_factor) * ratio

    return anchors[-1][1]


AGE_FACTORS_BY_SEX: dict[str, dict[int, float]] = {
    sex: {age: round(_interpolate_age_factor(age, anchors), 3) for age in range(18, 101)}
    for sex, anchors in AGE_FACTOR_ANCHORS.items()
}


def _performance_level(age_grade_percent: float) -> str:
    if age_grade_percent >= 90:
        return "世界级参考"
    if age_grade_percent >= 80:
        return "全国级参考"
    if age_grade_percent >= 70:
        return "区域优秀"
    if age_grade_percent >= 60:
        return "认真训练"
    return "日常参考"
