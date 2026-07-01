from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from planner_core.database.base import Base, IdMixin, MYSQL_TABLE_ARGS, TimestampMixin
from planner_core.enums import (
    AIPlanDraftStatus,
    AIPlanJobStatus,
    AuthEntryMode,
    BlockType,
    ExcelImportStatus,
    FeedbackType,
    FeatureKey,
    PlanAdjustmentAction,
    PlanAdjustmentDraftStatus,
    PainScaleVersion,
    PainTrend,
    PaceZoneCode,
    RaceDistance,
    ReadinessDataQuality,
    RecoveryCheckinSource,
    TrainingStatus,
    UIMode,
    UsageEventName,
    WeeklyReviewStatus,
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
auth_entry_mode_enum = Enum(
    AuthEntryMode,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
ui_mode_enum = Enum(
    UIMode,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)
usage_event_name_enum = Enum(
    UsageEventName,
    values_callable=enum_values,
    native_enum=False,
    length=64,
)
feature_key_enum = Enum(FeatureKey, values_callable=enum_values, native_enum=False, length=64)
pain_trend_enum = Enum(PainTrend, values_callable=enum_values, native_enum=False, length=16)
recovery_checkin_source_enum = Enum(
    RecoveryCheckinSource, values_callable=enum_values, native_enum=False, length=16
)
pain_scale_version_enum = Enum(PainScaleVersion, values_callable=enum_values, native_enum=False, length=32)
readiness_data_quality_enum = Enum(
    ReadinessDataQuality, values_callable=enum_values, native_enum=False, length=16
)
weekly_review_status_enum = Enum(WeeklyReviewStatus, values_callable=enum_values, native_enum=False, length=32)
training_status_enum = Enum(TrainingStatus, values_callable=enum_values, native_enum=False, length=32)
plan_adjustment_draft_status_enum = Enum(
    PlanAdjustmentDraftStatus, values_callable=enum_values, native_enum=False, length=32
)
plan_adjustment_action_enum = Enum(
    PlanAdjustmentAction, values_callable=enum_values, native_enum=False, length=16
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
    ui_mode: Mapped[UIMode] = mapped_column(
        ui_mode_enum,
        nullable=False,
        default=UIMode.simple,
        server_default=UIMode.simple.value,
    )
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
    admin_system_settings_updates: Mapped[list[AdminSystemSettings]] = relationship(
        back_populates="updated_by",
        foreign_keys="AdminSystemSettings.updated_by_id",
    )
    ai_plan_drafts: Mapped[list[AIPlanDraft]] = relationship(back_populates="user")
    ai_coach_preference: Mapped[AIPlanCoachPreference | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    excel_import_jobs: Mapped[list[ExcelImportJob]] = relationship(back_populates="user")
    usage_events: Mapped[list[UsageEvent]] = relationship(back_populates="user")
    weekly_review_reports: Mapped[list[WeeklyReviewReport]] = relationship(back_populates="user")
    plan_adjustment_drafts: Mapped[list[PlanAdjustmentDraft]] = relationship(back_populates="user")
    feature_access_items: Mapped[list[FeatureAccess]] = relationship(
        back_populates="user", foreign_keys="FeatureAccess.user_id"
    )
    granted_feature_access_items: Mapped[list[FeatureAccess]] = relationship(
        back_populates="granted_by_user", foreign_keys="FeatureAccess.granted_by"
    )
    recovery_checkins: Mapped[list[DailyRecoveryCheckin]] = relationship(back_populates="user")
    readiness_assessments: Mapped[list[TrainingReadinessAssessment]] = relationship(back_populates="user")


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
    weekly_review_reports: Mapped[list[WeeklyReviewReport]] = relationship(back_populates="cycle")
    plan_adjustment_drafts: Mapped[list[PlanAdjustmentDraft]] = relationship(
        back_populates="cycle", foreign_keys="PlanAdjustmentDraft.cycle_id"
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
    source_weekly_reviews: Mapped[list[WeeklyReviewReport]] = relationship(
        back_populates="source_block", foreign_keys="WeeklyReviewReport.source_block_id"
    )
    target_weekly_reviews: Mapped[list[WeeklyReviewReport]] = relationship(
        back_populates="target_block", foreign_keys="WeeklyReviewReport.target_block_id"
    )


class PlannedWorkout(IdMixin, TimestampMixin, Base):
    __tablename__ = "planned_workouts"
    __table_args__ = (
        UniqueConstraint("cycle_id", "workout_date", "session_index", name="uq_planned_workouts_cycle_date_session"),
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
    session_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    date_text: Mapped[str | None] = mapped_column(String(64))
    weekday: Mapped[str | None] = mapped_column(String(32))
    month_text: Mapped[str | None] = mapped_column(String(32))
    phase_name: Mapped[str | None] = mapped_column(String(128))
    planned_content: Mapped[str] = mapped_column(Text, nullable=False)
    focus_note: Mapped[str | None] = mapped_column(Text)
    target_pace_text: Mapped[str | None] = mapped_column(String(255))
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
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    lock_reason: Mapped[str | None] = mapped_column(String(255))
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    user: Mapped[UserAccount] = relationship(back_populates="planned_workouts")
    cycle: Mapped[TrainingCycle] = relationship(back_populates="planned_workouts")
    block: Mapped[TrainingBlock] = relationship(back_populates="planned_workouts")
    workout_log: Mapped[WorkoutLog | None] = relationship(
        back_populates="planned_workout",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    adjustment_items: Mapped[list[PlanAdjustmentItem]] = relationship(back_populates="planned_workout")


class WorkoutLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_logs"
    __table_args__ = (
        UniqueConstraint("planned_workout_id", name="uq_workout_logs_planned_workout"),
        Index("ix_workout_logs_status_normalized", "status_normalized"),
        CheckConstraint(
            "pain_level IS NULL OR (pain_level >= 0 AND pain_level <= 10)",
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
    pain_scale_version: Mapped[PainScaleVersion] = mapped_column(
        pain_scale_version_enum,
        nullable=False,
        default=PainScaleVersion.native_0_10,
        server_default=PainScaleVersion.native_0_10.value,
    )
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
            "max_pain_level IS NULL OR (max_pain_level >= 0 AND max_pain_level <= 10)",
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


class WeeklyReviewReport(IdMixin, TimestampMixin, Base):
    __tablename__ = "weekly_review_report"
    __table_args__ = (
        Index("ix_weekly_review_user_cycle_created", "user_id", "cycle_id", "created_at"),
        Index("ix_weekly_review_user_block_version", "user_id", "source_block_id", "version"),
        Index("ix_weekly_review_snapshot_hash", "user_id", "source_block_id", "snapshot_hash"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_block_id: Mapped[int] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="SET NULL"), index=True
    )
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[WeeklyReviewStatus] = mapped_column(
        weekly_review_status_enum,
        nullable=False,
        default=WeeklyReviewStatus.pending,
        server_default=WeeklyReviewStatus.pending.value,
    )
    training_status: Mapped[TrainingStatus] = mapped_column(
        training_status_enum,
        nullable=False,
        default=TrainingStatus.insufficient_data,
        server_default=TrainingStatus.insufficient_data.value,
    )
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    rule_reasons_json: Mapped[list | None] = mapped_column(JSON)
    missing_data_json: Mapped[list | None] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text)
    positive_points_json: Mapped[list | None] = mapped_column(JSON)
    attention_points_json: Mapped[list | None] = mapped_column(JSON)
    next_week_strategy: Mapped[str | None] = mapped_column(Text)
    risk_notes_json: Mapped[list | None] = mapped_column(JSON)
    source_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    model_name: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="weekly_review_reports")
    cycle: Mapped[TrainingCycle] = relationship(back_populates="weekly_review_reports")
    source_block: Mapped[TrainingBlock] = relationship(
        back_populates="source_weekly_reviews", foreign_keys=[source_block_id]
    )
    target_block: Mapped[TrainingBlock | None] = relationship(
        back_populates="target_weekly_reviews", foreign_keys=[target_block_id]
    )
    adjustment_draft: Mapped[PlanAdjustmentDraft | None] = relationship(
        back_populates="review_report", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class PlanAdjustmentDraft(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_adjustment_draft"
    __table_args__ = (
        Index("ix_plan_adjustment_user_status", "user_id", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_review_report.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    cycle_id: Mapped[int] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    target_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_blocks.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[PlanAdjustmentDraftStatus] = mapped_column(
        plan_adjustment_draft_status_enum,
        nullable=False,
        default=PlanAdjustmentDraftStatus.draft,
        server_default=PlanAdjustmentDraftStatus.draft.value,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    original_week_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    suggested_week_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_name: Mapped[str | None] = mapped_column(String(128))
    source_filename: Mapped[str | None] = mapped_column(String(255))
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    parser_version: Mapped[str | None] = mapped_column(String(32))
    merge_strategy: Mapped[str | None] = mapped_column(String(64))
    anchor_strategy: Mapped[str | None] = mapped_column(String(64))
    effective_date: Mapped[date | None] = mapped_column(Date)
    target_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    normalized_payload_json: Mapped[list | None] = mapped_column(JSON)
    diff_summary_json: Mapped[dict | None] = mapped_column(JSON)
    conflict_summary_json: Mapped[list | None] = mapped_column(JSON)
    warnings_json: Mapped[list | None] = mapped_column(JSON)
    client_request_id: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="plan_adjustment_drafts")
    review_report: Mapped[WeeklyReviewReport | None] = relationship(back_populates="adjustment_draft")
    cycle: Mapped[TrainingCycle] = relationship(back_populates="plan_adjustment_drafts", foreign_keys=[cycle_id])
    items: Mapped[list[PlanAdjustmentItem]] = relationship(
        back_populates="draft", cascade="all, delete-orphan", passive_deletes=True
    )


class PlanAdjustmentItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_adjustment_item"
    __table_args__ = (
        Index("ix_plan_adjustment_item_draft_workout", "draft_id", "planned_workout_id"),
        MYSQL_TABLE_ARGS,
    )

    draft_id: Mapped[int] = mapped_column(
        ForeignKey("plan_adjustment_draft.id", ondelete="CASCADE"), nullable=False, index=True
    )
    planned_workout_id: Mapped[int | None] = mapped_column(
        ForeignKey("planned_workouts.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    operation: Mapped[str | None] = mapped_column(String(32))
    planned_date: Mapped[date | None] = mapped_column(Date)
    session_index: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[PlanAdjustmentAction] = mapped_column(plan_adjustment_action_enum, nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_content: Mapped[str] = mapped_column(Text, nullable=False)
    original_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    suggested_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    original_main_type: Mapped[str | None] = mapped_column(String(32))
    suggested_main_type: Mapped[str | None] = mapped_column(String(32))
    original_target_pace_text: Mapped[str | None] = mapped_column(String(255))
    suggested_target_pace_text: Mapped[str | None] = mapped_column(String(255))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    normalized_item_json: Mapped[dict | None] = mapped_column(JSON)
    conflict_json: Mapped[list | None] = mapped_column(JSON)
    warnings_json: Mapped[list | None] = mapped_column(JSON)
    base_plan_version: Mapped[int | None] = mapped_column(Integer)
    base_workout_updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    draft: Mapped[PlanAdjustmentDraft] = relationship(back_populates="items")
    planned_workout: Mapped[PlannedWorkout | None] = relationship(back_populates="adjustment_items")


class PlanImportAudit(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_import_audit"
    __table_args__ = (
        Index("ix_plan_import_audit_user_created", "user_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    import_id: Mapped[int] = mapped_column(ForeignKey("plan_adjustment_draft.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32))
    merge_strategy: Mapped[str | None] = mapped_column(String(64))
    effective_date: Mapped[date | None] = mapped_column(Date)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    protected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")
    client_request_id: Mapped[str | None] = mapped_column(String(128))


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


class FeatureAccess(IdMixin, TimestampMixin, Base):
    __tablename__ = "feature_access"
    __table_args__ = (
        UniqueConstraint("user_id", "feature_key", name="uq_feature_access_user_feature"),
        Index("ix_feature_access_feature_enabled", "feature_key", "enabled"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_key: Mapped[FeatureKey] = mapped_column(feature_key_enum, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    granted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[UserAccount] = relationship(
        back_populates="feature_access_items", foreign_keys=[user_id]
    )
    granted_by_user: Mapped[UserAccount | None] = relationship(
        back_populates="granted_feature_access_items", foreign_keys=[granted_by]
    )


class DailyRecoveryCheckin(IdMixin, TimestampMixin, Base):
    __tablename__ = "daily_recovery_checkin"
    __table_args__ = (
        UniqueConstraint("user_id", "checkin_date", name="uq_daily_recovery_user_date"),
        Index("ix_daily_recovery_user_date", "user_id", "checkin_date"),
        CheckConstraint(
            "sleep_quality IS NULL OR (sleep_quality >= 1 AND sleep_quality <= 5)",
            name="ck_daily_recovery_sleep_quality",
        ),
        CheckConstraint(
            "subjective_fatigue IS NULL OR (subjective_fatigue >= 1 AND subjective_fatigue <= 5)",
            name="ck_daily_recovery_subjective_fatigue",
        ),
        CheckConstraint(
            "muscle_soreness IS NULL OR (muscle_soreness >= 1 AND muscle_soreness <= 5)",
            name="ck_daily_recovery_muscle_soreness",
        ),
        CheckConstraint(
            "stress_level IS NULL OR (stress_level >= 1 AND stress_level <= 5)",
            name="ck_daily_recovery_stress_level",
        ),
        CheckConstraint(
            "mood_level IS NULL OR (mood_level >= 1 AND mood_level <= 5)",
            name="ck_daily_recovery_mood_level",
        ),
        CheckConstraint(
            "leg_feeling IS NULL OR (leg_feeling >= 1 AND leg_feeling <= 5)",
            name="ck_daily_recovery_leg_feeling",
        ),
        CheckConstraint(
            "pain_level IS NULL OR (pain_level >= 0 AND pain_level <= 10)",
            name="ck_daily_recovery_pain_level",
        ),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    sleep_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    sleep_quality: Mapped[int | None] = mapped_column(Integer)
    subjective_fatigue: Mapped[int | None] = mapped_column(Integer)
    muscle_soreness: Mapped[int | None] = mapped_column(Integer)
    stress_level: Mapped[int | None] = mapped_column(Integer)
    mood_level: Mapped[int | None] = mapped_column(Integer)
    leg_feeling: Mapped[int | None] = mapped_column(Integer)
    resting_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    hrv_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    hrv_metric: Mapped[str | None] = mapped_column(String(32))
    hrv_source: Mapped[str | None] = mapped_column(String(64))
    pain_level: Mapped[int | None] = mapped_column(Integer)
    pain_location: Mapped[str | None] = mapped_column(String(128))
    pain_trend: Mapped[PainTrend] = mapped_column(
        pain_trend_enum,
        nullable=False,
        default=PainTrend.unknown,
        server_default=PainTrend.unknown.value,
    )
    pain_affects_gait: Mapped[bool | None] = mapped_column(Boolean)
    illness_symptoms: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[RecoveryCheckinSource] = mapped_column(
        recovery_checkin_source_enum,
        nullable=False,
        default=RecoveryCheckinSource.manual,
        server_default=RecoveryCheckinSource.manual.value,
    )

    user: Mapped[UserAccount] = relationship(back_populates="recovery_checkins")


class TrainingReadinessAssessment(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_readiness_assessment"
    __table_args__ = (
        Index("ix_readiness_user_date_created", "user_id", "assessment_date", "created_at"),
        Index("ix_readiness_user_status", "user_id", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[TrainingStatus] = mapped_column(training_status_enum, nullable=False)
    data_quality: Mapped[ReadinessDataQuality] = mapped_column(readiness_data_quality_enum, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    external_load_signals_json: Mapped[list | None] = mapped_column(JSON)
    internal_load_signals_json: Mapped[list | None] = mapped_column(JSON)
    recovery_signals_json: Mapped[list | None] = mapped_column(JSON)
    performance_signals_json: Mapped[list | None] = mapped_column(JSON)
    pain_signals_json: Mapped[list | None] = mapped_column(JSON)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False)
    recommendations_json: Mapped[list] = mapped_column(JSON, nullable=False)
    missing_data_json: Mapped[list | None] = mapped_column(JSON)
    source_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped[UserAccount] = relationship(back_populates="readiness_assessments")


class UsageEvent(IdMixin, Base):
    __tablename__ = "usage_event"
    __table_args__ = (
        Index("ix_usage_event_user_occurred", "user_id", "occurred_at"),
        Index("ix_usage_event_event_occurred", "event_name", "occurred_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_name: Mapped[UsageEventName] = mapped_column(usage_event_name_enum, nullable=False)
    page_path: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped[UserAccount | None] = relationship(back_populates="usage_events")


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
        String(128),
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


class AdminSystemSettings(IdMixin, TimestampMixin, Base):
    __tablename__ = "admin_system_settings"
    __table_args__ = MYSQL_TABLE_ARGS

    auth_entry_mode: Mapped[AuthEntryMode] = mapped_column(
        auth_entry_mode_enum,
        nullable=False,
        default=AuthEntryMode.standalone,
        server_default=AuthEntryMode.standalone.value,
    )
    allow_public_registration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_account.id", ondelete="SET NULL"),
        index=True,
    )

    updated_by: Mapped[UserAccount | None] = relationship(
        back_populates="admin_system_settings_updates",
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
