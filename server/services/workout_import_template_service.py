from __future__ import annotations

import io

from openpyxl import Workbook


HEADERS = [
    "activity_date",
    "start_time",
    "session_index",
    "sport_type",
    "workout_type",
    "title",
    "distance_km",
    "duration_seconds",
    "moving_time_seconds",
    "elapsed_time_seconds",
    "average_pace_seconds_per_km",
    "average_heart_rate_bpm",
    "max_heart_rate_bpm",
    "average_cadence_spm",
    "max_cadence_spm",
    "elevation_gain_m",
    "calories_kcal",
    "rpe",
    "pain_level",
    "completion_status",
    "content",
    "notes",
]


def generate_workout_import_template_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "workout_import"
    sheet.append(HEADERS)
    sheet.append(
        [
            "2026-07-01",
            "07:15:00",
            1,
            "running",
            "E",
            "有氧跑",
            12.3,
            3012,
            2960,
            3150,
            245,
            142,
            158,
            180,
            190,
            42,
            760,
            4,
            0,
            "completed",
            "12km有氧跑",
            "整体轻松",
        ]
    )
    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 32)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
