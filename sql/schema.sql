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
