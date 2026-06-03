from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    planned_distance_km: Decimal
    actual_distance_km: Decimal
    completion_rate: Decimal
    workout_count: int
    completed_count: int
    missed_count: int
    avg_rpe: Decimal | None
    max_pain_level: int | None
    main_type_distribution: dict[str, int]


class BlockStats(BaseModel):
    planned_distance_km: Decimal
    actual_distance_km: Decimal
    completion_rate: Decimal
    i_effective_km: Decimal
    t1_effective_km: Decimal
    t2_effective_km: Decimal
    m_effective_km: Decimal
    r_effective_km: Decimal
    avg_rpe: Decimal | None
    avg_weight_kg: Decimal | None
    max_pain_level: int | None

