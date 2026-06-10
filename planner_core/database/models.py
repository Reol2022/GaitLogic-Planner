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
    AIPlanDraftStatus,
    AIPlanJobStatus,
    BlockType,
    ExcelImportStatus,
    FeedbackType,
    PaceZoneCode,
    RaceDistance,
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
race_distance_enum = Enum(
    RaceDistance,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
pace_zone_code_enum = Enum(
    PaceZoneCode,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)
feedback_type_enum = Enum(
    FeedbackType,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
ai_plan_job_status_enum = Enum(
    AIPlanJobStatus,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)
ai_plan_draft_status_enum = Enum(
    AIPlanDraftStatus,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)


class UserAccount(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_account_username"),
        UniqueConstraint("email", name="uq_user_account_email"),
        MYSQL_TABLE_ARGS,
    )

    username: Mapped[str] = mapped_column(String(64), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    training_cycles: Mapped[list[TrainingCycle]] = relationship(back_populates="user")
    training_blocks: Mapped[list[TrainingBlock]] = relationship(back_populates="user")
    planned_workouts: Mapped[list[PlannedWorkout]] = relationship(back_populates="user")
    workout_logs: Mapped[list[WorkoutLog]] = relationship(back_populates="user")
    block_reviews: Mapped[list[BlockReview]] = relationship(back_populates="user")
    pace_rules: Mapped[list[PaceRule]] = relationship(back_populates="user")
    pace_profiles: Mapped[list[PaceProfile]] = relationship(back_populates="user")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="user")
    ai_plan_jobs: Mapped[list[AIPlanJob]] = relationship(back_populates="user")
    ai_plan_quotas: Mapped[list[AIPlanQuota]] = relationship(back_populates="user")
    admin_ai_settings_updates: Mapped[list[AdminAISettings]] = relationship(
        back_populates="updated_by",
        foreign_keys="AdminAISettings.updated_by_id",
    )
    ai_plan_drafts: Mapped[list[AIPlanDraft]] = relationship(back_populates="user")
    ai_coach_preference: Mapped[AIPlanCoachPreference | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    excel_import_jobs: Mapped[list[ExcelImportJob]] = relationship(back_populates="user")


class TrainingCycle(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_cycles"
    __table_args__ = MYSQL_TABLE_ARGS

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    goal: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    target_race_name: Mapped[str | None] = mapped_column(String(128))
    target_race_date: Mapped[date | None] = mapped_column(Date)
    target_result: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[UserAccount] = relationship(back_populates="training_cycles")
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
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

    user: Mapped[UserAccount] = relationship(back_populates="training_blocks")
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
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

    user: Mapped[UserAccount] = relationship(back_populates="planned_workouts")
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
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

    user: Mapped[UserAccount] = relationship(back_populates="workout_logs")
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
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

    user: Mapped[UserAccount] = relationship(back_populates="block_reviews")
    block: Mapped[TrainingBlock] = relationship(back_populates="block_review")


class PaceRule(IdMixin, TimestampMixin, Base):
    __tablename__ = "pace_rules"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_pace_rules_user_code"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    target_pace_text: Mapped[str | None] = mapped_column(String(255))
    physiological_purpose: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    user: Mapped[UserAccount] = relationship(back_populates="pace_rules")


class PaceProfile(IdMixin, TimestampMixin, Base):
    __tablename__ = "pace_profile"
    __table_args__ = (
        Index("ix_pace_profile_user_created", "user_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    race_distance: Mapped[RaceDistance] = mapped_column(race_distance_enum, nullable=False)
    race_result_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    vdot: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="approx_vdot_v1",
        server_default="approx_vdot_v1",
    )

    user: Mapped[UserAccount] = relationship(back_populates="pace_profiles")
    zones: Mapped[list[PaceZone]] = relationship(
        back_populates="pace_profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class PaceZone(IdMixin, TimestampMixin, Base):
    __tablename__ = "pace_zone"
    __table_args__ = (
        UniqueConstraint("pace_profile_id", "zone_code", name="uq_pace_zone_profile_code"),
        MYSQL_TABLE_ARGS,
    )

    pace_profile_id: Mapped[int] = mapped_column(
        ForeignKey("pace_profile.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_code: Mapped[PaceZoneCode] = mapped_column(pace_zone_code_enum, nullable=False)
    zone_name: Mapped[str] = mapped_column(String(64), nullable=False)
    pace_min_seconds_per_km: Mapped[int] = mapped_column(Integer, nullable=False)
    pace_max_seconds_per_km: Mapped[int] = mapped_column(Integer, nullable=False)
    target_pace_text: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    pace_profile: Mapped[PaceProfile] = relationship(back_populates="zones")


class Feedback(IdMixin, TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        Index("ix_feedback_user_created", "user_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(feedback_type_enum, nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
        server_default="open",
    )

    user: Mapped[UserAccount] = relationship(back_populates="feedback_items")


class AIPlanJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_plan_job"
    __table_args__ = (
        Index("ix_ai_plan_job_user_prompt", "user_id", "prompt_hash"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AIPlanJobStatus] = mapped_column(
        ai_plan_job_status_enum,
        nullable=False,
        default=AIPlanJobStatus.pending,
        server_default=AIPlanJobStatus.pending.value,
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="ai_plan_jobs")
    draft: Mapped[AIPlanDraft | None] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class AIPlanQuota(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_plan_quota"
    __table_args__ = (
        UniqueConstraint("user_id", "quota_date", name="uq_ai_plan_quota_user_date"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="ai_plan_quotas")


class AdminAISettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "admin_ai_settings"
    __table_args__ = MYSQL_TABLE_ARGS

    deepseek_base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://api.deepseek.com",
        server_default="https://api.deepseek.com",
    )
    deepseek_model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="deepseek-v4-flash",
        server_default="deepseek-v4-flash",
    )
    deepseek_api_key: Mapped[str | None] = mapped_column(String(512))
    deepseek_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120, server_default="120")
    ai_plan_daily_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    ai_plan_cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.40"), server_default="0.40")
    top_p: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.90"), server_default="0.90")
    max_tokens_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=1600, server_default="1600")
    max_tokens_cap: Mapped[int] = mapped_column(Integer, nullable=False, default=24000, server_default="24000")
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL"),
        index=True,
    )

    updated_by: Mapped[UserAccount | None] = relationship(
        back_populates="admin_ai_settings_updates",
        foreign_keys=[updated_by_id],
    )


class AIPlanCoachPreference(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_coach_preference"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_ai_coach_preference_user"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preferred_training_systems: Mapped[list | None] = mapped_column(JSON)
    intensity_conservatism: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="standard",
        server_default="standard",
    )
    key_workout_habit: Mapped[str | None] = mapped_column(Text)
    rest_day_strategy: Mapped[str | None] = mapped_column(Text)
    disabled_workout_types: Mapped[list | None] = mapped_column(JSON)
    double_run_policy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="cautious",
        server_default="cautious",
    )
    long_run_strategy: Mapped[str | None] = mapped_column(Text)
    injury_risk_policy: Mapped[str | None] = mapped_column(Text)
    additional_notes: Mapped[str | None] = mapped_column(Text)

    user: Mapped[UserAccount] = relationship(back_populates="ai_coach_preference")


class AIPlanDraft(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_plan_draft"
    __table_args__ = (
        Index("ix_ai_plan_draft_user_status", "user_id", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("ai_plan_job.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    goal: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    target_race_name: Mapped[str | None] = mapped_column(String(128))
    target_race_date: Mapped[date | None] = mapped_column(Date)
    target_result: Mapped[str | None] = mapped_column(String(64))
    summary: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[AIPlanDraftStatus] = mapped_column(
        ai_plan_draft_status_enum,
        nullable=False,
        default=AIPlanDraftStatus.draft,
        server_default=AIPlanDraftStatus.draft.value,
    )

    user: Mapped[UserAccount] = relationship(back_populates="ai_plan_drafts")
    job: Mapped[AIPlanJob] = relationship(back_populates="draft")
    workouts: Mapped[list[AIPlanDraftWorkout]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AIPlanDraftWorkout(IdMixin, TimestampMixin, Base):
    __tablename__ = "ai_plan_draft_workout"
    __table_args__ = (
        Index("ix_ai_plan_draft_workout_date", "workout_date"),
        MYSQL_TABLE_ARGS,
    )

    draft_id: Mapped[int] = mapped_column(
        ForeignKey("ai_plan_draft.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workout_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekday: Mapped[str | None] = mapped_column(String(32))
    block_name: Mapped[str | None] = mapped_column(String(128))
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
    target_pace_text: Mapped[str | None] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    draft: Mapped[AIPlanDraft] = relationship(back_populates="workouts")


class ExcelImportJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "excel_import_jobs"
    __table_args__ = (
        Index("ix_excel_import_jobs_file_hash", "file_hash"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    user: Mapped[UserAccount] = relationship(back_populates="excel_import_jobs")
