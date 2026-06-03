from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner_core.database.base import Base, IdMixin, MYSQL_TABLE_ARGS, TimestampMixin
from planner_core.enums import (
    BlockType,
    ExcelImportStatus,
    WorkoutMainTypeNormalized,
    WorkoutStatusNormalized,
)


def enum_values(enum_cls: type) -> list[str]:
    return [item.value for item in enum_cls]


block_type_enum = Enum(
    BlockType,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)
workout_main_type_normalized_enum = Enum(
    WorkoutMainTypeNormalized,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
workout_status_normalized_enum = Enum(
    WorkoutStatusNormalized,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
excel_import_status_enum = Enum(
    ExcelImportStatus,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)


class TrainingCycle(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_cycles"
    __table_args__ = MYSQL_TABLE_ARGS

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    goal: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    target_race_name: Mapped[str | None] = mapped_column(String(128))
    target_race_date: Mapped[date | None] = mapped_column(Date)
    target_result: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    blocks: Mapped[list[TrainingBlock]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    planned_workouts: Mapped[list[PlannedWorkout]] = relationship(
        back_populates="cycle",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TrainingBlock(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_blocks"
    __table_args__ = (
        UniqueConstraint("cycle_id", "sort_order", name="uq_training_blocks_cycle_sort"),
        Index("ix_training_blocks_start_end", "start_date", "end_date"),
        MYSQL_TABLE_ARGS,
    )

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_name: Mapped[str] = mapped_column(String(128), nullable=False)
    block_type: Mapped[BlockType] = mapped_column(
        block_type_enum,
        nullable=False,
        default=BlockType.week,
        server_default=BlockType.week.value,
    )
    week_index: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    date_range_text: Mapped[str | None] = mapped_column(String(128))
    target_text: Mapped[str | None] = mapped_column(Text)
    target_distance_min_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    target_distance_max_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    planned_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    phase_name: Mapped[str | None] = mapped_column(String(128))
    focus: Mapped[str | None] = mapped_column(Text)

    cycle: Mapped[TrainingCycle] = relationship(back_populates="blocks")
    planned_workouts: Mapped[list[PlannedWorkout]] = relationship(
        back_populates="block",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    block_review: Mapped[BlockReview | None] = relationship(
        back_populates="block",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class PlannedWorkout(IdMixin, TimestampMixin, Base):
    __tablename__ = "planned_workouts"
    __table_args__ = (
        UniqueConstraint("cycle_id", "workout_date", name="uq_planned_workouts_cycle_date"),
        Index("ix_planned_workouts_workout_date", "workout_date"),
        Index("ix_planned_workouts_main_type_normalized", "main_type_normalized"),
        MYSQL_TABLE_ARGS,
    )

    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[int] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workout_date: Mapped[date | None] = mapped_column(Date)
    date_text: Mapped[str | None] = mapped_column(String(64))
    weekday: Mapped[str | None] = mapped_column(String(32))
    month_text: Mapped[str | None] = mapped_column(String(32))
    phase_name: Mapped[str | None] = mapped_column(String(128))
    planned_content: Mapped[str] = mapped_column(Text, nullable=False)
    focus_note: Mapped[str | None] = mapped_column(Text)
    planned_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    main_type_raw: Mapped[str | None] = mapped_column(String(64))
    main_type_normalized: Mapped[WorkoutMainTypeNormalized] = mapped_column(
        workout_main_type_normalized_enum,
        nullable=False,
        default=WorkoutMainTypeNormalized.unknown,
        server_default=WorkoutMainTypeNormalized.unknown.value,
    )
    source_sheet: Mapped[str | None] = mapped_column(String(128))
    source_row: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    cycle: Mapped[TrainingCycle] = relationship(back_populates="planned_workouts")
    block: Mapped[TrainingBlock] = relationship(back_populates="planned_workouts")
    workout_log: Mapped[WorkoutLog | None] = relationship(
        back_populates="planned_workout",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class WorkoutLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_logs"
    __table_args__ = (
        UniqueConstraint("planned_workout_id", name="uq_workout_logs_planned_workout"),
        Index("ix_workout_logs_status_normalized", "status_normalized"),
        CheckConstraint(
            "pain_level IS NULL OR (pain_level >= 0 AND pain_level <= 5)",
            name="ck_workout_logs_pain_level_range",
        ),
        MYSQL_TABLE_ARGS,
    )

    planned_workout_id: Mapped[int] = mapped_column(
        ForeignKey("planned_workouts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status_raw: Mapped[str | None] = mapped_column(String(64))
    status_normalized: Mapped[WorkoutStatusNormalized] = mapped_column(
        workout_status_normalized_enum,
        nullable=False,
        default=WorkoutStatusNormalized.not_started,
        server_default=WorkoutStatusNormalized.not_started.value,
    )
    actual_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    actual_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    avg_pace_seconds_per_km: Mapped[int | None] = mapped_column(Integer)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)
    rpe: Mapped[int | None] = mapped_column(Integer)
    i_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    t1_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    t2_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    m_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    r_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    sleep_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    hrv: Mapped[int | None] = mapped_column(Integer)
    morning_heart_rate: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    leg_feeling: Mapped[str | None] = mapped_column(String(128))
    pain_location: Mapped[str | None] = mapped_column(String(128))
    pain_level: Mapped[int | None] = mapped_column(Integer)
    main_session_data: Mapped[str | None] = mapped_column(Text)
    review_note: Mapped[str | None] = mapped_column(Text)
    tomorrow_adjustment: Mapped[str | None] = mapped_column(Text)
    alert_message: Mapped[str | None] = mapped_column(Text)
    completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    planned_workout: Mapped[PlannedWorkout] = relationship(back_populates="workout_log")


class BlockReview(IdMixin, TimestampMixin, Base):
    __tablename__ = "block_reviews"
    __table_args__ = (
        UniqueConstraint("block_id", name="uq_block_reviews_block"),
        CheckConstraint(
            "max_pain_level IS NULL OR (max_pain_level >= 0 AND max_pain_level <= 5)",
            name="ck_block_reviews_max_pain_level_range",
        ),
        MYSQL_TABLE_ARGS,
    )

    block_id: Mapped[int] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    planned_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    actual_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    completion_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    i_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    t1_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    t2_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    m_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    r_effective_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    avg_rpe: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    avg_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    max_pain_level: Mapped[int | None] = mapped_column(Integer)
    review_text: Mapped[str | None] = mapped_column(Text)
    next_block_adjustment: Mapped[str | None] = mapped_column(Text)

    block: Mapped[TrainingBlock] = relationship(back_populates="block_review")


class PaceRule(IdMixin, TimestampMixin, Base):
    __tablename__ = "pace_rules"
    __table_args__ = (
        UniqueConstraint("code", name="uq_pace_rules_code"),
        MYSQL_TABLE_ARGS,
    )

    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_pace_text: Mapped[str | None] = mapped_column(String(255))
    physiological_purpose: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class ExcelImportJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "excel_import_jobs"
    __table_args__ = (
        Index("ix_excel_import_jobs_file_hash", "file_hash"),
        MYSQL_TABLE_ARGS,
    )

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512))
    file_hash: Mapped[str | None] = mapped_column(String(128))
    sheet_names: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[ExcelImportStatus] = mapped_column(
        excel_import_status_enum,
        nullable=False,
        default=ExcelImportStatus.pending,
        server_default=ExcelImportStatus.pending.value,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

