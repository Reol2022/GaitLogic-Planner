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
  `target_race_name` VARCHAR(128) NULL,
  `target_race_date` DATE NULL,
  `target_result` VARCHAR(64) NULL,
  `description` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_training_cycles_user_id` (`user_id`),
  CONSTRAINT `fk_training_cycles_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
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
  `date_text` VARCHAR(64) NULL,
  `weekday` VARCHAR(32) NULL,
  `month_text` VARCHAR(32) NULL,
  `phase_name` VARCHAR(128) NULL,
  `planned_content` TEXT NOT NULL,
  `focus_note` TEXT NULL,
  `planned_distance_km` DECIMAL(7, 2) NULL,
  `main_type_raw` VARCHAR(64) NULL,
  `main_type_normalized` VARCHAR(32) NOT NULL DEFAULT 'unknown',
  `source_sheet` VARCHAR(128) NULL,
  `source_row` INT NULL,
  `sort_order` INT NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_planned_workouts_cycle_date` (`cycle_id`, `workout_date`),
  KEY `ix_planned_workouts_cycle_id` (`cycle_id`),
  KEY `ix_planned_workouts_user_id` (`user_id`),
  KEY `ix_planned_workouts_block_id` (`block_id`),
  KEY `ix_planned_workouts_workout_date` (`workout_date`),
  KEY `ix_planned_workouts_main_type_normalized` (`main_type_normalized`),
  CONSTRAINT `fk_planned_workouts_cycle_id`
    FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_planned_workouts_block_id`
    FOREIGN KEY (`block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_planned_workouts_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workout_logs` (
  `id` BIGINT NOT NULL AUTO_INCREMENT,
  `planned_workout_id` BIGINT NOT NULL,
  `user_id` BIGINT NOT NULL,
  `status_raw` VARCHAR(64) NULL,
  `status_normalized` VARCHAR(32) NOT NULL DEFAULT 'not_started',
  `actual_distance_km` DECIMAL(7, 2) NULL,
  `actual_duration_seconds` INT NULL,
  `avg_pace_seconds_per_km` INT NULL,
  `avg_heart_rate` INT NULL,
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
  `main_session_data` TEXT NULL,
  `review_note` TEXT NULL,
  `tomorrow_adjustment` TEXT NULL,
  `alert_message` TEXT NULL,
  `completion_rate` DECIMAL(5, 2) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_workout_logs_planned_workout` (`planned_workout_id`),
  KEY `ix_workout_logs_planned_workout_id` (`planned_workout_id`),
  KEY `ix_workout_logs_user_id` (`user_id`),
  KEY `ix_workout_logs_status_normalized` (`status_normalized`),
  CONSTRAINT `fk_workout_logs_planned_workout_id`
    FOREIGN KEY (`planned_workout_id`) REFERENCES `planned_workouts` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workout_logs_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE,
  CONSTRAINT `ck_workout_logs_pain_level_range`
    CHECK (`pain_level` IS NULL OR (`pain_level` >= 0 AND `pain_level` <= 5))
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
    CHECK (`max_pain_level` IS NULL OR (`max_pain_level` >= 0 AND `max_pain_level` <= 5))
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
