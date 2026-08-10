CREATE DATABASE IF NOT EXISTS `gaitlogic_planner`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `gaitlogic_planner`;

CREATE TABLE IF NOT EXISTS `user_account` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `username` VARCHAR(64) NOT NULL,
  `email` VARCHAR(255) NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `nickname` VARCHAR(64) NULL,
  `avatar_url` VARCHAR(512) NULL,
  `role` VARCHAR(32) NOT NULL DEFAULT 'user',
  `ui_mode` VARCHAR(16) NOT NULL DEFAULT 'simple',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `last_login_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_account_username` (`username`),
  UNIQUE KEY `uq_user_account_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_cycles` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `goal` VARCHAR(255) NULL,
  `start_date` DATE NULL,
  `end_date` DATE NULL,
  `actual_start_date` DATE NULL,
  `actual_end_date` DATE NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'draft',
  `active_user_id` BIGINT NULL,
  `activated_at` DATETIME NULL,
  `completed_at` DATETIME NULL,
  `superseded_by_cycle_id` BIGINT NULL,
  `target_race_name` VARCHAR(128) NULL,
  `target_race_date` DATE NULL,
  `target_result` VARCHAR(64) NULL,
  `description` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_cycles_one_active_per_user` (`active_user_id`),
  KEY `ix_training_cycles_user_id` (`user_id`),
  KEY `ix_training_cycles_user_status` (`user_id`, `status`),
  KEY `ix_training_cycles_superseded_by_cycle_id` (`superseded_by_cycle_id`),
  CONSTRAINT `fk_training_cycles_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_training_cycles_superseded_by_cycle_id`
    FOREIGN KEY (`superseded_by_cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_blocks` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `cycle_id` BIGINT NOT NULL,
  `user_id` BIGINT NOT NULL,
  `block_name` VARCHAR(128) NOT NULL,
  `block_type` VARCHAR(16) NOT NULL DEFAULT 'week',
  `week_index` INT NULL,
  `sort_order` INT NOT NULL,
  `date_range_text` VARCHAR(128) NULL,
  `target_text` TEXT NULL,
  `target_distance_min_km` DECIMAL(7, 2) NULL,
  `target_distance_max_km` DECIMAL(7, 2) NULL,
  `planned_distance_km` DECIMAL(7, 2) NULL,
  `start_date` DATE NULL,
  `end_date` DATE NULL,
  `phase_name` VARCHAR(128) NULL,
  `focus` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_blocks_cycle_sort` (`cycle_id`, `sort_order`),
  KEY `ix_training_blocks_cycle_id` (`cycle_id`),
  KEY `ix_training_blocks_user_id` (`user_id`),
  KEY `ix_training_blocks_start_end` (`start_date`, `end_date`),
  CONSTRAINT `fk_training_blocks_cycle_id`
    FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_training_blocks_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `planned_workouts` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `cycle_id` BIGINT NOT NULL,
  `user_id` BIGINT NOT NULL,
  `block_id` BIGINT NOT NULL,
  `workout_date` DATE NULL,
  `session_index` INT NOT NULL DEFAULT 1,
  `date_text` VARCHAR(64) NULL,
  `weekday` VARCHAR(32) NULL,
  `month_text` VARCHAR(32) NULL,
  `phase_name` VARCHAR(128) NULL,
  `planned_content` TEXT NOT NULL,
  `focus_note` TEXT NULL,
  `target_pace_text` VARCHAR(255) NULL,
  `planned_distance_km` DECIMAL(7, 2) NULL,
  `main_type_raw` VARCHAR(64) NULL,
  `main_type_normalized` VARCHAR(32) NOT NULL DEFAULT 'unknown',
  `source_sheet` VARCHAR(128) NULL,
  `source_row` INT NULL,
  `sort_order` INT NOT NULL,
  `is_locked` TINYINT(1) NOT NULL DEFAULT 0,
  `lock_reason` VARCHAR(255) NULL,
  `plan_version` INT NOT NULL DEFAULT 1,
  `lifecycle_status` VARCHAR(16) NOT NULL DEFAULT 'planned',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_planned_workouts_cycle_date_session` (`cycle_id`, `workout_date`, `session_index`),
  KEY `ix_planned_workouts_cycle_id` (`cycle_id`),
  KEY `ix_planned_workouts_user_id` (`user_id`),
  KEY `ix_planned_workouts_block_id` (`block_id`),
  KEY `ix_planned_workouts_workout_date` (`workout_date`),
  KEY `ix_planned_workouts_main_type_normalized` (`main_type_normalized`),
  KEY `ix_planned_workouts_lifecycle` (`user_id`, `cycle_id`, `lifecycle_status`),
  CONSTRAINT `fk_planned_workouts_cycle_id`
    FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_planned_workouts_block_id`
    FOREIGN KEY (`block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_planned_workouts_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `weekly_review_report` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `cycle_id` BIGINT NOT NULL,
  `source_block_id` BIGINT NOT NULL,
  `target_block_id` BIGINT NULL,
  `week_start_date` DATE NOT NULL,
  `week_end_date` DATE NOT NULL,
  `version` INT NOT NULL DEFAULT 1,
  `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `training_status` VARCHAR(32) NOT NULL DEFAULT 'insufficient_data',
  `metrics_json` JSON NOT NULL,
  `rule_reasons_json` JSON NULL,
  `missing_data_json` JSON NULL,
  `summary` TEXT NULL,
  `positive_points_json` JSON NULL,
  `attention_points_json` JSON NULL,
  `next_week_strategy` TEXT NULL,
  `risk_notes_json` JSON NULL,
  `source_snapshot_json` JSON NOT NULL,
  `snapshot_hash` VARCHAR(64) NOT NULL,
  `algorithm_version` VARCHAR(32) NOT NULL,
  `prompt_version` VARCHAR(32) NULL,
  `model_name` VARCHAR(128) NULL,
  `error_message` TEXT NULL,
  `generated_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_weekly_review_user_cycle_created` (`user_id`, `cycle_id`, `created_at`),
  KEY `ix_weekly_review_user_block_version` (`user_id`, `source_block_id`, `version`),
  KEY `ix_weekly_review_snapshot_hash` (`user_id`, `source_block_id`, `snapshot_hash`),
  KEY `ix_weekly_review_cycle_id` (`cycle_id`),
  KEY `ix_weekly_review_source_block_id` (`source_block_id`),
  KEY `ix_weekly_review_target_block_id` (`target_block_id`),
  CONSTRAINT `fk_weekly_review_user` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_weekly_review_cycle` FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_weekly_review_source_block` FOREIGN KEY (`source_block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_weekly_review_target_block` FOREIGN KEY (`target_block_id`) REFERENCES `training_blocks` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `plan_adjustment_draft` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `review_report_id` BIGINT NULL,
  `cycle_id` BIGINT NOT NULL,
  `source_block_id` BIGINT NULL,
  `target_block_id` BIGINT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'draft',
  `summary` TEXT NULL,
  `original_week_distance_km` DECIMAL(7,2) NULL,
  `suggested_week_distance_km` DECIMAL(7,2) NULL,
  `applied_at` DATETIME NULL,
  `rejected_at` DATETIME NULL,
  `cancelled_at` DATETIME NULL,
  `source_type` VARCHAR(32) NULL,
  `source_name` VARCHAR(128) NULL,
  `source_filename` VARCHAR(255) NULL,
  `raw_payload_hash` VARCHAR(64) NULL,
  `parser_version` VARCHAR(64) NULL,
  `merge_strategy` VARCHAR(64) NULL,
  `anchor_strategy` VARCHAR(64) NULL,
  `effective_date` DATE NULL,
  `target_cycle_id` BIGINT NULL,
  `normalized_payload_json` JSON NULL,
  `diff_summary_json` JSON NULL,
  `conflict_summary_json` JSON NULL,
  `warnings_json` JSON NULL,
  `client_request_id` VARCHAR(128) NULL,
  `expires_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_plan_adjustment_review_report` (`review_report_id`),
  UNIQUE KEY `uq_plan_adjustment_user_client_request` (`user_id`, `client_request_id`),
  KEY `ix_plan_adjustment_user_status` (`user_id`, `status`),
  KEY `ix_plan_adjustment_cycle_id` (`cycle_id`),
  KEY `ix_plan_adjustment_source_block_id` (`source_block_id`),
  KEY `ix_plan_adjustment_target_block_id` (`target_block_id`),
  KEY `ix_plan_adjustment_target_cycle_id` (`target_cycle_id`),
  CONSTRAINT `fk_plan_adjustment_user` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_report` FOREIGN KEY (`review_report_id`) REFERENCES `weekly_review_report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_cycle` FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_source_block` FOREIGN KEY (`source_block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_target_block` FOREIGN KEY (`target_block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_target_cycle` FOREIGN KEY (`target_cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `plan_adjustment_item` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `draft_id` BIGINT NOT NULL,
  `planned_workout_id` BIGINT NULL,
  `action` VARCHAR(16) NOT NULL,
  `operation` VARCHAR(16) NULL,
  `planned_date` DATE NULL,
  `session_index` INT NULL,
  `original_content` TEXT NOT NULL,
  `suggested_content` TEXT NOT NULL,
  `original_distance_km` DECIMAL(7,2) NULL,
  `suggested_distance_km` DECIMAL(7,2) NULL,
  `original_main_type` VARCHAR(32) NULL,
  `suggested_main_type` VARCHAR(32) NULL,
  `original_target_pace_text` VARCHAR(255) NULL,
  `suggested_target_pace_text` VARCHAR(255) NULL,
  `reason` TEXT NOT NULL,
  `normalized_item_json` JSON NULL,
  `conflict_json` JSON NULL,
  `warnings_json` JSON NULL,
  `base_plan_version` INT NULL,
  `base_workout_updated_at` DATETIME NULL,
  `is_selected` TINYINT(1) NOT NULL DEFAULT 0,
  `is_applied` TINYINT(1) NOT NULL DEFAULT 0,
  `applied_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_plan_adjustment_item_draft_workout` (`draft_id`, `planned_workout_id`),
  KEY `ix_plan_adjustment_item_workout_id` (`planned_workout_id`),
  CONSTRAINT `fk_plan_adjustment_item_draft` FOREIGN KEY (`draft_id`) REFERENCES `plan_adjustment_draft` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_adjustment_item_workout` FOREIGN KEY (`planned_workout_id`) REFERENCES `planned_workouts` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `plan_import_audit` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `import_id` BIGINT NOT NULL,
  `source_type` VARCHAR(32) NOT NULL,
  `merge_strategy` VARCHAR(64) NOT NULL,
  `effective_date` DATE NOT NULL,
  `created_count` INT NOT NULL DEFAULT 0,
  `updated_count` INT NOT NULL DEFAULT 0,
  `removed_count` INT NOT NULL DEFAULT 0,
  `protected_count` INT NOT NULL DEFAULT 0,
  `applied_at` DATETIME NOT NULL,
  `actor_type` VARCHAR(32) NOT NULL DEFAULT 'user',
  `client_request_id` VARCHAR(128) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_plan_import_audit_user_created` (`user_id`, `created_at`),
  KEY `ix_plan_import_audit_import_id` (`import_id`),
  CONSTRAINT `fk_plan_import_audit_user` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_plan_import_audit_import` FOREIGN KEY (`import_id`) REFERENCES `plan_adjustment_draft` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_import_batch` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `source_type` VARCHAR(32) NOT NULL,
  `source_filename` VARCHAR(255) NULL,
  `parser_version` VARCHAR(32) NULL,
  `normalization_version` VARCHAR(32) NULL,
  `raw_payload_hash` VARCHAR(64) NULL,
  `merge_strategy` VARCHAR(64) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'ready',
  `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `total_count` INT NOT NULL DEFAULT 0,
  `matched_plan_count` INT NOT NULL DEFAULT 0,
  `matched_log_count` INT NOT NULL DEFAULT 0,
  `unplanned_count` INT NOT NULL DEFAULT 0,
  `ready_count` INT NOT NULL DEFAULT 0,
  `conflict_count` INT NOT NULL DEFAULT 0,
  `invalid_count` INT NOT NULL DEFAULT 0,
  `skipped_count` INT NOT NULL DEFAULT 0,
  `client_request_id` VARCHAR(128) NULL,
  `warnings_json` JSON NULL,
  `preview_summary_json` JSON NULL,
  `expires_at` DATETIME NULL,
  `applied_at` DATETIME NULL,
  `cancelled_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workout_import_user_client_request` (`user_id`, `client_request_id`),
  KEY `ix_workout_import_batch_user_status` (`user_id`, `status`),
  CONSTRAINT `fk_workout_import_batch_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `planned_workout_id` BIGINT NULL,
  `cycle_id` BIGINT NULL,
  `user_id` BIGINT NOT NULL,
  `status_raw` VARCHAR(64) NULL,
  `status_normalized` VARCHAR(32) NOT NULL DEFAULT 'not_started',
  `actual_distance_km` DECIMAL(7, 2) NULL,
  `actual_duration_seconds` INT NULL,
  `moving_time_seconds` INT NULL,
  `elapsed_time_seconds` INT NULL,
  `avg_pace_seconds_per_km` INT NULL,
  `avg_heart_rate` INT NULL,
  `max_heart_rate` INT NULL,
  `average_cadence_spm` INT NULL,
  `max_cadence_spm` INT NULL,
  `elevation_gain_m` INT NULL,
  `calories_kcal` INT NULL,
  `rpe` INT NULL,
  `i_effective_km` DECIMAL(7, 2) NULL,
  `t1_effective_km` DECIMAL(7, 2) NULL,
  `t2_effective_km` DECIMAL(7, 2) NULL,
  `m_effective_km` DECIMAL(7, 2) NULL,
  `r_effective_km` DECIMAL(7, 2) NULL,
  `sleep_hours` DECIMAL(4, 2) NULL,
  `hrv` INT NULL,
  `morning_heart_rate` INT NULL,
  `weight_kg` DECIMAL(5, 2) NULL,
  `leg_feeling` VARCHAR(128) NULL,
  `pain_location` VARCHAR(128) NULL,
  `pain_level` INT NULL,
  `pain_scale_version` VARCHAR(32) NOT NULL DEFAULT 'native_0_10',
  `main_session_data` TEXT NULL,
  `review_note` TEXT NULL,
  `tomorrow_adjustment` TEXT NULL,
  `alert_message` TEXT NULL,
  `completion_rate` DECIMAL(5, 2) NULL,
  `activity_date` DATE NULL,
  `start_time` TIME NULL,
  `timezone` VARCHAR(64) NULL,
  `session_index` INT NOT NULL DEFAULT 1,
  `sport_type` VARCHAR(32) NOT NULL DEFAULT 'running',
  `workout_type` VARCHAR(32) NULL,
  `title` VARCHAR(128) NULL,
  `is_unplanned` TINYINT(1) NOT NULL DEFAULT 0,
  `source_type` VARCHAR(32) NOT NULL DEFAULT 'manual',
  `source_import_batch_id` BIGINT NULL,
  `external_activity_id` VARCHAR(128) NULL,
  `activity_fingerprint` VARCHAR(64) NULL,
  `field_sources_json` JSON NULL,
  `subjective_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `cycle_assignment_status` VARCHAR(32) NOT NULL DEFAULT 'assigned',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workout_logs_planned_workout` (`planned_workout_id`),
  KEY `ix_workout_logs_planned_workout_id` (`planned_workout_id`),
  KEY `ix_workout_logs_cycle_id` (`cycle_id`),
  KEY `ix_workout_logs_user_id` (`user_id`),
  KEY `ix_workout_logs_user_cycle_date` (`user_id`, `cycle_id`, `activity_date`),
  KEY `ix_workout_logs_user_activity_date` (`user_id`, `activity_date`, `session_index`),
  KEY `ix_workout_logs_activity_fingerprint` (`user_id`, `activity_fingerprint`),
  KEY `ix_workout_logs_source_import_batch_id` (`source_import_batch_id`),
  KEY `ix_workout_logs_status_normalized` (`status_normalized`),
  CONSTRAINT `fk_workout_logs_planned_workout_id`
    FOREIGN KEY (`planned_workout_id`) REFERENCES `planned_workouts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_workout_logs_cycle_id`
    FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_workout_logs_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_logs_source_import_batch_id`
    FOREIGN KEY (`source_import_batch_id`) REFERENCES `workout_import_batch` (`id`) ON DELETE SET NULL,
  CONSTRAINT `ck_workout_logs_pain_level_range`
    CHECK (`pain_level` IS NULL OR (`pain_level` >= 0 AND `pain_level` <= 10))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_import_item` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `batch_id` BIGINT NOT NULL,
  `row_number` INT NULL,
  `activity_date` DATE NULL,
  `start_time` TIME NULL,
  `session_index` INT NULL,
  `normalized_data_json` JSON NULL,
  `matched_plan_id` BIGINT NULL,
  `matched_log_id` BIGINT NULL,
  `applied_log_id` BIGINT NULL,
  `match_status` VARCHAR(32) NOT NULL DEFAULT 'invalid',
  `match_confidence` VARCHAR(16) NULL,
  `suggested_action` VARCHAR(32) NOT NULL DEFAULT 'manual_review',
  `user_action` VARCHAR(32) NULL,
  `validation_errors_json` JSON NULL,
  `warnings_json` JSON NULL,
  `field_diff_json` JSON NULL,
  `activity_fingerprint` VARCHAR(64) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_workout_import_item_batch_id` (`batch_id`),
  KEY `ix_workout_import_item_batch_date` (`batch_id`, `activity_date`, `session_index`),
  KEY `ix_workout_import_item_matched_plan_id` (`matched_plan_id`),
  KEY `ix_workout_import_item_matched_log_id` (`matched_log_id`),
  KEY `ix_workout_import_item_applied_log_id` (`applied_log_id`),
  CONSTRAINT `fk_workout_import_item_batch_id`
    FOREIGN KEY (`batch_id`) REFERENCES `workout_import_batch` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_import_item_matched_plan_id`
    FOREIGN KEY (`matched_plan_id`) REFERENCES `planned_workouts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_workout_import_item_matched_log_id`
    FOREIGN KEY (`matched_log_id`) REFERENCES `workout_logs` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_workout_import_item_applied_log_id`
    FOREIGN KEY (`applied_log_id`) REFERENCES `workout_logs` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_import_audit` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `batch_id` BIGINT NOT NULL,
  `source_type` VARCHAR(32) NULL,
  `merge_strategy` VARCHAR(64) NULL,
  `total_count` INT NOT NULL DEFAULT 0,
  `created_count` INT NOT NULL DEFAULT 0,
  `updated_count` INT NOT NULL DEFAULT 0,
  `linked_plan_count` INT NOT NULL DEFAULT 0,
  `unplanned_count` INT NOT NULL DEFAULT 0,
  `skipped_count` INT NOT NULL DEFAULT 0,
  `conflict_count` INT NOT NULL DEFAULT 0,
  `applied_at` DATETIME NULL,
  `actor_type` VARCHAR(32) NOT NULL DEFAULT 'user',
  `client_request_id` VARCHAR(128) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workout_import_audit_batch` (`batch_id`),
  KEY `ix_workout_import_audit_user_created` (`user_id`, `created_at`),
  CONSTRAINT `fk_workout_import_audit_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_import_audit_batch_id`
    FOREIGN KEY (`batch_id`) REFERENCES `workout_import_batch` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `block_reviews` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `block_id` BIGINT NOT NULL,
  `user_id` BIGINT NOT NULL,
  `planned_distance_km` DECIMAL(7, 2) NULL,
  `actual_distance_km` DECIMAL(7, 2) NULL,
  `completion_rate` DECIMAL(5, 2) NULL,
  `i_effective_km` DECIMAL(7, 2) NULL,
  `t1_effective_km` DECIMAL(7, 2) NULL,
  `t2_effective_km` DECIMAL(7, 2) NULL,
  `m_effective_km` DECIMAL(7, 2) NULL,
  `r_effective_km` DECIMAL(7, 2) NULL,
  `avg_rpe` DECIMAL(4, 2) NULL,
  `avg_weight_kg` DECIMAL(5, 2) NULL,
  `max_pain_level` INT NULL,
  `review_text` TEXT NULL,
  `next_block_adjustment` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_block_reviews_block` (`block_id`),
  KEY `ix_block_reviews_block_id` (`block_id`),
  KEY `ix_block_reviews_user_id` (`user_id`),
  CONSTRAINT `fk_block_reviews_block_id`
    FOREIGN KEY (`block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_block_reviews_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ck_block_reviews_max_pain_level_range`
    CHECK (`max_pain_level` IS NULL OR (`max_pain_level` >= 0 AND `max_pain_level` <= 10))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `pace_rules` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `code` VARCHAR(16) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `target_pace_text` VARCHAR(255) NULL,
  `physiological_purpose` TEXT NULL,
  `note` TEXT NULL,
  `sort_order` INT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pace_rules_user_code` (`user_id`, `code`),
  KEY `ix_pace_rules_user_id` (`user_id`),
  CONSTRAINT `fk_pace_rules_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `pace_profile` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `race_distance` VARCHAR(32) NOT NULL,
  `race_result_seconds` INT NOT NULL,
  `vdot` DECIMAL(5, 1) NOT NULL,
  `algorithm_version` VARCHAR(32) NOT NULL DEFAULT 'approx_vdot_v1',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_pace_profile_user_id` (`user_id`),
  KEY `ix_pace_profile_user_created` (`user_id`, `created_at`),
  CONSTRAINT `fk_pace_profile_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `pace_zone` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `pace_profile_id` BIGINT NOT NULL,
  `zone_code` VARCHAR(16) NOT NULL,
  `zone_name` VARCHAR(64) NOT NULL,
  `pace_min_seconds_per_km` INT NOT NULL,
  `pace_max_seconds_per_km` INT NOT NULL,
  `target_pace_text` VARCHAR(64) NOT NULL,
  `description` TEXT NULL,
  `sort_order` INT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pace_zone_profile_code` (`pace_profile_id`, `zone_code`),
  KEY `ix_pace_zone_pace_profile_id` (`pace_profile_id`),
  CONSTRAINT `fk_pace_zone_pace_profile_id`
    FOREIGN KEY (`pace_profile_id`) REFERENCES `pace_profile` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `feedback` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `feedback_type` VARCHAR(32) NOT NULL,
  `page_url` VARCHAR(512) NULL,
  `content` TEXT NOT NULL,
  `contact` VARCHAR(255) NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'open',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_feedback_user_id` (`user_id`),
  KEY `ix_feedback_user_created` (`user_id`, `created_at`),
  CONSTRAINT `fk_feedback_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_plan_job` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'pending',
  `model_name` VARCHAR(64) NOT NULL,
  `prompt_hash` VARCHAR(64) NOT NULL,
  `input_json` JSON NOT NULL,
  `output_json` JSON NULL,
  `error_message` TEXT NULL,
  `input_tokens` INT NULL,
  `output_tokens` INT NULL,
  `total_tokens` INT NULL,
  `finished_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ai_plan_job_user_id` (`user_id`),
  KEY `ix_ai_plan_job_user_prompt` (`user_id`, `prompt_hash`),
  CONSTRAINT `fk_ai_plan_job_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_plan_quota` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `quota_date` DATE NOT NULL,
  `daily_limit` INT NOT NULL,
  `used_count` INT NOT NULL DEFAULT 0,
  `last_generated_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_plan_quota_user_date` (`user_id`, `quota_date`),
  KEY `ix_ai_plan_quota_user_id` (`user_id`),
  CONSTRAINT `fk_ai_plan_quota_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `admin_ai_settings` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `deepseek_base_url` VARCHAR(255) NOT NULL DEFAULT 'https://api.deepseek.com',
  `deepseek_model` VARCHAR(128) NOT NULL DEFAULT 'deepseek-v4-flash',
  `deepseek_api_key` VARCHAR(512) NULL,
  `deepseek_timeout_seconds` INT NOT NULL DEFAULT 120,
  `ai_plan_daily_limit` INT NOT NULL DEFAULT 3,
  `ai_plan_cooldown_seconds` INT NOT NULL DEFAULT 60,
  `temperature` DECIMAL(3, 2) NOT NULL DEFAULT 0.40,
  `top_p` DECIMAL(3, 2) NOT NULL DEFAULT 0.90,
  `max_tokens_per_week` INT NOT NULL DEFAULT 1600,
  `max_tokens_cap` INT NOT NULL DEFAULT 24000,
  `updated_by_id` BIGINT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_admin_ai_settings_updated_by_id` (`updated_by_id`),
  CONSTRAINT `fk_admin_ai_settings_updated_by_id`
    FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `admin_system_settings` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `auth_entry_mode` VARCHAR(32) NOT NULL DEFAULT 'standalone',
  `allow_public_registration` TINYINT(1) NOT NULL DEFAULT 1,
  `updated_by_id` BIGINT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_admin_system_settings_updated_by_id` (`updated_by_id`),
  CONSTRAINT `fk_admin_system_settings_updated_by_id`
    FOREIGN KEY (`updated_by_id`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_coach_preference` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `preferred_training_systems` JSON NULL,
  `intensity_conservatism` VARCHAR(32) NOT NULL DEFAULT 'standard',
  `key_workout_habit` TEXT NULL,
  `rest_day_strategy` TEXT NULL,
  `disabled_workout_types` JSON NULL,
  `double_run_policy` VARCHAR(32) NOT NULL DEFAULT 'cautious',
  `long_run_strategy` TEXT NULL,
  `injury_risk_policy` TEXT NULL,
  `additional_notes` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_coach_preference_user` (`user_id`),
  KEY `ix_ai_coach_preference_user_id` (`user_id`),
  CONSTRAINT `fk_ai_coach_preference_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_plan_draft` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `job_id` BIGINT NOT NULL,
  `title` VARCHAR(128) NOT NULL,
  `goal` VARCHAR(255) NULL,
  `start_date` DATE NULL,
  `end_date` DATE NULL,
  `target_race_name` VARCHAR(128) NULL,
  `target_race_date` DATE NULL,
  `target_result` VARCHAR(64) NULL,
  `summary` TEXT NULL,
  `risk_notes` JSON NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'draft',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ai_plan_draft_job_id` (`job_id`),
  KEY `ix_ai_plan_draft_user_id` (`user_id`),
  KEY `ix_ai_plan_draft_user_status` (`user_id`, `status`),
  CONSTRAINT `fk_ai_plan_draft_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ai_plan_draft_job_id`
    FOREIGN KEY (`job_id`) REFERENCES `ai_plan_job` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `ai_plan_draft_workout` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `draft_id` BIGINT NOT NULL,
  `workout_date` DATE NOT NULL,
  `weekday` VARCHAR(32) NULL,
  `block_name` VARCHAR(128) NULL,
  `phase_name` VARCHAR(128) NULL,
  `planned_content` TEXT NOT NULL,
  `focus_note` TEXT NULL,
  `planned_distance_km` DECIMAL(7, 2) NULL,
  `main_type_raw` VARCHAR(64) NULL,
  `main_type_normalized` VARCHAR(32) NOT NULL DEFAULT 'unknown',
  `target_pace_text` VARCHAR(255) NULL,
  `sort_order` INT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_ai_plan_draft_workout_draft_id` (`draft_id`),
  KEY `ix_ai_plan_draft_workout_date` (`workout_date`),
  CONSTRAINT `fk_ai_plan_draft_workout_draft_id`
    FOREIGN KEY (`draft_id`) REFERENCES `ai_plan_draft` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `excel_import_jobs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `file_name` VARCHAR(255) NOT NULL,
  `file_path` VARCHAR(512) NULL,
  `file_hash` VARCHAR(128) NULL,
  `sheet_names` JSON NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `total_count` INT NOT NULL DEFAULT 0,
  `success_count` INT NOT NULL DEFAULT 0,
  `failed_count` INT NOT NULL DEFAULT 0,
  `error_message` TEXT NULL,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_excel_import_jobs_user_id` (`user_id`),
  KEY `ix_excel_import_jobs_file_hash` (`file_hash`),
  CONSTRAINT `fk_excel_import_jobs_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `feature_access` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `feature_key` VARCHAR(64) NOT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `granted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `granted_by` BIGINT NULL,
  `expires_at` DATETIME NULL,
  `notes` VARCHAR(255) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_feature_access_user_feature` (`user_id`, `feature_key`),
  KEY `ix_feature_access_user_id` (`user_id`),
  KEY `ix_feature_access_granted_by` (`granted_by`),
  KEY `ix_feature_access_feature_enabled` (`feature_key`, `enabled`),
  CONSTRAINT `fk_feature_access_user`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_feature_access_granted_by`
    FOREIGN KEY (`granted_by`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `daily_recovery_checkin` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `checkin_date` DATE NOT NULL,
  `sleep_duration_minutes` INT NULL,
  `sleep_quality` INT NULL,
  `subjective_fatigue` INT NULL,
  `muscle_soreness` INT NULL,
  `stress_level` INT NULL,
  `mood_level` INT NULL,
  `leg_feeling` INT NULL,
  `resting_heart_rate_bpm` INT NULL,
  `hrv_value` DECIMAL(8, 2) NULL,
  `hrv_metric` VARCHAR(32) NULL,
  `hrv_source` VARCHAR(64) NULL,
  `pain_level` INT NULL,
  `pain_location` VARCHAR(128) NULL,
  `pain_trend` VARCHAR(16) NOT NULL DEFAULT 'unknown',
  `pain_affects_gait` TINYINT(1) NULL,
  `illness_symptoms` VARCHAR(255) NULL,
  `notes` TEXT NULL,
  `source` VARCHAR(16) NOT NULL DEFAULT 'manual',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_daily_recovery_user_date` (`user_id`, `checkin_date`),
  KEY `ix_daily_recovery_user_id` (`user_id`),
  KEY `ix_daily_recovery_user_date` (`user_id`, `checkin_date`),
  CONSTRAINT `fk_daily_recovery_user`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ck_daily_recovery_sleep_quality`
    CHECK (`sleep_quality` IS NULL OR (`sleep_quality` >= 1 AND `sleep_quality` <= 5)),
  CONSTRAINT `ck_daily_recovery_subjective_fatigue`
    CHECK (`subjective_fatigue` IS NULL OR (`subjective_fatigue` >= 1 AND `subjective_fatigue` <= 5)),
  CONSTRAINT `ck_daily_recovery_muscle_soreness`
    CHECK (`muscle_soreness` IS NULL OR (`muscle_soreness` >= 1 AND `muscle_soreness` <= 5)),
  CONSTRAINT `ck_daily_recovery_stress_level`
    CHECK (`stress_level` IS NULL OR (`stress_level` >= 1 AND `stress_level` <= 5)),
  CONSTRAINT `ck_daily_recovery_mood_level`
    CHECK (`mood_level` IS NULL OR (`mood_level` >= 1 AND `mood_level` <= 5)),
  CONSTRAINT `ck_daily_recovery_leg_feeling`
    CHECK (`leg_feeling` IS NULL OR (`leg_feeling` >= 1 AND `leg_feeling` <= 5)),
  CONSTRAINT `ck_daily_recovery_pain_level`
    CHECK (`pain_level` IS NULL OR (`pain_level` >= 0 AND `pain_level` <= 10))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_readiness_assessment` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `assessment_date` DATE NOT NULL,
  `status` VARCHAR(32) NOT NULL,
  `data_quality` VARCHAR(16) NOT NULL,
  `metrics_json` JSON NOT NULL,
  `external_load_signals_json` JSON NULL,
  `internal_load_signals_json` JSON NULL,
  `recovery_signals_json` JSON NULL,
  `performance_signals_json` JSON NULL,
  `pain_signals_json` JSON NULL,
  `reasons_json` JSON NOT NULL,
  `recommendations_json` JSON NOT NULL,
  `missing_data_json` JSON NULL,
  `source_snapshot_json` JSON NOT NULL,
  `algorithm_version` VARCHAR(32) NOT NULL,
  `threshold_version` VARCHAR(32) NOT NULL,
  `generated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_readiness_user_id` (`user_id`),
  KEY `ix_readiness_user_date_created` (`user_id`, `assessment_date`, `created_at`),
  KEY `ix_readiness_user_status` (`user_id`, `status`),
  CONSTRAINT `fk_readiness_user`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `usage_event` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NULL,
  `event_name` VARCHAR(64) NOT NULL,
  `page_path` VARCHAR(255) NULL,
  `metadata_json` JSON NULL,
  `occurred_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_usage_event_user_id` (`user_id`),
  KEY `ix_usage_event_user_occurred` (`user_id`, `occurred_at`),
  KEY `ix_usage_event_event_occurred` (`event_name`, `occurred_at`),
  CONSTRAINT `fk_usage_event_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_account_connection` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `provider` VARCHAR(32) NOT NULL DEFAULT 'garmin',
  `region` VARCHAR(32) NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'connected',
  `masked_account_identifier` VARCHAR(255) NULL,
  `account_identifier_hash` VARCHAR(64) NULL,
  `active_user_provider_key` VARCHAR(128) NULL,
  `active_account_key` VARCHAR(128) NULL,
  `encrypted_token_payload` TEXT NULL,
  `token_key_version` VARCHAR(32) NULL,
  `connector_version` VARCHAR(32) NULL,
  `auto_import_enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `auto_sync_enabled` TINYINT(1) NOT NULL DEFAULT 0,
  `auto_sync_last_run_at` DATETIME NULL,
  `last_authenticated_at` DATETIME NULL,
  `last_successful_sync_at` DATETIME NULL,
  `sync_cursor` VARCHAR(512) NULL,
  `last_error_code` VARCHAR(64) NULL,
  `last_error_at` DATETIME NULL,
  `disconnected_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_external_connection_active_user_provider` (`active_user_provider_key`),
  UNIQUE KEY `uq_external_connection_active_account` (`active_account_key`),
  KEY `ix_external_connection_user_provider` (`user_id`, `provider`, `status`),
  CONSTRAINT `fk_external_connection_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_sync_job` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `connection_id` BIGINT NOT NULL,
  `provider` VARCHAR(32) NOT NULL DEFAULT 'garmin',
  `sync_mode` VARCHAR(32) NOT NULL,
  `requested_start` DATETIME NULL,
  `requested_end` DATETIME NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'queued',
  `idempotency_key` VARCHAR(128) NULL,
  `sync_run_id` VARCHAR(36) NOT NULL,
  `attempt_count` INT NOT NULL DEFAULT 0,
  `fetched_count` INT NOT NULL DEFAULT 0,
  `created_count` INT NOT NULL DEFAULT 0,
  `updated_count` INT NOT NULL DEFAULT 0,
  `duplicate_count` INT NOT NULL DEFAULT 0,
  `matched_count` INT NOT NULL DEFAULT 0,
  `unplanned_count` INT NOT NULL DEFAULT 0,
  `needs_review_count` INT NOT NULL DEFAULT 0,
  `ignored_count` INT NOT NULL DEFAULT 0,
  `failed_count` INT NOT NULL DEFAULT 0,
  `is_committed` TINYINT(1) NOT NULL DEFAULT 0,
  `committed_at` DATETIME NULL,
  `created_log_count` INT NOT NULL DEFAULT 0,
  `updated_log_count` INT NOT NULL DEFAULT 0,
  `unchanged_activity_count` INT NOT NULL DEFAULT 0,
  `runner_state_affecting_change_count` INT NOT NULL DEFAULT 0,
  `started_at` DATETIME NULL,
  `finished_at` DATETIME NULL,
  `error_code` VARCHAR(64) NULL,
  `safe_error_message` VARCHAR(255) NULL,
  `locked_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_external_sync_job_idempotency` (`connection_id`, `idempotency_key`),
  KEY `ix_external_sync_job_status_created` (`status`, `created_at`),
  KEY `ix_external_sync_job_user_created` (`user_id`, `created_at`),
  KEY `ix_external_sync_job_sync_run_id` (`sync_run_id`),
  KEY `ix_external_sync_job_connection_id` (`connection_id`),
  CONSTRAINT `fk_external_sync_job_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_sync_job_connection_id`
    FOREIGN KEY (`connection_id`) REFERENCES `external_account_connection` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_activity_raw` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `connection_id` BIGINT NOT NULL,
  `sync_job_id` BIGINT NULL,
  `provider` VARCHAR(32) NOT NULL DEFAULT 'garmin',
  `external_activity_id` VARCHAR(128) NOT NULL,
  `payload_hash` VARCHAR(64) NOT NULL,
  `raw_payload_json` JSON NULL,
  `fetched_at` DATETIME NOT NULL,
  `expires_at` DATETIME NULL,
  `desensitization_version` VARCHAR(32) NOT NULL DEFAULT 'garmin-raw-v1',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_external_raw_payload` (`provider`, `external_activity_id`, `payload_hash`),
  KEY `ix_external_raw_user_expires` (`user_id`, `expires_at`),
  KEY `ix_external_raw_connection_id` (`connection_id`),
  KEY `ix_external_raw_sync_job_id` (`sync_job_id`),
  CONSTRAINT `fk_external_raw_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_raw_connection_id`
    FOREIGN KEY (`connection_id`) REFERENCES `external_account_connection` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_raw_sync_job_id`
    FOREIGN KEY (`sync_job_id`) REFERENCES `external_sync_job` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_activity` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `connection_id` BIGINT NOT NULL,
  `sync_job_id` BIGINT NULL,
  `raw_activity_id` BIGINT NULL,
  `provider` VARCHAR(32) NOT NULL DEFAULT 'garmin',
  `external_activity_id` VARCHAR(128) NOT NULL,
  `connector_version` VARCHAR(32) NOT NULL,
  `normalization_version` VARCHAR(32) NOT NULL DEFAULT 'garmin-activity-v1',
  `segmentation_version` VARCHAR(64) NULL,
  `classification_version` VARCHAR(64) NULL,
  `payload_hash` VARCHAR(64) NULL,
  `source_updated_at` DATETIME NULL,
  `fetched_at` DATETIME NULL,
  `activity_name` VARCHAR(255) NULL,
  `activity_type` VARCHAR(64) NOT NULL,
  `activity_subtype` VARCHAR(64) NULL,
  `start_time_utc` DATETIME NULL,
  `start_time_local` DATETIME NOT NULL,
  `timezone` VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
  `activity_date` DATE NOT NULL,
  `source_deleted` TINYINT(1) NOT NULL DEFAULT 0,
  `processing_status` VARCHAR(32) NOT NULL DEFAULT 'synced',
  `resolution_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `apply_status` VARCHAR(32) NOT NULL DEFAULT 'not_applied',
  `composite_session_key` VARCHAR(128) NULL,
  `match_confidence` VARCHAR(16) NULL,
  `planned_workout_id` BIGINT NULL,
  `workout_log_id` BIGINT NULL,
  `distance_m` DECIMAL(10, 2) NULL,
  `duration_seconds` INT NULL,
  `timer_time_seconds` INT NULL,
  `moving_time_seconds` INT NULL,
  `elapsed_time_seconds` INT NULL,
  `average_speed_mps` DECIMAL(8, 3) NULL,
  `average_pace_seconds_per_km` INT NULL,
  `max_speed_mps` DECIMAL(8, 3) NULL,
  `best_pace_seconds_per_km` INT NULL,
  `average_heart_rate_bpm` INT NULL,
  `max_heart_rate_bpm` INT NULL,
  `min_heart_rate_bpm` INT NULL,
  `average_cadence_spm` INT NULL,
  `max_cadence_spm` INT NULL,
  `cadence_normalization_method` VARCHAR(64) NULL,
  `elevation_gain_m` INT NULL,
  `elevation_loss_m` INT NULL,
  `calories_kcal` INT NULL,
  `average_stride_length_m` DECIMAL(6, 3) NULL,
  `average_vertical_ratio_percent` DECIMAL(5, 2) NULL,
  `average_vertical_oscillation_cm` DECIMAL(5, 2) NULL,
  `average_ground_contact_time_ms` INT NULL,
  `ground_contact_balance_percent` DECIMAL(5, 2) NULL,
  `average_running_power_w` INT NULL,
  `max_running_power_w` INT NULL,
  `garmin_primary_benefit` VARCHAR(128) NULL,
  `garmin_aerobic_training_effect` DECIMAL(4, 2) NULL,
  `garmin_anaerobic_training_effect` DECIMAL(4, 2) NULL,
  `garmin_training_load` DECIMAL(8, 2) NULL,
  `garmin_recovery_time_seconds` INT NULL,
  `high_intensity_distance_m` DECIMAL(10, 2) NULL,
  `data_quality` VARCHAR(32) NOT NULL DEFAULT 'valid',
  `quality_warnings_json` JSON NULL,
  `field_sources_json` JSON NULL,
  `ignored_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_external_activity_provider_id` (`provider`, `external_activity_id`),
  KEY `ix_external_activity_user_date` (`user_id`, `activity_date`, `processing_status`),
  KEY `ix_external_activity_user_status` (`user_id`, `processing_status`),
  KEY `ix_external_activity_connection_id` (`connection_id`),
  KEY `ix_external_activity_sync_job_id` (`sync_job_id`),
  KEY `ix_external_activity_raw_activity_id` (`raw_activity_id`),
  KEY `ix_external_activity_planned_workout_id` (`planned_workout_id`),
  KEY `ix_external_activity_workout_log_id` (`workout_log_id`),
  CONSTRAINT `fk_external_activity_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_activity_connection_id`
    FOREIGN KEY (`connection_id`) REFERENCES `external_account_connection` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_activity_sync_job_id`
    FOREIGN KEY (`sync_job_id`) REFERENCES `external_sync_job` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_external_activity_raw_activity_id`
    FOREIGN KEY (`raw_activity_id`) REFERENCES `external_activity_raw` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_external_activity_planned_workout_id`
    FOREIGN KEY (`planned_workout_id`) REFERENCES `planned_workouts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_external_activity_workout_log_id`
    FOREIGN KEY (`workout_log_id`) REFERENCES `workout_logs` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_activity_lap` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `external_activity_id` BIGINT NOT NULL,
  `lap_index` INT NOT NULL,
  `external_lap_id` VARCHAR(128) NULL,
  `start_time` DATETIME NULL,
  `start_offset_seconds` INT NULL,
  `distance_m` DECIMAL(10, 2) NULL,
  `duration_seconds` INT NULL,
  `timer_time_seconds` INT NULL,
  `moving_time_seconds` INT NULL,
  `average_speed_mps` DECIMAL(8, 3) NULL,
  `average_pace_seconds_per_km` INT NULL,
  `average_heart_rate_bpm` INT NULL,
  `max_heart_rate_bpm` INT NULL,
  `average_cadence_spm` INT NULL,
  `elevation_gain_m` INT NULL,
  `lap_type` VARCHAR(64) NULL,
  `workout_step_type` VARCHAR(64) NULL,
  `segment_role` VARCHAR(32) NOT NULL DEFAULT 'unknown',
  `classification_source` VARCHAR(64) NOT NULL DEFAULT 'unknown',
  `classification_confidence` VARCHAR(16) NOT NULL DEFAULT 'low',
  `data_quality` VARCHAR(32) NOT NULL DEFAULT 'valid',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_external_activity_lap_index` (`external_activity_id`, `lap_index`),
  CONSTRAINT `fk_external_activity_lap_external_activity_id`
    FOREIGN KEY (`external_activity_id`) REFERENCES `external_activity` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_log_external_activity` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `workout_log_id` BIGINT NOT NULL,
  `external_activity_id` BIGINT NOT NULL,
  `link_type` VARCHAR(32) NOT NULL DEFAULT 'matched',
  `match_confidence` VARCHAR(16) NULL,
  `resolution_status` VARCHAR(32) NOT NULL DEFAULT 'auto_applied',
  `field_sources_json` JSON NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workout_log_external_activity` (`workout_log_id`, `external_activity_id`),
  UNIQUE KEY `uq_workout_log_external_single_activity` (`external_activity_id`),
  KEY `ix_workout_log_external_user` (`user_id`, `workout_log_id`),
  KEY `ix_workout_log_external_external_activity_id` (`external_activity_id`),
  CONSTRAINT `fk_workout_log_external_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_log_external_workout_log_id`
    FOREIGN KEY (`workout_log_id`) REFERENCES `workout_logs` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_log_external_external_activity_id`
    FOREIGN KEY (`external_activity_id`) REFERENCES `external_activity` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `external_activity_resolution` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `external_activity_id` BIGINT NOT NULL,
  `workout_log_id` BIGINT NULL,
  `action` VARCHAR(32) NOT NULL,
  `previous_state_json` JSON NULL,
  `new_state_json` JSON NULL,
  `reason` VARCHAR(255) NULL,
  `actor_type` VARCHAR(32) NOT NULL DEFAULT 'user',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_external_activity_resolution_user_created` (`user_id`, `created_at`),
  KEY `ix_external_activity_resolution_external_activity_id` (`external_activity_id`),
  KEY `ix_external_activity_resolution_workout_log_id` (`workout_log_id`),
  CONSTRAINT `fk_external_activity_resolution_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_activity_resolution_external_activity_id`
    FOREIGN KEY (`external_activity_id`) REFERENCES `external_activity` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_external_activity_resolution_workout_log_id`
    FOREIGN KEY (`workout_log_id`) REFERENCES `workout_logs` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_knowledge_items` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(96) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `english_name` VARCHAR(128) NULL,
  `category` VARCHAR(64) NOT NULL,
  `definition` TEXT NOT NULL,
  `aliases_json` JSON NOT NULL,
  `attributes_json` JSON NOT NULL,
  `related_codes_json` JSON NOT NULL,
  `source_refs_json` JSON NOT NULL,
  `evidence_level` VARCHAR(64) NOT NULL DEFAULT 'product_rule',
  `version` VARCHAR(32) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_knowledge_items_code` (`code`),
  KEY `ix_training_knowledge_items_category_status` (`category`, `status`),
  KEY `ix_training_knowledge_items_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_evidence_sources` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(96) NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `authors` TEXT NULL,
  `publication_year` INT NULL,
  `source_type` VARCHAR(64) NOT NULL,
  `publication_name` VARCHAR(255) NULL,
  `doi` VARCHAR(255) NULL,
  `url` VARCHAR(512) NULL,
  `language` VARCHAR(32) NULL,
  `summary` TEXT NOT NULL,
  `evidence_level` VARCHAR(64) NOT NULL,
  `review_status` VARCHAR(32) NOT NULL DEFAULT 'draft',
  `copyright_note` TEXT NULL,
  `metadata_json` JSON NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_evidence_sources_code` (`code`),
  KEY `ix_training_evidence_type_level` (`source_type`, `evidence_level`),
  KEY `ix_training_evidence_review_status` (`review_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_versions` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `rule_code` VARCHAR(96) NOT NULL,
  `version` VARCHAR(32) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `category` VARCHAR(64) NOT NULL,
  `scope` VARCHAR(64) NOT NULL,
  `conditions_json` JSON NOT NULL,
  `result_json` JSON NOT NULL,
  `applicability_json` JSON NOT NULL,
  `thresholds_json` JSON NOT NULL,
  `explanation_template` TEXT NOT NULL,
  `severity` VARCHAR(32) NOT NULL,
  `priority` INT NOT NULL DEFAULT 0,
  `source_type` VARCHAR(64) NOT NULL,
  `lifecycle_status` VARCHAR(32) NOT NULL DEFAULT 'draft',
  `content_hash` VARCHAR(64) NOT NULL,
  `change_summary` TEXT NULL,
  `created_by` BIGINT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `published_at` DATETIME NULL,
  `retired_at` DATETIME NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_rule_versions_code_version` (`rule_code`, `version`),
  KEY `ix_training_rule_versions_code_status` (`rule_code`, `lifecycle_status`),
  KEY `ix_training_rule_versions_scope_status` (`scope`, `lifecycle_status`),
  KEY `ix_training_rule_versions_content_hash` (`content_hash`),
  KEY `ix_training_rule_versions_created_by` (`created_by`),
  CONSTRAINT `fk_training_rule_versions_created_by`
    FOREIGN KEY (`created_by`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rules` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(96) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `category` VARCHAR(64) NOT NULL,
  `scope` VARCHAR(64) NOT NULL DEFAULT 'generic',
  `conditions_json` JSON NOT NULL,
  `result_json` JSON NOT NULL,
  `explanation_template` TEXT NOT NULL,
  `severity` VARCHAR(32) NOT NULL DEFAULT 'info',
  `priority` INT NOT NULL DEFAULT 0,
  `evidence_refs_json` JSON NOT NULL,
  `version` VARCHAR(32) NOT NULL,
  `current_version` VARCHAR(32) NULL,
  `lifecycle_status` VARCHAR(32) NOT NULL DEFAULT 'published',
  `applicability_json` JSON NOT NULL,
  `thresholds_json` JSON NOT NULL,
  `current_version_id` BIGINT NULL,
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `public` TINYINT(1) NOT NULL DEFAULT 1,
  `source_type` VARCHAR(64) NOT NULL DEFAULT 'product_rule',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_rules_code` (`code`),
  KEY `ix_training_rules_category_enabled` (`category`, `enabled`),
  KEY `ix_training_rules_scope_enabled` (`scope`, `enabled`),
  KEY `ix_training_rules_severity` (`severity`),
  KEY `ix_training_rules_lifecycle` (`lifecycle_status`),
  KEY `ix_training_rules_current_version_id` (`current_version_id`),
  CONSTRAINT `fk_training_rules_current_version_id`
    FOREIGN KEY (`current_version_id`) REFERENCES `training_rule_versions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_evidence_links` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `rule_code` VARCHAR(96) NOT NULL,
  `rule_version` VARCHAR(32) NOT NULL,
  `evidence_source_code` VARCHAR(96) NOT NULL,
  `relationship_type` VARCHAR(64) NOT NULL,
  `support_note` TEXT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_rule_evidence_version_link` (`rule_code`, `rule_version`, `evidence_source_code`, `relationship_type`),
  KEY `ix_rule_evidence_rule` (`rule_code`, `rule_version`),
  KEY `ix_rule_evidence_source` (`evidence_source_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_reviews` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `rule_code` VARCHAR(96) NOT NULL,
  `rule_version` VARCHAR(32) NOT NULL,
  `reviewer_id` BIGINT NULL,
  `review_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `review_comment` TEXT NULL,
  `checklist_json` JSON NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_reviews_rule` (`rule_code`, `rule_version`),
  KEY `ix_training_rule_reviews_status` (`review_status`),
  KEY `ix_training_rule_reviews_reviewer_id` (`reviewer_id`),
  CONSTRAINT `fk_training_rule_reviews_reviewer_id`
    FOREIGN KEY (`reviewer_id`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_test_cases` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(96) NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `description` TEXT NULL,
  `context_type` VARCHAR(64) NOT NULL,
  `facts_json` JSON NOT NULL,
  `expected_result_json` JSON NOT NULL,
  `tags_json` JSON NOT NULL,
  `source_type` VARCHAR(32) NOT NULL DEFAULT 'positive',
  `enabled` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_training_rule_test_cases_code` (`code`),
  KEY `ix_training_rule_test_cases_context` (`context_type`, `enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_test_runs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `ruleset_version` VARCHAR(64) NOT NULL,
  `run_type` VARCHAR(32) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'running',
  `total_cases` INT NOT NULL DEFAULT 0,
  `passed_cases` INT NOT NULL DEFAULT 0,
  `failed_cases` INT NOT NULL DEFAULT 0,
  `result_summary_json` JSON NOT NULL,
  `started_at` DATETIME NOT NULL,
  `finished_at` DATETIME NULL,
  `created_by` BIGINT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_test_runs_created` (`started_at`),
  KEY `ix_training_rule_test_runs_ruleset` (`ruleset_version`),
  KEY `ix_training_rule_test_runs_created_by` (`created_by`),
  CONSTRAINT `fk_training_rule_test_runs_created_by`
    FOREIGN KEY (`created_by`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_test_results` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `test_run_id` BIGINT NOT NULL,
  `test_case_code` VARCHAR(96) NOT NULL,
  `passed` TINYINT(1) NOT NULL DEFAULT 0,
  `actual_result_json` JSON NOT NULL,
  `expected_result_json` JSON NOT NULL,
  `diff_json` JSON NOT NULL,
  `duration_ms` INT NOT NULL DEFAULT 0,
  `error_message` TEXT NULL,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_test_results_run` (`test_run_id`),
  KEY `ix_training_rule_test_results_case` (`test_case_code`),
  CONSTRAINT `fk_training_rule_test_results_run`
    FOREIGN KEY (`test_run_id`) REFERENCES `training_rule_test_runs` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_audit_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `actor_user_id` BIGINT NULL,
  `action` VARCHAR(64) NOT NULL,
  `target_type` VARCHAR(64) NOT NULL,
  `target_code` VARCHAR(96) NULL,
  `target_version` VARCHAR(32) NULL,
  `before_snapshot_json` JSON NULL,
  `after_snapshot_json` JSON NULL,
  `reason` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_audit_actor_created` (`actor_user_id`, `created_at`),
  KEY `ix_training_rule_audit_target` (`target_type`, `target_code`, `target_version`),
  CONSTRAINT `fk_training_rule_audit_actor`
    FOREIGN KEY (`actor_user_id`) REFERENCES `user_account` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_evaluations` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `context_type` VARCHAR(64) NOT NULL,
  `context_id` VARCHAR(128) NULL,
  `input_snapshot_json` JSON NOT NULL,
  `final_result_json` JSON NOT NULL,
  `dominant_rule_code` VARCHAR(96) NULL,
  `engine_version` VARCHAR(32) NOT NULL,
  `ruleset_version` VARCHAR(64) NOT NULL,
  `facts_hash` VARCHAR(64) NULL,
  `source_version` VARCHAR(64) NULL,
  `is_stale` TINYINT(1) NOT NULL DEFAULT 0,
  `stale_reason` VARCHAR(255) NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_eval_user_created` (`user_id`, `created_at`),
  KEY `ix_training_rule_eval_context` (`context_type`, `context_id`),
  KEY `ix_training_rule_eval_hash` (`user_id`, `context_type`, `context_id`, `facts_hash`),
  CONSTRAINT `fk_training_rule_eval_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_rule_hits` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `evaluation_id` BIGINT NOT NULL,
  `rule_code` VARCHAR(96) NOT NULL,
  `rule_version` VARCHAR(32) NOT NULL,
  `matched` TINYINT(1) NOT NULL DEFAULT 1,
  `severity` VARCHAR(32) NOT NULL,
  `priority` INT NOT NULL,
  `input_snapshot_json` JSON NOT NULL,
  `output_json` JSON NOT NULL,
  `explanation` TEXT NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_rule_hits_evaluation_id` (`evaluation_id`),
  KEY `ix_training_rule_hits_rule_code` (`rule_code`),
  CONSTRAINT `fk_training_rule_hits_evaluation_id`
    FOREIGN KEY (`evaluation_id`) REFERENCES `training_rule_evaluations` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `training_adjustment_drafts` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `source_type` VARCHAR(64) NOT NULL,
  `source_evaluation_id` BIGINT NULL,
  `cycle_id` BIGINT NULL,
  `week_start` DATE NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'draft',
  `adjustment_json` JSON NOT NULL,
  `explanation_json` JSON NOT NULL,
  `original_plan_snapshot_json` JSON NOT NULL,
  `applied_result_json` JSON NULL,
  `facts_hash` VARCHAR(64) NULL,
  `source_version` VARCHAR(64) NULL,
  `applied_at` DATETIME NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_adjustment_user_status` (`user_id`, `status`),
  KEY `ix_training_adjustment_user_source` (`user_id`, `source_type`, `source_evaluation_id`),
  KEY `ix_training_adjustment_cycle_week` (`cycle_id`, `week_start`),
  KEY `ix_training_adjustment_source_evaluation_id` (`source_evaluation_id`),
  CONSTRAINT `fk_training_adjustment_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_training_adjustment_source_evaluation_id`
    FOREIGN KEY (`source_evaluation_id`) REFERENCES `training_rule_evaluations` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_training_adjustment_cycle_id`
    FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `runner_state_snapshots` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `snapshot_date` DATE NOT NULL,
  `data_cutoff_date` DATE NOT NULL,
  `calculated_at` DATETIME NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `trigger_type` VARCHAR(32) NOT NULL DEFAULT 'MANUAL',
  `trigger_reference` VARCHAR(128) NULL,
  `snapshot_schema_version` VARCHAR(64) NOT NULL,
  `ruleset_version` VARCHAR(64) NOT NULL,
  `distance_7d_km` DECIMAL(10,2) NULL,
  `distance_28d_km` DECIMAL(10,2) NULL,
  `volume_trend` VARCHAR(32) NULL,
  `training_consistency` VARCHAR(32) NULL,
  `fatigue_state` VARCHAR(32) NULL,
  `training_phase` VARCHAR(32) NULL,
  `risk_flag_count` INT NOT NULL DEFAULT 0,
  `evidence_coverage` DECIMAL(6,4) NULL,
  `data_completeness` DECIMAL(6,4) NULL,
  `snapshot_payload` JSON NOT NULL,
  `payload_hash` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_runner_state_snapshot_user_cutoff_hash`
    (`user_id`, `data_cutoff_date`, `payload_hash`),
  KEY `ix_runner_state_snapshots_user_cutoff` (`user_id`, `data_cutoff_date`),
  KEY `ix_runner_state_snapshots_user_created` (`user_id`, `created_at`),
  CONSTRAINT `fk_runner_state_snapshots_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `runner_state_snapshot_trigger_receipt` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `trigger_type` VARCHAR(32) NOT NULL,
  `trigger_reference` VARCHAR(128) NOT NULL,
  `status` VARCHAR(40) NOT NULL,
  `snapshot_id` BIGINT NULL,
  `sync_job_id` BIGINT NULL,
  `material_change_count` INT NOT NULL DEFAULT 0,
  `is_committed` TINYINT(1) NOT NULL DEFAULT 0,
  `attempt_count` INT NOT NULL DEFAULT 0,
  `processing_token` VARCHAR(36) NULL,
  `locked_at` DATETIME NULL,
  `completed_at` DATETIME NULL,
  `error_code` VARCHAR(64) NULL,
  `safe_error_message` VARCHAR(255) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  CONSTRAINT `uq_runner_state_receipt_user_trigger_reference`
    UNIQUE (`user_id`, `trigger_type`, `trigger_reference`),
  CONSTRAINT `ck_runner_state_receipt_material_change_nonnegative`
    CHECK (`material_change_count` >= 0),
  CONSTRAINT `ck_runner_state_receipt_attempt_count_nonnegative`
    CHECK (`attempt_count` >= 0),
  KEY `ix_runner_state_receipt_user_created` (`user_id`, `created_at`),
  KEY `ix_runner_state_receipt_sync_job` (`sync_job_id`),
  KEY `ix_runner_state_receipt_status_locked` (`status`, `locked_at`),
  KEY `ix_runner_state_receipt_snapshot` (`snapshot_id`),
  CONSTRAINT `fk_runner_state_receipt_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_runner_state_receipt_snapshot_id`
    FOREIGN KEY (`snapshot_id`) REFERENCES `runner_state_snapshots` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_runner_state_receipt_sync_job_id`
    FOREIGN KEY (`sync_job_id`) REFERENCES `external_sync_job` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `adaptive_plan_versions` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `proposal_id` BIGINT NULL,
  `version_number` INT NOT NULL,
  `previous_version_id` BIGINT NULL,
  `rollback_of_version_id` BIGINT NULL,
  `reason` VARCHAR(1000) NOT NULL,
  `actor_user_id` BIGINT NOT NULL,
  `source` VARCHAR(64) NOT NULL,
  `before_snapshot_json` JSON NOT NULL,
  `after_snapshot_json` JSON NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_adaptive_plan_version_user_number` (`user_id`, `version_number`),
  UNIQUE KEY `uq_adaptive_plan_version_proposal` (`proposal_id`),
  KEY `ix_adaptive_plan_versions_user_created` (`user_id`, `created_at`),
  CONSTRAINT `fk_adaptive_plan_version_user` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_adaptive_plan_version_actor` FOREIGN KEY (`actor_user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_adaptive_plan_version_proposal` FOREIGN KEY (`proposal_id`) REFERENCES `training_adjustment_drafts` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_adaptive_plan_version_previous` FOREIGN KEY (`previous_version_id`) REFERENCES `adaptive_plan_versions` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_adaptive_plan_version_rollback` FOREIGN KEY (`rollback_of_version_id`) REFERENCES `adaptive_plan_versions` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `adaptive_workflow_checkpoints` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `thread_id` VARCHAR(128) NOT NULL,
  `checkpoint_namespace` VARCHAR(128) NOT NULL DEFAULT '',
  `checkpoint_id` VARCHAR(128) NOT NULL,
  `parent_checkpoint_id` VARCHAR(128) NULL,
  `checkpoint_type` VARCHAR(64) NOT NULL,
  `checkpoint_blob` LONGBLOB NOT NULL,
  `metadata_type` VARCHAR(64) NOT NULL,
  `metadata_blob` LONGBLOB NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_adaptive_checkpoint_thread_namespace_id` (`thread_id`, `checkpoint_namespace`, `checkpoint_id`),
  KEY `ix_adaptive_checkpoint_thread_created` (`thread_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `adaptive_workflow_checkpoint_writes` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `thread_id` VARCHAR(128) NOT NULL,
  `checkpoint_namespace` VARCHAR(128) NOT NULL DEFAULT '',
  `checkpoint_id` VARCHAR(128) NOT NULL,
  `task_id` VARCHAR(128) NOT NULL,
  `task_path` VARCHAR(512) NOT NULL DEFAULT '',
  `write_index` INT NOT NULL,
  `channel` VARCHAR(128) NOT NULL,
  `value_type` VARCHAR(64) NOT NULL,
  `value_blob` LONGBLOB NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_adaptive_checkpoint_write_identity` (`thread_id`, `checkpoint_namespace`, `checkpoint_id`, `task_id`, `task_path`, `write_index`),
  KEY `ix_adaptive_checkpoint_writes_lookup` (`thread_id`, `checkpoint_namespace`, `checkpoint_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
