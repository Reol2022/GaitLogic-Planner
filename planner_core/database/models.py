from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

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
    Time,
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
    PlannedWorkoutLifecycleStatus,
    RaceDistance,
    ReadinessDataQuality,
    RecoveryCheckinSource,
    RunnerStateSnapshotReceiptStatus,
    RunnerStateSnapshotTriggerType,
    TrainingCycleStatus,
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
training_cycle_status_enum = Enum(
    TrainingCycleStatus,
    values_callable=enum_values,
    native_enum=False,
    length=16,
)
planned_workout_lifecycle_status_enum = Enum(
    PlannedWorkoutLifecycleStatus,
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
runner_state_snapshot_trigger_type_enum = Enum(
    RunnerStateSnapshotTriggerType,
    values_callable=enum_values,
    native_enum=False,
    length=32,
)
runner_state_snapshot_receipt_status_enum = Enum(
    RunnerStateSnapshotReceiptStatus,
    values_callable=enum_values,
    native_enum=False,
    length=40,
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
    workout_import_batches: Mapped[list[WorkoutImportBatch]] = relationship(back_populates="user")
    workout_import_audits: Mapped[list[WorkoutImportAudit]] = relationship(back_populates="user")
    external_account_connections: Mapped[list[ExternalAccountConnection]] = relationship(back_populates="user")
    external_sync_jobs: Mapped[list[ExternalSyncJob]] = relationship(back_populates="user")
    external_activities: Mapped[list[ExternalActivity]] = relationship(back_populates="user")
    external_activity_links: Mapped[list[WorkoutLogExternalActivity]] = relationship(back_populates="user")
    training_rule_evaluations: Mapped[list[TrainingRuleEvaluation]] = relationship(back_populates="user")
    training_adjustment_drafts: Mapped[list[TrainingAdjustmentDraft]] = relationship(back_populates="user")
    training_rule_reviews: Mapped[list[TrainingRuleReview]] = relationship(back_populates="reviewer")
    training_rule_test_runs: Mapped[list[TrainingRuleTestRun]] = relationship(back_populates="created_by_user")
    training_rule_audit_logs: Mapped[list[TrainingRuleAuditLog]] = relationship(back_populates="actor")
    runner_state_snapshots: Mapped[list[RunnerStateSnapshotRecord]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TrainingCycle(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_cycles"
    __table_args__ = (
        UniqueConstraint("active_user_id", name="uq_training_cycles_one_active_per_user"),
        Index("ix_training_cycles_user_status", "user_id", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    goal: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[TrainingCycleStatus] = mapped_column(
        training_cycle_status_enum,
        nullable=False,
        default=TrainingCycleStatus.draft,
        server_default=TrainingCycleStatus.draft.value,
    )
    active_user_id: Mapped[int | None] = mapped_column(Integer)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    superseded_by_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="SET NULL"),
        index=True,
    )
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
        Index("ix_planned_workouts_lifecycle", "user_id", "cycle_id", "lifecycle_status"),
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
    lifecycle_status: Mapped[PlannedWorkoutLifecycleStatus] = mapped_column(
        planned_workout_lifecycle_status_enum,
        nullable=False,
        default=PlannedWorkoutLifecycleStatus.planned,
        server_default=PlannedWorkoutLifecycleStatus.planned.value,
    )

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
        Index("ix_workout_logs_user_cycle_date", "user_id", "cycle_id", "activity_date"),
        Index("ix_workout_logs_user_activity_date", "user_id", "activity_date", "session_index"),
        Index("ix_workout_logs_activity_fingerprint", "user_id", "activity_fingerprint"),
        Index("ix_workout_logs_status_normalized", "status_normalized"),
        CheckConstraint(
            "pain_level IS NULL OR (pain_level >= 0 AND pain_level <= 10)",
            name="ck_workout_logs_pain_level_range",
        ),
        MYSQL_TABLE_ARGS,
    )

    planned_workout_id: Mapped[int | None] = mapped_column(
        ForeignKey("planned_workouts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="SET NULL"),
        nullable=True,
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
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer)
    avg_pace_seconds_per_km: Mapped[int | None] = mapped_column(Integer)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    average_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    max_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    elevation_gain_m: Mapped[int | None] = mapped_column(Integer)
    calories_kcal: Mapped[int | None] = mapped_column(Integer)
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
    activity_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str | None] = mapped_column(String(64))
    session_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sport_type: Mapped[str] = mapped_column(String(32), nullable=False, default="running", server_default="running")
    workout_type: Mapped[str | None] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(128))
    is_unplanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", server_default="manual")
    source_import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("workout_import_batch.id", ondelete="SET NULL"), index=True)
    external_activity_id: Mapped[str | None] = mapped_column(String(128))
    activity_fingerprint: Mapped[str | None] = mapped_column(String(64))
    field_sources_json: Mapped[dict | None] = mapped_column(JSON)
    subjective_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    cycle_assignment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned", server_default="assigned")

    user: Mapped[UserAccount] = relationship(back_populates="workout_logs")
    planned_workout: Mapped[PlannedWorkout | None] = relationship(back_populates="workout_log")
    cycle: Mapped[TrainingCycle | None] = relationship()
    external_activity_links: Mapped[list[WorkoutLogExternalActivity]] = relationship(
        back_populates="workout_log", cascade="all, delete-orphan", passive_deletes=True
    )


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


class WorkoutImportBatch(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_import_batch"
    __table_args__ = (
        UniqueConstraint("user_id", "client_request_id", name="uq_workout_import_user_client_request"),
        Index("ix_workout_import_batch_user_status", "user_id", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(255))
    parser_version: Mapped[str | None] = mapped_column(String(32))
    normalization_version: Mapped[str | None] = mapped_column(String(32))
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64))
    merge_strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready", server_default="ready")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matched_plan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matched_log_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unplanned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ready_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    client_request_id: Mapped[str | None] = mapped_column(String(128))
    warnings_json: Mapped[list | None] = mapped_column(JSON)
    preview_summary_json: Mapped[dict | None] = mapped_column(JSON)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="workout_import_batches")
    items: Mapped[list[WorkoutImportItem]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True
    )
    audit: Mapped[WorkoutImportAudit | None] = relationship(
        back_populates="batch", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class WorkoutImportItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_import_item"
    __table_args__ = (
        Index("ix_workout_import_item_batch_date", "batch_id", "activity_date", "session_index"),
        MYSQL_TABLE_ARGS,
    )

    batch_id: Mapped[int] = mapped_column(ForeignKey("workout_import_batch.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int | None] = mapped_column(Integer)
    activity_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    session_index: Mapped[int | None] = mapped_column(Integer)
    normalized_data_json: Mapped[dict | None] = mapped_column(JSON)
    matched_plan_id: Mapped[int | None] = mapped_column(ForeignKey("planned_workouts.id", ondelete="SET NULL"), index=True)
    matched_log_id: Mapped[int | None] = mapped_column(ForeignKey("workout_logs.id", ondelete="SET NULL"), index=True)
    applied_log_id: Mapped[int | None] = mapped_column(ForeignKey("workout_logs.id", ondelete="SET NULL"), index=True)
    match_status: Mapped[str] = mapped_column(String(32), nullable=False, default="invalid", server_default="invalid")
    match_confidence: Mapped[str | None] = mapped_column(String(16))
    suggested_action: Mapped[str] = mapped_column(String(32), nullable=False, default="manual_review", server_default="manual_review")
    user_action: Mapped[str | None] = mapped_column(String(32))
    validation_errors_json: Mapped[list | None] = mapped_column(JSON)
    warnings_json: Mapped[list | None] = mapped_column(JSON)
    field_diff_json: Mapped[list | None] = mapped_column(JSON)
    activity_fingerprint: Mapped[str | None] = mapped_column(String(64))

    batch: Mapped[WorkoutImportBatch] = relationship(back_populates="items")
    matched_plan: Mapped[PlannedWorkout | None] = relationship()
    matched_log: Mapped[WorkoutLog | None] = relationship(foreign_keys=[matched_log_id])
    applied_log: Mapped[WorkoutLog | None] = relationship(foreign_keys=[applied_log_id])


class WorkoutImportAudit(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_import_audit"
    __table_args__ = (
        Index("ix_workout_import_audit_user_created", "user_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("workout_import_batch.id", ondelete="CASCADE"), nullable=False, unique=True)
    source_type: Mapped[str | None] = mapped_column(String(32))
    merge_strategy: Mapped[str | None] = mapped_column(String(64))
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    linked_plan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unplanned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    conflict_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")
    client_request_id: Mapped[str | None] = mapped_column(String(128))

    user: Mapped[UserAccount] = relationship(back_populates="workout_import_audits")
    batch: Mapped[WorkoutImportBatch] = relationship(back_populates="audit")


class ExternalAccountConnection(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_account_connection"
    __table_args__ = (
        UniqueConstraint("active_user_provider_key", name="uq_external_connection_active_user_provider"),
        UniqueConstraint("active_account_key", name="uq_external_connection_active_account"),
        Index("ix_external_connection_user_provider", "user_id", "provider", "status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin", server_default="garmin")
    region: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="connected", server_default="connected")
    masked_account_identifier: Mapped[str | None] = mapped_column(String(255))
    account_identifier_hash: Mapped[str | None] = mapped_column(String(64))
    active_user_provider_key: Mapped[str | None] = mapped_column(String(128))
    active_account_key: Mapped[str | None] = mapped_column(String(128))
    encrypted_token_payload: Mapped[str | None] = mapped_column(Text)
    token_key_version: Mapped[str | None] = mapped_column(String(32))
    connector_version: Mapped[str | None] = mapped_column(String(32))
    auto_import_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    auto_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    auto_sync_last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime)
    sync_cursor: Mapped[str | None] = mapped_column(String(512))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="external_account_connections")
    sync_jobs: Mapped[list[ExternalSyncJob]] = relationship(back_populates="connection")
    raw_activities: Mapped[list[ExternalActivityRaw]] = relationship(back_populates="connection")
    activities: Mapped[list[ExternalActivity]] = relationship(back_populates="connection")


class ExternalSyncJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_sync_job"
    __table_args__ = (
        UniqueConstraint("connection_id", "idempotency_key", name="uq_external_sync_job_idempotency"),
        Index("ix_external_sync_job_status_created", "status", "created_at"),
        Index("ix_external_sync_job_user_created", "user_id", "created_at"),
        Index("ix_external_sync_job_sync_run_id", "sync_run_id"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("external_account_connection.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin", server_default="garmin")
    sync_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_start: Mapped[datetime | None] = mapped_column(DateTime)
    requested_end: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", server_default="queued")
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    sync_run_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default=lambda: str(uuid4()),
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    matched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unplanned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    needs_review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ignored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_committed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    committed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_log_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_log_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unchanged_activity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    runner_state_affecting_change_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(64))
    safe_error_message: Mapped[str | None] = mapped_column(String(255))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="external_sync_jobs")
    connection: Mapped[ExternalAccountConnection] = relationship(back_populates="sync_jobs")
    raw_activities: Mapped[list[ExternalActivityRaw]] = relationship(back_populates="sync_job")
    activities: Mapped[list[ExternalActivity]] = relationship(back_populates="sync_job")


class ExternalActivityRaw(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_activity_raw"
    __table_args__ = (
        UniqueConstraint("provider", "external_activity_id", "payload_hash", name="uq_external_raw_payload"),
        Index("ix_external_raw_user_expires", "user_id", "expires_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("external_account_connection.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_job_id: Mapped[int | None] = mapped_column(ForeignKey("external_sync_job.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin", server_default="garmin")
    external_activity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    desensitization_version: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin-raw-v1", server_default="garmin-raw-v1")

    user: Mapped[UserAccount] = relationship()
    connection: Mapped[ExternalAccountConnection] = relationship(back_populates="raw_activities")
    sync_job: Mapped[ExternalSyncJob | None] = relationship(back_populates="raw_activities")
    activity: Mapped[ExternalActivity | None] = relationship(back_populates="raw_activity", uselist=False)


class ExternalActivity(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_activity"
    __table_args__ = (
        UniqueConstraint("provider", "external_activity_id", name="uq_external_activity_provider_id"),
        Index("ix_external_activity_user_date", "user_id", "activity_date", "processing_status"),
        Index("ix_external_activity_user_status", "user_id", "processing_status"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("external_account_connection.id", ondelete="CASCADE"), nullable=False, index=True)
    sync_job_id: Mapped[int | None] = mapped_column(ForeignKey("external_sync_job.id", ondelete="SET NULL"), index=True)
    raw_activity_id: Mapped[int | None] = mapped_column(ForeignKey("external_activity_raw.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin", server_default="garmin")
    external_activity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    connector_version: Mapped[str] = mapped_column(String(32), nullable=False)
    normalization_version: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin-activity-v1", server_default="garmin-activity-v1")
    segmentation_version: Mapped[str | None] = mapped_column(String(64))
    classification_version: Mapped[str | None] = mapped_column(String(64))
    payload_hash: Mapped[str | None] = mapped_column(String(64))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    activity_name: Mapped[str | None] = mapped_column(String(255))
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    activity_subtype: Mapped[str | None] = mapped_column(String(64))
    start_time_utc: Mapped[datetime | None] = mapped_column(DateTime)
    start_time_local: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai", server_default="Asia/Shanghai")
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="synced", server_default="synced")
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    apply_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_applied", server_default="not_applied")
    composite_session_key: Mapped[str | None] = mapped_column(String(128))
    match_confidence: Mapped[str | None] = mapped_column(String(16))
    planned_workout_id: Mapped[int | None] = mapped_column(ForeignKey("planned_workouts.id", ondelete="SET NULL"), index=True)
    workout_log_id: Mapped[int | None] = mapped_column(ForeignKey("workout_logs.id", ondelete="SET NULL"), index=True)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    timer_time_seconds: Mapped[int | None] = mapped_column(Integer)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer)
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    average_pace_seconds_per_km: Mapped[int | None] = mapped_column(Integer)
    max_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    best_pace_seconds_per_km: Mapped[int | None] = mapped_column(Integer)
    average_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    min_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    average_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    max_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    cadence_normalization_method: Mapped[str | None] = mapped_column(String(64))
    elevation_gain_m: Mapped[int | None] = mapped_column(Integer)
    elevation_loss_m: Mapped[int | None] = mapped_column(Integer)
    calories_kcal: Mapped[int | None] = mapped_column(Integer)
    average_stride_length_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    average_vertical_ratio_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    average_vertical_oscillation_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    average_ground_contact_time_ms: Mapped[int | None] = mapped_column(Integer)
    ground_contact_balance_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    average_running_power_w: Mapped[int | None] = mapped_column(Integer)
    max_running_power_w: Mapped[int | None] = mapped_column(Integer)
    garmin_primary_benefit: Mapped[str | None] = mapped_column(String(128))
    garmin_aerobic_training_effect: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    garmin_anaerobic_training_effect: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    garmin_training_load: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    garmin_recovery_time_seconds: Mapped[int | None] = mapped_column(Integer)
    high_intensity_distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    data_quality: Mapped[str] = mapped_column(String(32), nullable=False, default="valid", server_default="valid")
    quality_warnings_json: Mapped[list | None] = mapped_column(JSON)
    field_sources_json: Mapped[dict | None] = mapped_column(JSON)
    ignored_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="external_activities")
    connection: Mapped[ExternalAccountConnection] = relationship(back_populates="activities")
    sync_job: Mapped[ExternalSyncJob | None] = relationship(back_populates="activities")
    raw_activity: Mapped[ExternalActivityRaw | None] = relationship(back_populates="activity")
    planned_workout: Mapped[PlannedWorkout | None] = relationship()
    workout_log: Mapped[WorkoutLog | None] = relationship()
    laps: Mapped[list[ExternalActivityLap]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", passive_deletes=True
    )
    workout_links: Mapped[list[WorkoutLogExternalActivity]] = relationship(
        back_populates="external_activity", cascade="all, delete-orphan", passive_deletes=True
    )
    resolutions: Mapped[list[ExternalActivityResolution]] = relationship(
        back_populates="external_activity", cascade="all, delete-orphan", passive_deletes=True
    )


class ExternalActivityLap(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_activity_lap"
    __table_args__ = (
        UniqueConstraint("external_activity_id", "lap_index", name="uq_external_activity_lap_index"),
        MYSQL_TABLE_ARGS,
    )

    external_activity_id: Mapped[int] = mapped_column(ForeignKey("external_activity.id", ondelete="CASCADE"), nullable=False, index=True)
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    external_lap_id: Mapped[str | None] = mapped_column(String(128))
    start_time: Mapped[datetime | None] = mapped_column(DateTime)
    start_offset_seconds: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    timer_time_seconds: Mapped[int | None] = mapped_column(Integer)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer)
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(8, 3))
    average_pace_seconds_per_km: Mapped[int | None] = mapped_column(Integer)
    average_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate_bpm: Mapped[int | None] = mapped_column(Integer)
    average_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    elevation_gain_m: Mapped[int | None] = mapped_column(Integer)
    lap_type: Mapped[str | None] = mapped_column(String(64))
    workout_step_type: Mapped[str | None] = mapped_column(String(64))
    segment_role: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    classification_source: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", server_default="unknown")
    classification_confidence: Mapped[str] = mapped_column(String(16), nullable=False, default="low", server_default="low")
    data_quality: Mapped[str] = mapped_column(String(32), nullable=False, default="valid", server_default="valid")

    activity: Mapped[ExternalActivity] = relationship(back_populates="laps")


class WorkoutLogExternalActivity(IdMixin, TimestampMixin, Base):
    __tablename__ = "workout_log_external_activity"
    __table_args__ = (
        UniqueConstraint("workout_log_id", "external_activity_id", name="uq_workout_log_external_activity"),
        UniqueConstraint("external_activity_id", name="uq_workout_log_external_single_activity"),
        Index("ix_workout_log_external_user", "user_id", "workout_log_id"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    workout_log_id: Mapped[int] = mapped_column(ForeignKey("workout_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    external_activity_id: Mapped[int] = mapped_column(ForeignKey("external_activity.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False, default="matched", server_default="matched")
    match_confidence: Mapped[str | None] = mapped_column(String(16))
    resolution_status: Mapped[str] = mapped_column(String(32), nullable=False, default="auto_applied", server_default="auto_applied")
    field_sources_json: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped[UserAccount] = relationship(back_populates="external_activity_links")
    workout_log: Mapped[WorkoutLog] = relationship(back_populates="external_activity_links")
    external_activity: Mapped[ExternalActivity] = relationship(back_populates="workout_links")


class ExternalActivityResolution(IdMixin, TimestampMixin, Base):
    __tablename__ = "external_activity_resolution"
    __table_args__ = (
        Index("ix_external_activity_resolution_user_created", "user_id", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True)
    external_activity_id: Mapped[int] = mapped_column(ForeignKey("external_activity.id", ondelete="CASCADE"), nullable=False, index=True)
    workout_log_id: Mapped[int | None] = mapped_column(ForeignKey("workout_logs.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_state_json: Mapped[dict | None] = mapped_column(JSON)
    new_state_json: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String(255))
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user", server_default="user")

    external_activity: Mapped[ExternalActivity] = relationship(back_populates="resolutions")
    workout_log: Mapped[WorkoutLog | None] = relationship()


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


class RunnerStateSnapshotRecord(IdMixin, Base):
    __tablename__ = "runner_state_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "data_cutoff_date",
            "payload_hash",
            name="uq_runner_state_snapshot_user_cutoff_hash",
        ),
        Index(
            "ix_runner_state_snapshots_user_cutoff",
            "user_id",
            "data_cutoff_date",
        ),
        Index(
            "ix_runner_state_snapshots_user_created",
            "user_id",
            "created_at",
        ),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_cutoff_date: Mapped[date] = mapped_column(Date, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    trigger_type: Mapped[RunnerStateSnapshotTriggerType] = mapped_column(
        runner_state_snapshot_trigger_type_enum,
        nullable=False,
        default=RunnerStateSnapshotTriggerType.MANUAL,
        server_default=RunnerStateSnapshotTriggerType.MANUAL.value,
    )
    trigger_reference: Mapped[str | None] = mapped_column(String(128))
    snapshot_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    distance_7d_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    distance_28d_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    volume_trend: Mapped[str | None] = mapped_column(String(32))
    training_consistency: Mapped[str | None] = mapped_column(String(32))
    fatigue_state: Mapped[str | None] = mapped_column(String(32))
    training_phase: Mapped[str | None] = mapped_column(String(32))
    risk_flag_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    evidence_coverage: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    data_completeness: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    snapshot_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    user: Mapped[UserAccount] = relationship(back_populates="runner_state_snapshots")


class RunnerStateSnapshotTriggerReceipt(IdMixin, TimestampMixin, Base):
    __tablename__ = "runner_state_snapshot_trigger_receipt"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "trigger_type",
            "trigger_reference",
            name="uq_runner_state_receipt_user_trigger_reference",
        ),
        CheckConstraint(
            "material_change_count >= 0",
            name="ck_runner_state_receipt_material_change_nonnegative",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_runner_state_receipt_attempt_count_nonnegative",
        ),
        Index("ix_runner_state_receipt_user_created", "user_id", "created_at"),
        Index("ix_runner_state_receipt_sync_job", "sync_job_id"),
        Index("ix_runner_state_receipt_status_locked", "status", "locked_at"),
        Index("ix_runner_state_receipt_snapshot", "snapshot_id"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False
    )
    trigger_type: Mapped[RunnerStateSnapshotTriggerType] = mapped_column(
        runner_state_snapshot_trigger_type_enum,
        nullable=False,
    )
    trigger_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[RunnerStateSnapshotReceiptStatus] = mapped_column(
        runner_state_snapshot_receipt_status_enum,
        nullable=False,
    )
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("runner_state_snapshots.id", ondelete="SET NULL")
    )
    sync_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("external_sync_job.id", ondelete="SET NULL")
    )
    material_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_committed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    processing_token: Mapped[str | None] = mapped_column(String(36))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(64))
    safe_error_message: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[UserAccount] = relationship(viewonly=True)
    snapshot: Mapped[RunnerStateSnapshotRecord | None] = relationship(viewonly=True)
    sync_job: Mapped[ExternalSyncJob | None] = relationship(viewonly=True)


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


class TrainingKnowledgeItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_knowledge_items"
    __table_args__ = (
        UniqueConstraint("code", name="uq_training_knowledge_items_code"),
        Index("ix_training_knowledge_items_category_status", "category", "status"),
        Index("ix_training_knowledge_items_status", "status"),
        MYSQL_TABLE_ARGS,
    )

    code: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    aliases_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    attributes_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    related_codes_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_level: Mapped[str] = mapped_column(String(64), nullable=False, default="product_rule")
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")


class TrainingRule(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_rules"
    __table_args__ = (
        UniqueConstraint("code", name="uq_training_rules_code"),
        Index("ix_training_rules_category_enabled", "category", "enabled"),
        Index("ix_training_rules_scope_enabled", "scope", "enabled"),
        Index("ix_training_rules_severity", "severity"),
        Index("ix_training_rules_lifecycle", "lifecycle_status"),
        MYSQL_TABLE_ARGS,
    )

    code: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="generic", server_default="generic")
    conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation_template: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info", server_default="info")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    evidence_refs_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="product_rule", server_default="product_rule")
    current_version: Mapped[str | None] = mapped_column(String(32))
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="published", server_default="published")
    applicability_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thresholds_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_rule_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    versions: Mapped[list[TrainingRuleVersion]] = relationship(
        back_populates="current_rule",
        foreign_keys="TrainingRuleVersion.rule_code",
        primaryjoin="TrainingRule.code == foreign(TrainingRuleVersion.rule_code)",
        viewonly=True,
    )
    current_version_row: Mapped[TrainingRuleVersion | None] = relationship(foreign_keys=[current_version_id])


class TrainingEvidenceSource(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_evidence_sources"
    __table_args__ = (
        UniqueConstraint("code", name="uq_training_evidence_sources_code"),
        Index("ix_training_evidence_type_level", "source_type", "evidence_level"),
        Index("ix_training_evidence_review_status", "review_status"),
        MYSQL_TABLE_ARGS,
    )

    code: Mapped[str] = mapped_column(String(96), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authors: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    publication_name: Mapped[str | None] = mapped_column(String(255))
    doi: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(512))
    language: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_level: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    copyright_note: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class TrainingRuleEvidenceLink(IdMixin, Base):
    __tablename__ = "training_rule_evidence_links"
    __table_args__ = (
        UniqueConstraint("rule_code", "rule_version", "evidence_source_code", "relationship_type", name="uq_rule_evidence_version_link"),
        Index("ix_rule_evidence_rule", "rule_code", "rule_version"),
        Index("ix_rule_evidence_source", "evidence_source_code"),
        MYSQL_TABLE_ARGS,
    )

    rule_code: Mapped[str] = mapped_column(String(96), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_source_code: Mapped[str] = mapped_column(String(96), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(64), nullable=False)
    support_note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )


class TrainingRuleVersion(IdMixin, Base):
    __tablename__ = "training_rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_training_rule_versions_code_version"),
        Index("ix_training_rule_versions_code_status", "rule_code", "lifecycle_status"),
        Index("ix_training_rule_versions_scope_status", "scope", "lifecycle_status"),
        Index("ix_training_rule_versions_content_hash", "content_hash"),
        MYSQL_TABLE_ARGS,
    )

    rule_code: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    conditions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    applicability_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    thresholds_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    explanation_template: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime)

    current_rule: Mapped[TrainingRule | None] = relationship(
        back_populates="versions",
        primaryjoin="foreign(TrainingRuleVersion.rule_code) == TrainingRule.code",
        viewonly=True,
    )


class TrainingRuleReview(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_rule_reviews"
    __table_args__ = (
        Index("ix_training_rule_reviews_rule", "rule_code", "rule_version"),
        Index("ix_training_rule_reviews_status", "review_status"),
        MYSQL_TABLE_ARGS,
    )

    rule_code: Mapped[str] = mapped_column(String(96), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    review_comment: Mapped[str | None] = mapped_column(Text)
    checklist_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    reviewer: Mapped[UserAccount | None] = relationship(back_populates="training_rule_reviews")


class TrainingRuleTestCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_rule_test_cases"
    __table_args__ = (
        UniqueConstraint("code", name="uq_training_rule_test_cases_code"),
        Index("ix_training_rule_test_cases_context", "context_type", "enabled"),
        MYSQL_TABLE_ARGS,
    )

    code: Mapped[str] = mapped_column(String(96), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    context_type: Mapped[str] = mapped_column(String(64), nullable=False)
    facts_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="positive", server_default="positive")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")


class TrainingRuleTestRun(IdMixin, Base):
    __tablename__ = "training_rule_test_runs"
    __table_args__ = (
        Index("ix_training_rule_test_runs_created", "started_at"),
        Index("ix_training_rule_test_runs_ruleset", "ruleset_version"),
        MYSQL_TABLE_ARGS,
    )

    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running", server_default="running")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    result_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True)

    created_by_user: Mapped[UserAccount | None] = relationship(back_populates="training_rule_test_runs")
    results: Mapped[list[TrainingRuleTestResult]] = relationship(
        back_populates="test_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TrainingRuleTestResult(IdMixin, Base):
    __tablename__ = "training_rule_test_results"
    __table_args__ = (
        Index("ix_training_rule_test_results_run", "test_run_id"),
        Index("ix_training_rule_test_results_case", "test_case_code"),
        MYSQL_TABLE_ARGS,
    )

    test_run_id: Mapped[int] = mapped_column(ForeignKey("training_rule_test_runs.id", ondelete="CASCADE"), nullable=False)
    test_case_code: Mapped[str] = mapped_column(String(96), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    actual_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    diff_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)

    test_run: Mapped[TrainingRuleTestRun] = relationship(back_populates="results")


class TrainingRuleAuditLog(IdMixin, Base):
    __tablename__ = "training_rule_audit_logs"
    __table_args__ = (
        Index("ix_training_rule_audit_actor_created", "actor_user_id", "created_at"),
        Index("ix_training_rule_audit_target", "target_type", "target_code", "target_version"),
        MYSQL_TABLE_ARGS,
    )

    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("user_account.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_code: Mapped[str | None] = mapped_column(String(96))
    target_version: Mapped[str | None] = mapped_column(String(32))
    before_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    after_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    actor: Mapped[UserAccount | None] = relationship(back_populates="training_rule_audit_logs")


class TrainingRuleEvaluation(IdMixin, Base):
    __tablename__ = "training_rule_evaluations"
    __table_args__ = (
        Index("ix_training_rule_eval_user_created", "user_id", "created_at"),
        Index("ix_training_rule_eval_context", "context_type", "context_id"),
        Index("ix_training_rule_eval_hash", "user_id", "context_type", "context_id", "facts_hash"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    context_type: Mapped[str] = mapped_column(String(64), nullable=False)
    context_id: Mapped[str | None] = mapped_column(String(128))
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    final_result_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    dominant_rule_code: Mapped[str | None] = mapped_column(String(96))
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(64), nullable=False)
    facts_hash: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(64))
    is_stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    stale_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    user: Mapped[UserAccount] = relationship(back_populates="training_rule_evaluations")
    hits: Mapped[list[TrainingRuleHit]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TrainingRuleHit(IdMixin, Base):
    __tablename__ = "training_rule_hits"
    __table_args__ = (
        Index("ix_training_rule_hits_evaluation_id", "evaluation_id"),
        Index("ix_training_rule_hits_rule_code", "rule_code"),
        MYSQL_TABLE_ARGS,
    )

    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("training_rule_evaluations.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(96), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    input_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, server_default=text("CURRENT_TIMESTAMP")
    )

    evaluation: Mapped[TrainingRuleEvaluation] = relationship(back_populates="hits")


class TrainingAdjustmentDraft(IdMixin, TimestampMixin, Base):
    __tablename__ = "training_adjustment_drafts"
    __table_args__ = (
        Index("ix_training_adjustment_user_status", "user_id", "status"),
        Index("ix_training_adjustment_user_source", "user_id", "source_type", "source_evaluation_id"),
        Index("ix_training_adjustment_cycle_week", "cycle_id", "week_start"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_evaluation_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_rule_evaluations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    week_start: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft")
    adjustment_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    original_plan_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    applied_result_json: Mapped[dict | None] = mapped_column(JSON)
    facts_hash: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(64))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[UserAccount] = relationship(back_populates="training_adjustment_drafts")
    source_evaluation: Mapped[TrainingRuleEvaluation | None] = relationship()
    cycle: Mapped[TrainingCycle | None] = relationship()


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
