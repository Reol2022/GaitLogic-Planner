/*
 Navicat Premium Data Transfer

 Source Server         : 本地8.0
 Source Server Type    : MySQL
 Source Server Version : 80046
 Source Host           : localhost:3307
 Source Schema         : gaitlogic_planner

 Target Server Type    : MySQL
 Target Server Version : 80046
 File Encoding         : 65001

 Date: 09/06/2026 14:14:53
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for ai_plan_draft
-- ----------------------------
DROP TABLE IF EXISTS `ai_plan_draft`;
CREATE TABLE `ai_plan_draft`  (
  `user_id` bigint(0) NOT NULL,
  `job_id` bigint(0) NOT NULL,
  `title` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `goal` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `start_date` date NULL DEFAULT NULL,
  `end_date` date NULL DEFAULT NULL,
  `target_race_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `target_race_date` date NULL DEFAULT NULL,
  `target_result` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `risk_notes` json NULL,
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'draft',
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `ix_ai_plan_draft_job_id`(`job_id`) USING BTREE,
  INDEX `ix_ai_plan_draft_user_id`(`user_id`) USING BTREE,
  INDEX `ix_ai_plan_draft_user_status`(`user_id`, `status`) USING BTREE,
  CONSTRAINT `ai_plan_draft_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `ai_plan_draft_ibfk_2` FOREIGN KEY (`job_id`) REFERENCES `ai_plan_job` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of ai_plan_draft
-- ----------------------------

-- ----------------------------
-- Table structure for ai_plan_draft_workout
-- ----------------------------
DROP TABLE IF EXISTS `ai_plan_draft_workout`;
CREATE TABLE `ai_plan_draft_workout`  (
  `draft_id` bigint(0) NOT NULL,
  `workout_date` date NOT NULL,
  `weekday` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `block_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `phase_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `planned_content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `focus_note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `planned_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `main_type_raw` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `main_type_normalized` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'unknown',
  `target_pace_text` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `sort_order` int(0) NOT NULL,
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_ai_plan_draft_workout_draft_id`(`draft_id`) USING BTREE,
  INDEX `ix_ai_plan_draft_workout_date`(`workout_date`) USING BTREE,
  CONSTRAINT `ai_plan_draft_workout_ibfk_1` FOREIGN KEY (`draft_id`) REFERENCES `ai_plan_draft` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of ai_plan_draft_workout
-- ----------------------------

-- ----------------------------
-- Table structure for ai_plan_job
-- ----------------------------
DROP TABLE IF EXISTS `ai_plan_job`;
CREATE TABLE `ai_plan_job`  (
  `user_id` bigint(0) NOT NULL,
  `status` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `model_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `prompt_hash` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `input_json` json NOT NULL,
  `output_json` json NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `input_tokens` int(0) NULL DEFAULT NULL,
  `output_tokens` int(0) NULL DEFAULT NULL,
  `total_tokens` int(0) NULL DEFAULT NULL,
  `finished_at` datetime(0) NULL DEFAULT NULL,
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_ai_plan_job_user_id`(`user_id`) USING BTREE,
  INDEX `ix_ai_plan_job_user_prompt`(`user_id`, `prompt_hash`) USING BTREE,
  CONSTRAINT `ai_plan_job_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of ai_plan_job
-- ----------------------------

-- ----------------------------
-- Table structure for ai_plan_quota
-- ----------------------------
DROP TABLE IF EXISTS `ai_plan_quota`;
CREATE TABLE `ai_plan_quota`  (
  `user_id` bigint(0) NOT NULL,
  `quota_date` date NOT NULL,
  `daily_limit` int(0) NOT NULL,
  `used_count` int(0) NOT NULL DEFAULT 0,
  `last_generated_at` datetime(0) NULL DEFAULT NULL,
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_ai_plan_quota_user_date`(`user_id`, `quota_date`) USING BTREE,
  INDEX `ix_ai_plan_quota_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `ai_plan_quota_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of ai_plan_quota
-- ----------------------------
INSERT INTO `ai_plan_quota` VALUES (1, '2026-06-09', 3, 0, NULL, 1, '2026-06-09 11:31:51', '2026-06-09 11:31:51');

-- ----------------------------
-- Table structure for block_reviews
-- ----------------------------
DROP TABLE IF EXISTS `block_reviews`;
CREATE TABLE `block_reviews`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `block_id` bigint(0) NOT NULL,
  `planned_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `actual_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `completion_rate` decimal(5, 2) NULL DEFAULT NULL,
  `i_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `t1_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `t2_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `m_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `r_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `avg_rpe` decimal(4, 2) NULL DEFAULT NULL,
  `avg_weight_kg` decimal(5, 2) NULL DEFAULT NULL,
  `max_pain_level` int(0) NULL DEFAULT NULL,
  `review_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `next_block_adjustment` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_block_reviews_block`(`block_id`) USING BTREE,
  INDEX `ix_block_reviews_block_id`(`block_id`) USING BTREE,
  INDEX `ix_block_reviews_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `fk_block_reviews_block_id` FOREIGN KEY (`block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 16 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of block_reviews
-- ----------------------------
INSERT INTO `block_reviews` VALUES (1, 1, 92.00, 88.50, 96.20, 5.00, 8.00, 0.00, 0.00, 1.20, 5.50, 68.80, 1, '整体接量顺利，强度控制合理', '下周恢复正常二四日结构', '2026-06-06 12:07:15', '2026-06-08 15:26:26', 1);
INSERT INTO `block_reviews` VALUES (2, 2, 103.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (3, 3, 116.50, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (4, 4, 82.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (5, 5, 27.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (6, 6, 76.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (7, 7, 118.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (8, 8, 117.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (9, 9, 120.50, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (10, 10, 91.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (11, 11, 120.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (12, 12, 131.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (13, 13, 127.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (14, 14, 116.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);
INSERT INTO `block_reviews` VALUES (15, 15, 88.00, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:15', '2026-06-06 21:46:43', 1);

-- ----------------------------
-- Table structure for excel_import_jobs
-- ----------------------------
DROP TABLE IF EXISTS `excel_import_jobs`;
CREATE TABLE `excel_import_jobs`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `file_name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `file_path` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `file_hash` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `sheet_names` json NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `total_count` int(0) NOT NULL DEFAULT 0,
  `success_count` int(0) NOT NULL DEFAULT 0,
  `failed_count` int(0) NOT NULL DEFAULT 0,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `started_at` datetime(0) NULL DEFAULT NULL,
  `finished_at` datetime(0) NULL DEFAULT NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_excel_import_jobs_file_hash`(`file_hash`) USING BTREE,
  INDEX `ix_excel_import_jobs_user_id`(`user_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of excel_import_jobs
-- ----------------------------
INSERT INTO `excel_import_jobs` VALUES (1, 'gaitlogic_planner_template_api_test.xlsx', NULL, 'af68a4b7b1513715d954ec4b7d75ad26d630071987ffa2744c71c14acc920ac9', '[\"填写说明\", \"训练周期\", \"训练块\", \"训练计划\", \"训练日志\", \"每周复盘\", \"配速规则\"]', 'success', 13, 13, 0, NULL, '2026-06-08 15:26:26', '2026-06-08 15:26:27', '2026-06-08 15:26:26', '2026-06-08 15:26:26', 1);

-- ----------------------------
-- Table structure for feedback
-- ----------------------------
DROP TABLE IF EXISTS `feedback`;
CREATE TABLE `feedback`  (
  `user_id` bigint(0) NOT NULL,
  `feedback_type` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `page_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'open',
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_feedback_user_id`(`user_id`) USING BTREE,
  INDEX `ix_feedback_user_created`(`user_id`, `created_at`) USING BTREE,
  CONSTRAINT `feedback_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of feedback
-- ----------------------------

-- ----------------------------
-- Table structure for pace_profile
-- ----------------------------
DROP TABLE IF EXISTS `pace_profile`;
CREATE TABLE `pace_profile`  (
  `user_id` bigint(0) NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `race_distance` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `race_result_seconds` int(0) NOT NULL,
  `vdot` decimal(5, 1) NOT NULL,
  `algorithm_version` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'approx_vdot_v1',
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_pace_profile_user_created`(`user_id`, `created_at`) USING BTREE,
  INDEX `ix_pace_profile_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `pace_profile_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `user_account` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 3 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of pace_profile
-- ----------------------------
INSERT INTO `pace_profile` VALUES (1, '半马 PB 1:12:32', 'half_marathon', 4352, 65.4, 'approx_vdot_v1', 1, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_profile` VALUES (1, '半马一级', 'half_marathon', 4290, 66.5, 'approx_vdot_v1', 2, '2026-06-08 19:15:47', '2026-06-08 19:15:47');

-- ----------------------------
-- Table structure for pace_rules
-- ----------------------------
DROP TABLE IF EXISTS `pace_rules`;
CREATE TABLE `pace_rules`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `code` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `target_pace_text` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `physiological_purpose` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `sort_order` int(0) NOT NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_pace_rules_code`(`code`) USING BTREE,
  INDEX `ix_pace_rules_user_id`(`user_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 9 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of pace_rules
-- ----------------------------
INSERT INTO `pace_rules` VALUES (1, 'R', '短速度', '2:49-2:57/km', '神经速度和跑姿经济性训练', '来自配速档案：半马一级，VDOT 66.5', 1, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (2, 'I', '间歇跑', '3:03-3:12/km', 'VO2max 间歇训练', '来自配速档案：半马一级，VDOT 66.5', 2, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (3, 'T2', '高阈值', '3:25-3:32/km', '高阈值，接近标准阈值强度', '来自配速档案：半马一级，VDOT 66.5', 3, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (4, 'T1', '稳阈值', '3:32-3:40/km', '稳阈值，比标准阈值稍慢', '来自配速档案：半马一级，VDOT 66.5', 4, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (5, 'M', '稳态跑', '3:43-4:00/km', '稳态跑，接近马拉松强度', '来自配速档案：半马一级，VDOT 66.5', 5, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (6, 'E', '轻松跑', '4:14-4:50/km', '轻松跑，用于有氧基础建设', '来自配速档案：半马一级，VDOT 66.5', 6, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (7, 'REC', '恢复跑', '4:50-5:15/km', '恢复跑，用于低强度恢复和双跑第二跑', '来自配速档案：半马一级，VDOT 66.5', 7, '2026-06-06 12:07:15', '2026-06-08 19:16:33', 1);
INSERT INTO `pace_rules` VALUES (8, 'LSD', '长距离', '4:45-5:45/km', '长时间有氧与肌耐力', '注意补给', 8, '2026-06-06 12:07:15', '2026-06-08 15:26:26', 1);

-- ----------------------------
-- Table structure for pace_zone
-- ----------------------------
DROP TABLE IF EXISTS `pace_zone`;
CREATE TABLE `pace_zone`  (
  `pace_profile_id` bigint(0) NOT NULL,
  `zone_code` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `zone_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `pace_min_seconds_per_km` int(0) NOT NULL,
  `pace_max_seconds_per_km` int(0) NOT NULL,
  `target_pace_text` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `sort_order` int(0) NOT NULL,
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_pace_zone_profile_code`(`pace_profile_id`, `zone_code`) USING BTREE,
  INDEX `ix_pace_zone_pace_profile_id`(`pace_profile_id`) USING BTREE,
  CONSTRAINT `pace_zone_ibfk_1` FOREIGN KEY (`pace_profile_id`) REFERENCES `pace_profile` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 14 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of pace_zone
-- ----------------------------
INSERT INTO `pace_zone` VALUES (1, 'REC', '恢复跑', 294, 319, '4:54-5:19/km', '恢复跑，用于低强度恢复和双跑第二跑', 1, 1, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'E', '轻松跑', 257, 294, '4:17-4:54/km', '轻松跑，用于有氧基础建设', 2, 2, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'M', '稳态 / 马拉松强度', 226, 244, '3:46-4:04/km', '稳态跑，接近马拉松强度', 3, 3, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'T1', '稳阈值', 215, 223, '3:35-3:43/km', '稳阈值，比标准阈值稍慢', 4, 4, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'T2', '高阈值', 208, 215, '3:28-3:35/km', '高阈值，接近标准阈值强度', 5, 5, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'I', '间歇', 185, 195, '3:05-3:15/km', 'VO2max 间歇训练', 6, 6, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (1, 'R', '短速度', 171, 180, '2:51-3:00/km', '神经速度和跑姿经济性训练', 7, 7, '2026-06-08 19:15:19', '2026-06-08 19:15:19');
INSERT INTO `pace_zone` VALUES (2, 'REC', '恢复跑', 290, 315, '4:50-5:15/km', '恢复跑，用于低强度恢复和双跑第二跑', 1, 8, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'E', '轻松跑', 254, 290, '4:14-4:50/km', '轻松跑，用于有氧基础建设', 2, 9, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'M', '稳态 / 马拉松强度', 223, 240, '3:43-4:00/km', '稳态跑，接近马拉松强度', 3, 10, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'T1', '稳阈值', 212, 220, '3:32-3:40/km', '稳阈值，比标准阈值稍慢', 4, 11, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'T2', '高阈值', 205, 212, '3:25-3:32/km', '高阈值，接近标准阈值强度', 5, 12, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'I', '间歇', 183, 192, '3:03-3:12/km', 'VO2max 间歇训练', 6, 13, '2026-06-08 19:15:47', '2026-06-08 19:15:47');
INSERT INTO `pace_zone` VALUES (2, 'R', '短速度', 169, 177, '2:49-2:57/km', '神经速度和跑姿经济性训练', 7, 14, '2026-06-08 19:15:47', '2026-06-08 19:15:47');

-- ----------------------------
-- Table structure for planned_workouts
-- ----------------------------
DROP TABLE IF EXISTS `planned_workouts`;
CREATE TABLE `planned_workouts`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `cycle_id` bigint(0) NOT NULL,
  `block_id` bigint(0) NOT NULL,
  `workout_date` date NULL DEFAULT NULL,
  `date_text` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `weekday` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `month_text` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `phase_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `planned_content` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `focus_note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `planned_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `main_type_raw` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `main_type_normalized` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'unknown',
  `source_sheet` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `source_row` int(0) NULL DEFAULT NULL,
  `sort_order` int(0) NOT NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_planned_workouts_cycle_date`(`cycle_id`, `workout_date`) USING BTREE,
  INDEX `ix_planned_workouts_cycle_id`(`cycle_id`) USING BTREE,
  INDEX `ix_planned_workouts_block_id`(`block_id`) USING BTREE,
  INDEX `ix_planned_workouts_workout_date`(`workout_date`) USING BTREE,
  INDEX `ix_planned_workouts_main_type_normalized`(`main_type_normalized`) USING BTREE,
  INDEX `ix_planned_workouts_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `fk_planned_workouts_block_id` FOREIGN KEY (`block_id`) REFERENCES `training_blocks` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_planned_workouts_cycle_id` FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 99 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of planned_workouts
-- ----------------------------
INSERT INTO `planned_workouts` VALUES (1, 1, 1, '2026-06-01', '2026-06-01', '周一', '06月', '6月计划', '轻松跑 10km + 4×100m', '控制心率，恢复节奏\n目标配速：4:45-5:30/km', 10.00, 'E', 'easy', '训练计划', 2, 1, '2026-06-06 12:07:14', '2026-06-08 15:26:26', 1);
INSERT INTO `planned_workouts` VALUES (2, 1, 1, '2026-06-02', '06.02', '周二', '06月', '6月计划', '10×400m @74-76秒，间歇200m慢跑；总量14-16km', '速度唤醒，不硬冲', 15.00, 'I/R', 'interval_speed', '6月计划', 10, 2, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (3, 1, 1, '2026-06-03', '06.03', '周三', '06月', '6月计划', 'E跑 16km @4:50-5:20', '单跑，有氧堆量', 16.00, 'E', 'easy', '6月计划', 11, 3, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (4, 1, 1, '2026-06-04', '06.04', '周四', '06月', '6月计划', '4×2km @3:33-3:38，间歇2分钟慢跑 + 4×100m；总量16-18km', '稳阈值 + 疲劳后提频', 17.00, 'T', 'tempo', '6月计划', 12, 4, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (5, 1, 1, '2026-06-05', '06.05', '周五', '06月', '6月计划', 'REC 10km @5:10-5:40 + 力量', '小腿、臀中肌、核心', 10.00, 'REC', 'recovery', '6月计划', 13, 5, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (6, 1, 1, '2026-06-06', '06.06', '周六', '06月', '6月计划', '全休', '真休息', 0.00, 'Rest', 'rest', '6月计划', 14, 6, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (7, 1, 1, '2026-06-07', '06.07', '周日', '06月', '6月计划', 'LSD 22km @4:35-4:55', '轻松长距离', 22.00, 'LSD', 'long_run', '6月计划', 15, 7, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (8, 1, 2, '2026-06-08', '06.08', '周一', '06月', '6月计划', '上午E 10km + 下午REC 6km', '第一周双卡，下午必须慢', 16.00, 'REC', 'recovery', '6月计划', 20, 8, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (9, 1, 2, '2026-06-09', '06.09', '周二', '06月', '6月计划', '6×1000m @3:15-3:18，间歇90秒慢跑；总量16-18km', '稳住，不抢前两组', 17.00, 'I/R', 'interval_speed', '6月计划', 21, 9, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (10, 1, 2, '2026-06-10', '06.10', '周三', '06月', '6月计划', 'E跑 18km @4:45-5:20', '有氧堆量', 18.00, 'E', 'easy', '6月计划', 22, 10, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (11, 1, 2, '2026-06-11', '06.11', '周四', '06月', '6月计划', '8km T @3:38-3:43 + 6×100m；总量16km', '连续节奏，跑稳', 16.00, 'T', 'tempo', '6月计划', 23, 11, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (12, 1, 2, '2026-06-12', '06.12', '周五', '06月', '6月计划', 'REC 12km @5:10-5:40 + 力量', '恢复为主', 12.00, 'REC', 'recovery', '6月计划', 24, 12, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (13, 1, 2, '2026-06-13', '06.13', '周六', '06月', '6月计划', '全休', '睡眠优先', 0.00, 'Rest', 'rest', '6月计划', 25, 13, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (14, 1, 2, '2026-06-14', '06.14', '周日', '06月', '6月计划', 'LSD 24km @4:30-4:55', '后5km可自然到4:15-4:25', 24.00, 'LSD', 'long_run', '6月计划', 26, 14, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (15, 1, 3, '2026-06-15', '06.15', '周一', '06月', '6月计划', '上午E 12km + 下午REC 6km', '双卡，恢复感第一', 18.00, 'REC', 'recovery', '6月计划', 31, 15, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (16, 1, 3, '2026-06-16', '06.16', '周二', '06月', '6月计划', '5×1200m @3:50-3:55/组，间歇2分半 + 4×200m @35-37秒；总量18-19km', '5000专项 + 速度收尾', 18.50, 'I/R', 'interval_speed', '6月计划', 32, 16, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (17, 1, 3, '2026-06-17', '06.17', '周三', '06月', '6月计划', 'E跑 18-20km @4:45-5:20', '稳住跑量', 19.00, 'E', 'easy', '6月计划', 33, 17, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (18, 1, 3, '2026-06-18', '06.18', '周四', '06月', '6月计划', '3×3km @3:32-3:38，间歇3分钟慢跑 + 4×100m；总量18-20km', '阈值主菜', 19.00, 'T', 'tempo', '6月计划', 34, 18, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (19, 1, 3, '2026-06-19', '06.19', '周五', '06月', '6月计划', '上午REC 10km + 下午REC 6km', '慢到无聊才对', 16.00, 'REC', 'recovery', '6月计划', 35, 19, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (20, 1, 3, '2026-06-20', '06.20', '周六', '06月', '6月计划', '全休', '小腿、足底放松', 0.00, 'Rest', 'rest', '6月计划', 36, 20, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (21, 1, 3, '2026-06-21', '06.21', '周日', '06月', '6月计划', 'LSD 26km @4:30-4:55', '不做后程硬加速', 26.00, 'LSD', 'long_run', '6月计划', 37, 21, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (22, 1, 4, '2026-06-22', '06.22', '周一', '06月', '6月计划', 'REC 10km @5:10-5:40', '回血', 10.00, 'REC', 'recovery', '6月计划', 42, 22, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (23, 1, 4, '2026-06-23', '06.23', '周二', '06月', '6月计划', '12×200m @34-36秒，间歇200m慢跑；总量12-14km', '速度感，不累积疲劳', 13.00, 'I/R', 'interval_speed', '6月计划', 43, 23, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (24, 1, 4, '2026-06-24', '06.24', '周三', '06月', '6月计划', 'E跑 14-16km', '不双卡', 15.00, 'E', 'easy', '6月计划', 44, 24, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (25, 1, 4, '2026-06-25', '06.25', '周四', '06月', '6月计划', '5-6km T @3:35-3:40 + 4×100m；总量12-14km', '保持阈值', 13.00, 'T', 'tempo', '6月计划', 45, 25, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (26, 1, 4, '2026-06-26', '06.26', '周五', '06月', '6月计划', 'REC 10km + 力量', '低负担', 10.00, 'REC', 'recovery', '6月计划', 46, 26, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (27, 1, 4, '2026-06-27', '06.27', '周六', '06月', '6月计划', '全休', '完全休', 0.00, 'Rest', 'rest', '6月计划', 47, 27, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (28, 1, 4, '2026-06-28', '06.28', '周日', '06月', '6月计划', 'LSD 20-22km @4:35-5:00', '恢复长距离', 21.00, 'LSD', 'long_run', '6月计划', 48, 28, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (29, 1, 5, '2026-06-29', '06.29', '周一', '06月', '6月计划', 'E跑 12km + 6×100m', '进入7月前激活', 12.00, 'E+R', 'easy_with_speed', '6月计划', 52, 29, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (30, 1, 5, '2026-06-30', '06.30', '周二', '06月', '6月计划', '6×800m @2:30-2:34，间歇90秒慢跑；总量14-16km', '不跑炸', 15.00, 'I/R', 'interval_speed', '6月计划', 53, 30, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (31, 1, 6, '2026-07-01', '07.01', '周三', '07月', '7月计划', '上午E 14km + 下午REC 6km', '双卡接入', 20.00, 'REC', 'recovery', '7月计划', 10, 31, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (32, 1, 6, '2026-07-02', '07.02', '周四', '07月', '7月计划', '4×2km @3:28-3:33 + 4×200m @35-37秒；总量17-19km', '阈值 + 速度', 18.00, 'T', 'tempo', '7月计划', 11, 32, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (33, 1, 6, '2026-07-03', '07.03', '周五', '07月', '7月计划', 'REC 12km', '慢', 12.00, 'REC', 'recovery', '7月计划', 12, 33, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (34, 1, 6, '2026-07-04', '07.04', '周六', '07月', '7月计划', '全休', '固定休息', 0.00, 'Rest', 'rest', '7月计划', 13, 34, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (35, 1, 6, '2026-07-05', '07.05', '周日', '07月', '7月计划', 'LSD 26km @4:25-4:55', '稳住', 26.00, 'LSD', 'long_run', '7月计划', 14, 35, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (36, 1, 7, '2026-07-06', '07.06', '周一', '07月', '7月计划', '上午E 12km + 下午REC 6km', '双卡', 18.00, 'REC', 'recovery', '7月计划', 19, 36, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (37, 1, 7, '2026-07-07', '07.07', '周二', '07月', '7月计划', '6×1000m @3:10-3:14，间歇90秒慢跑 + 4×200m @35-36秒；总量18-20km', 'I + R，不能前快后崩', 19.00, 'I/R', 'interval_speed', '7月计划', 20, 37, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (38, 1, 7, '2026-07-08', '07.08', '周三', '07月', '7月计划', '上午E 16km + 下午REC 6km', '堆量', 22.00, 'REC', 'recovery', '7月计划', 21, 38, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (39, 1, 7, '2026-07-09', '07.09', '周四', '07月', '7月计划', '3×3km @3:28-3:33，间歇3分钟慢跑 + 4×100m；总量18-20km', '阈值主菜', 19.00, 'T', 'tempo', '7月计划', 22, 39, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (40, 1, 7, '2026-07-10', '07.10', '周五', '07月', '7月计划', 'REC 12km + 力量', '恢复', 12.00, 'REC', 'recovery', '7月计划', 23, 40, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (41, 1, 7, '2026-07-11', '07.11', '周六', '07月', '7月计划', '全休', '必须休', 0.00, 'Rest', 'rest', '7月计划', 24, 41, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (42, 1, 7, '2026-07-12', '07.12', '周日', '07月', '7月计划', 'LSD 28km @4:25-4:55', '只吃距离，不加速', 28.00, 'LSD', 'long_run', '7月计划', 25, 42, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (43, 1, 8, '2026-07-13', '07.13', '周一', '07月', '7月计划', '上午E 12km + 下午REC 6km', '恢复', 18.00, 'REC', 'recovery', '7月计划', 30, 43, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (44, 1, 8, '2026-07-14', '07.14', '周二', '07月', '7月计划', '3×1600m @5:05-5:12，间歇3分钟 + 4×200m @34-36秒；总量18km', '5000专项', 18.00, 'I/R', 'interval_speed', '7月计划', 31, 44, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (45, 1, 8, '2026-07-15', '07.15', '周三', '07月', '7月计划', '上午E 18km + 下午REC 6km', '高量日', 24.00, 'REC', 'recovery', '7月计划', 32, 45, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (46, 1, 8, '2026-07-16', '07.16', '周四', '07月', '7月计划', '2×5km @3:28-3:33，间歇4分钟慢跑；总量20-22km', '半马核心阈值', 21.00, 'T', 'tempo', '7月计划', 33, 46, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (47, 1, 8, '2026-07-17', '07.17', '周五', '07月', '7月计划', 'REC 12km + 6×100m', '放松提频', 12.00, 'REC', 'recovery', '7月计划', 34, 47, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (48, 1, 8, '2026-07-18', '07.18', '周六', '07月', '7月计划', '全休', '法定休息', 0.00, 'Rest', 'rest', '7月计划', 35, 48, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (49, 1, 8, '2026-07-19', '07.19', '周日', '07月', '7月计划', '24km：前18km E，后6km @3:50-4:00', '后程稳态', 24.00, 'E', 'easy', '7月计划', 36, 49, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (50, 1, 9, '2026-07-20', '07.20', '周一', '07月', '7月计划', '上午E 12km + 下午REC 8km', '双卡', 20.00, 'REC', 'recovery', '7月计划', 41, 50, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (51, 1, 9, '2026-07-21', '07.21', '周二', '07月', '7月计划', '12×400m @72-75秒，间歇200m慢跑；总量17-18km', '速度保留，不硬冲70', 17.50, 'I/R', 'interval_speed', '7月计划', 42, 51, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (52, 1, 9, '2026-07-22', '07.22', '周三', '07月', '7月计划', '上午E 18km + 下午REC 6km', '堆量', 24.00, 'REC', 'recovery', '7月计划', 43, 52, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (53, 1, 9, '2026-07-23', '07.23', '周四', '07月', '7月计划', '10-12km T @3:33-3:38 + 6×100m；总量18-20km', '连续阈值', 19.00, 'T', 'tempo', '7月计划', 44, 53, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (54, 1, 9, '2026-07-24', '07.24', '周五', '07月', '7月计划', 'REC 12km + 力量', '小腿、臀、核心', 12.00, 'REC', 'recovery', '7月计划', 45, 54, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (55, 1, 9, '2026-07-25', '07.25', '周六', '07月', '7月计划', '全休', '休息', 0.00, 'Rest', 'rest', '7月计划', 46, 55, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (56, 1, 9, '2026-07-26', '07.26', '周日', '07月', '7月计划', 'LSD 28km @4:20-4:50', '不抢配速', 28.00, 'LSD', 'long_run', '7月计划', 47, 56, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (57, 1, 10, '2026-07-27', '07.27', '周一', '07月', '7月计划', 'REC 10-12km', '回血', 11.00, 'REC', 'recovery', '7月计划', 52, 57, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (58, 1, 10, '2026-07-28', '07.28', '周二', '07月', '7月计划', '10×300m @51-53秒，间歇200m慢跑；总量12-14km', '1500速度感', 13.00, 'I/R', 'interval_speed', '7月计划', 53, 58, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (59, 1, 10, '2026-07-29', '07.29', '周三', '07月', '7月计划', 'E跑 16km', '不双卡', 16.00, 'E', 'easy', '7月计划', 54, 59, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (60, 1, 10, '2026-07-30', '07.30', '周四', '07月', '7月计划', '4×2km @3:28-3:32，间歇2分钟 + 4×100m；总量16-18km', '保阈值', 17.00, 'T', 'tempo', '7月计划', 55, 60, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (61, 1, 10, '2026-07-31', '07.31', '周五', '07月', '7月计划', 'REC 10-12km', '慢', 11.00, 'REC', 'recovery', '7月计划', 56, 61, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (62, 1, 10, '2026-08-01', '08.01', '周六', '08月', '7月计划', '全休', '完全休', 0.00, 'Rest', 'rest', '7月计划', 57, 62, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (63, 1, 10, '2026-08-02', '08.02', '周日', '08月', '7月计划', 'LSD 22-24km @4:35-5:00', '恢复长距离', 23.00, 'LSD', 'long_run', '7月计划', 58, 63, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (64, 1, 11, '2026-08-03', '08.03', '周一', '08月', '8月计划', '上午E 12km + 下午REC 6km', '双卡恢复', 18.00, 'REC', 'recovery', '8月计划', 9, 64, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (65, 1, 11, '2026-08-04', '08.04', '周二', '08月', '8月计划', '3000m @9:40-9:50 + 4×400m @72-74秒 + 4×200m @35秒；总量17-19km', '专补5000后程短板', 18.00, 'I/R', 'interval_speed', '8月计划', 10, 65, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (66, 1, 11, '2026-08-05', '08.05', '周三', '08月', '8月计划', '上午E 18km + 下午REC 6km', '堆量', 24.00, 'REC', 'recovery', '8月计划', 11, 66, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (67, 1, 11, '2026-08-06', '08.06', '周四', '08月', '8月计划', '4×3km @3:26-3:30，间歇3分钟；总量22km', '半马专项阈值', 22.00, 'T', 'tempo', '8月计划', 12, 67, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (68, 1, 11, '2026-08-07', '08.07', '周五', '08月', '8月计划', 'REC 12km + 6×100m', '放松', 12.00, 'REC', 'recovery', '8月计划', 13, 68, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (69, 1, 11, '2026-08-08', '08.08', '周六', '08月', '8月计划', '全休', '保命', 0.00, 'Rest', 'rest', '8月计划', 14, 69, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (70, 1, 11, '2026-08-09', '08.09', '周日', '08月', '8月计划', '26km：前18km E，后8km @3:40-3:50', '长距离后程能力', 26.00, 'E', 'easy', '8月计划', 15, 70, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (71, 1, 12, '2026-08-10', '08.10', '周一', '08月', '8月计划', '上午E 12km + 下午REC 8km', '双卡', 20.00, 'REC', 'recovery', '8月计划', 19, 71, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (72, 1, 12, '2026-08-11', '08.11', '周二', '08月', '8月计划', '6×1000m @3:08-3:12，间歇90秒 + 4×200m @34-36秒；总量18-20km', '5000专项，不炸', 19.00, 'I/R', 'interval_speed', '8月计划', 20, 72, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (73, 1, 12, '2026-08-12', '08.12', '周三', '08月', '8月计划', '上午E 20km + 下午REC 6km', '高量日', 26.00, 'REC', 'recovery', '8月计划', 21, 73, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (74, 1, 12, '2026-08-13', '08.13', '周四', '08月', '8月计划', '3×5km @3:26-3:30，间歇4分钟；总量24km', '半马核心门槛课', 24.00, 'T', 'tempo', '8月计划', 22, 74, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (75, 1, 12, '2026-08-14', '08.14', '周五', '08月', '8月计划', 'REC 12km', '慢', 12.00, 'REC', 'recovery', '8月计划', 23, 75, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (76, 1, 12, '2026-08-15', '08.15', '周六', '08月', '8月计划', '全休', '彻底休', 0.00, 'Rest', 'rest', '8月计划', 24, 76, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (77, 1, 12, '2026-08-16', '08.16', '周日', '08月', '8月计划', 'LSD 30km @4:25-4:55', '跑距离，不比配速', 30.00, 'LSD', 'long_run', '8月计划', 25, 77, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (78, 1, 13, '2026-08-17', '08.17', '周一', '08月', '8月计划', '上午E 12km + 下午REC 8km', '双卡', 20.00, 'REC', 'recovery', '8月计划', 29, 78, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (79, 1, 13, '2026-08-18', '08.18', '周二', '08月', '8月计划', '4×1200m @3:45-3:50，间歇2分半 + 4×200m @34-35秒；总量18km', '疲劳下速度', 18.00, 'I/R', 'interval_speed', '8月计划', 30, 79, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (80, 1, 13, '2026-08-19', '08.19', '周三', '08月', '8月计划', '上午E 20km + 下午REC 8km', '本周最高有氧日', 28.00, 'REC', 'recovery', '8月计划', 31, 80, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (81, 1, 13, '2026-08-20', '08.20', '周四', '08月', '8月计划', '14km T @3:30-3:36 + 4×100m；总量20-22km', '连续阈值', 21.00, 'T', 'tempo', '8月计划', 32, 81, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (82, 1, 13, '2026-08-21', '08.21', '周五', '08月', '8月计划', 'REC 12km + 力量', '身体检查日', 12.00, 'REC', 'recovery', '8月计划', 33, 82, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (83, 1, 13, '2026-08-22', '08.22', '周六', '08月', '8月计划', '全休', '必须休', 0.00, 'Rest', 'rest', '8月计划', 34, 83, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (84, 1, 13, '2026-08-23', '08.23', '周日', '08月', '8月计划', '28km：前20km E，后8km @3:35-3:45', '半马后程专项', 28.00, 'T', 'tempo', '8月计划', 35, 84, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (85, 1, 14, '2026-08-24', '08.24', '周一', '08月', '8月计划', '上午E 12km + 下午REC 6km', '稍收一点', 18.00, 'REC', 'recovery', '8月计划', 39, 85, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (86, 1, 14, '2026-08-25', '08.25', '周二', '08月', '8月计划', '5×1600m @5:08-5:15，间歇2分半-3分钟；总量20km', '5000/10km专项耐受', 20.00, 'I/R', 'interval_speed', '8月计划', 40, 86, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (87, 1, 14, '2026-08-26', '08.26', '周三', '08月', '8月计划', 'E跑 18-20km', '单跑即可', 19.00, 'E', 'easy', '8月计划', 41, 87, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (88, 1, 14, '2026-08-27', '08.27', '周四', '08月', '8月计划', '2×6km @3:27-3:32，间歇5分钟 + 4×100m；总量22km', '半马专项阈值', 22.00, 'T', 'tempo', '8月计划', 42, 88, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (89, 1, 14, '2026-08-28', '08.28', '周五', '08月', '8月计划', 'REC 12km + 6×100m', '放松', 12.00, 'REC', 'recovery', '8月计划', 43, 89, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (90, 1, 14, '2026-08-29', '08.29', '周六', '08月', '8月计划', '全休', '休息', 0.00, 'Rest', 'rest', '8月计划', 44, 90, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (91, 1, 14, '2026-08-30', '08.30', '周日', '08月', '8月计划', '24-26km @4:10-4:30', '稳态长距离，不冲', 25.00, 'E', 'easy', '8月计划', 45, 91, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (92, 1, 15, '2026-08-31', '08.31', '周一', '08月', '8月计划', 'REC 10km', '回血', 10.00, 'REC', 'recovery', '8月计划', 49, 92, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (93, 1, 15, '2026-09-01', '09.01', '周二', '09月', '8月计划', '8×400m @73-75秒，间歇200m慢跑；总量12-14km', '保速度，不累', 13.00, 'I/R', 'interval_speed', '8月计划', 50, 93, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (94, 1, 15, '2026-09-02', '09.02', '周三', '09月', '8月计划', 'E跑 16km', '不双卡', 16.00, 'E', 'easy', '8月计划', 51, 94, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (95, 1, 15, '2026-09-03', '09.03', '周四', '09月', '8月计划', '8km T @3:30-3:35 + 4×100m；总量14-16km', '保阈值', 15.00, 'T', 'tempo', '8月计划', 52, 95, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (96, 1, 15, '2026-09-04', '09.04', '周五', '09月', '8月计划', 'REC 10-12km', '慢', 11.00, 'REC', 'recovery', '8月计划', 53, 96, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (97, 1, 15, '2026-09-05', '09.05', '周六', '09月', '8月计划', '全休', '休息', 0.00, 'Rest', 'rest', '8月计划', 54, 97, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);
INSERT INTO `planned_workouts` VALUES (98, 1, 15, '2026-09-06', '09.06', '周日', '09月', '8月计划', 'LSD 22-24km', '吸收训练', 23.00, 'LSD', 'long_run', '8月计划', 55, 98, '2026-06-06 12:07:14', '2026-06-06 21:46:42', 1);

-- ----------------------------
-- Table structure for training_blocks
-- ----------------------------
DROP TABLE IF EXISTS `training_blocks`;
CREATE TABLE `training_blocks`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `cycle_id` bigint(0) NOT NULL,
  `block_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `block_type` varchar(16) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'week',
  `week_index` int(0) NULL DEFAULT NULL,
  `sort_order` int(0) NOT NULL,
  `date_range_text` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `target_text` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `target_distance_min_km` decimal(7, 2) NULL DEFAULT NULL,
  `target_distance_max_km` decimal(7, 2) NULL DEFAULT NULL,
  `planned_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `start_date` date NULL DEFAULT NULL,
  `end_date` date NULL DEFAULT NULL,
  `phase_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `focus` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_training_blocks_cycle_sort`(`cycle_id`, `sort_order`) USING BTREE,
  INDEX `ix_training_blocks_cycle_id`(`cycle_id`) USING BTREE,
  INDEX `ix_training_blocks_start_end`(`start_date`, `end_date`) USING BTREE,
  INDEX `ix_training_blocks_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `fk_training_blocks_cycle_id` FOREIGN KEY (`cycle_id`) REFERENCES `training_cycles` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 16 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of training_blocks
-- ----------------------------
INSERT INTO `training_blocks` VALUES (1, 1, 'Week 1：重新启动周', 'week', 1, 1, '6.1-6.7', '目标88-94km', 88.00, 94.00, 92.00, '2026-06-01', '2026-06-07', '6月计划', '恢复接量，重新建立节奏', '2026-06-06 12:07:14', '2026-06-08 15:26:26', 1);
INSERT INTO `training_blocks` VALUES (2, 1, 'Week 2：恢复正常结构', 'week', 2, 2, '6.8 - 6.14', '目标98-104km', 98.00, 104.00, 103.00, '2026-06-08', '2026-06-14', '6月计划', '目标98-104km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (3, 1, 'Week 3：第一次轻峰值', 'week', 3, 3, '6.15 - 6.21', '目标110-116km', 110.00, 116.00, 116.50, '2026-06-15', '2026-06-21', '6月计划', '目标110-116km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (4, 1, 'Week 4：回撤吸收周', 'week', 4, 4, '6.22 - 6.28', '目标80-90km', 80.00, 90.00, 82.00, '2026-06-22', '2026-06-28', '6月计划', '目标80-90km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (5, 1, '6月最后两天', 'transition', NULL, 5, '6.29 - 6.30', '进入7月前激活', NULL, NULL, 27.00, '2026-06-29', '2026-06-30', '6月计划', '进入7月前激活', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (6, 1, 'Week 5：高跑量接入', 'week', 5, 6, '7.1 - 7.5', '目标80-90km', 80.00, 90.00, 76.00, '2026-07-01', '2026-07-05', '7月计划', '目标80-90km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (7, 1, 'Week 6：正式高量周', 'week', 6, 7, '7.6 - 7.12', '目标110-115km', 110.00, 115.00, 118.00, '2026-07-06', '2026-07-12', '7月计划', '目标110-115km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (8, 1, 'Week 7：阈值加厚周', 'week', 7, 8, '7.13 - 7.19', '目标115-120km', 115.00, 120.00, 117.00, '2026-07-13', '2026-07-19', '7月计划', '目标115-120km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (9, 1, 'Week 8：速度唤醒周', 'week', 8, 9, '7.20 - 7.26', '目标120-125km', 120.00, 125.00, 120.50, '2026-07-20', '2026-07-26', '7月计划', '目标120-125km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (10, 1, 'Week 9：回撤周', 'week', 9, 10, '7.27 - 8.2', '目标90-100km', 90.00, 100.00, 91.00, '2026-07-27', '2026-08-02', '7月计划', '目标90-100km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (11, 1, 'Week 10：专项耐受开启', 'week', 10, 11, '8.3 - 8.9', '目标120-125km', 120.00, 125.00, 120.00, '2026-08-03', '2026-08-09', '8月计划', '目标120-125km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (12, 1, 'Week 11：峰值周一', 'week', 11, 12, '8.10 - 8.16', '目标125-132km', 125.00, 132.00, 131.00, '2026-08-10', '2026-08-16', '8月计划', '目标125-132km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (13, 1, 'Week 12：峰值周二', 'week', 12, 13, '8.17 - 8.23', '目标130-135km', 130.00, 135.00, 127.00, '2026-08-17', '2026-08-23', '8月计划', '目标130-135km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (14, 1, 'Week 13：专项压迫周', 'week', 13, 14, '8.24 - 8.30', '目标115-125km', 115.00, 125.00, 116.00, '2026-08-24', '2026-08-30', '8月计划', '目标115-125km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);
INSERT INTO `training_blocks` VALUES (15, 1, 'Week 14：夏训吸收周', 'week', 14, 15, '8.31 - 9.6', '目标90-105km', 90.00, 105.00, 88.00, '2026-08-31', '2026-09-06', '8月计划', '目标90-105km', '2026-06-06 12:07:14', '2026-06-06 21:46:41', 1);

-- ----------------------------
-- Table structure for training_cycles
-- ----------------------------
DROP TABLE IF EXISTS `training_cycles`;
CREATE TABLE `training_cycles`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `goal` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `start_date` date NULL DEFAULT NULL,
  `end_date` date NULL DEFAULT NULL,
  `target_race_name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `target_race_date` date NULL DEFAULT NULL,
  `target_result` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  INDEX `ix_training_cycles_user_id`(`user_id`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 2 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of training_cycles
-- ----------------------------
INSERT INTO `training_cycles` VALUES (1, '2026夏训', '眉山东坡半马 1:11:30', '2026-06-01', '2026-09-06', '眉山东坡半马', '2026-11-08', '1:11:30', '夏季系统训练周期', '2026-06-06 12:06:20', '2026-06-08 15:26:26', 1);

-- ----------------------------
-- Table structure for user_account
-- ----------------------------
DROP TABLE IF EXISTS `user_account`;
CREATE TABLE `user_account`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `username` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `password_hash` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `nickname` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `avatar_url` varchar(512) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `role` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user',
  `status` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active',
  `last_login_at` datetime(0) NULL DEFAULT NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_user_account_username`(`username`) USING BTREE,
  UNIQUE INDEX `uq_user_account_email`(`email`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 4 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of user_account
-- ----------------------------
INSERT INTO `user_account` VALUES (1, 'demo', 'demo@example.com', 'pbkdf2_sha256$260000$ac1d1b9d7e37f74df7ed3cc1bf0f537a$ueJ-mtOgJy3bX4P2i9cZymvgZ_7YLd2pMuZItq8KT5o', 'Demo Runner', NULL, 'user', 'active', '2026-06-08 16:43:36', '2026-06-06 20:49:39', '2026-06-08 16:43:35');
INSERT INTO `user_account` VALUES (2, 'runner_a', 'runner_a@example.com', 'pbkdf2_sha256$260000$a55dadf1033f4f782f244291c89b5470$6y_acBTiUmwZN23IDRk2XkcFBw1s5rKkiH1qdyfY3ws', '严肃跑者 A', NULL, 'user', 'active', NULL, '2026-06-06 20:49:39', '2026-06-06 20:49:39');
INSERT INTO `user_account` VALUES (3, 'runner_b', 'runner_b@example.com', 'pbkdf2_sha256$260000$a353e1c6a3f0df805ed14c438932fb84$eyoM7Q2nxTW-xlbj5i4cWz8X7emNuOgK2rX0S9A6H3A', '严肃跑者 B', NULL, 'user', 'active', NULL, '2026-06-06 20:49:39', '2026-06-06 20:49:39');

-- ----------------------------
-- Table structure for workout_logs
-- ----------------------------
DROP TABLE IF EXISTS `workout_logs`;
CREATE TABLE `workout_logs`  (
  `id` bigint(0) NOT NULL AUTO_INCREMENT,
  `planned_workout_id` bigint(0) NOT NULL,
  `status_raw` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `status_normalized` varchar(32) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'not_started',
  `actual_distance_km` decimal(7, 2) NULL DEFAULT NULL,
  `actual_duration_seconds` int(0) NULL DEFAULT NULL,
  `avg_pace_seconds_per_km` int(0) NULL DEFAULT NULL,
  `avg_heart_rate` int(0) NULL DEFAULT NULL,
  `rpe` int(0) NULL DEFAULT NULL,
  `i_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `t1_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `t2_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `m_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `r_effective_km` decimal(7, 2) NULL DEFAULT NULL,
  `sleep_hours` decimal(4, 2) NULL DEFAULT NULL,
  `hrv` int(0) NULL DEFAULT NULL,
  `morning_heart_rate` int(0) NULL DEFAULT NULL,
  `weight_kg` decimal(5, 2) NULL DEFAULT NULL,
  `leg_feeling` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `pain_location` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL DEFAULT NULL,
  `pain_level` int(0) NULL DEFAULT NULL,
  `main_session_data` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `review_note` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `tomorrow_adjustment` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `alert_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NULL,
  `completion_rate` decimal(5, 2) NULL DEFAULT NULL,
  `created_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0),
  `updated_at` timestamp(0) NOT NULL DEFAULT CURRENT_TIMESTAMP(0) ON UPDATE CURRENT_TIMESTAMP(0),
  `user_id` bigint(0) NOT NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uq_workout_logs_planned_workout`(`planned_workout_id`) USING BTREE,
  INDEX `ix_workout_logs_planned_workout_id`(`planned_workout_id`) USING BTREE,
  INDEX `ix_workout_logs_status_normalized`(`status_normalized`) USING BTREE,
  INDEX `ix_workout_logs_user_id`(`user_id`) USING BTREE,
  CONSTRAINT `fk_workout_logs_planned_workout_id` FOREIGN KEY (`planned_workout_id`) REFERENCES `planned_workouts` (`id`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 99 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of workout_logs
-- ----------------------------
INSERT INTO `workout_logs` VALUES (1, 1, '高质量完成', 'completed_high', 10.20, 3000, 294, 142, 4, 0.00, 0.00, 0.00, 0.00, 0.40, 7.50, 82, 44, 68.80, '轻松', '无', 0, '4×100m 放松加速', '状态不错，控制得比较稳', '明天正常训练', '无', 102.00, '2026-06-06 12:07:14', '2026-06-08 15:26:26', 1);
INSERT INTO `workout_logs` VALUES (2, 2, '高质量完成', 'completed_high', 14.00, 4004, 286, 160, 8, 4.00, 0.00, 0.00, 0.00, 0.00, 7.47, 72, NULL, NULL, '一般', '无', 0, '热身4.2km @4:56，10×400m，组休200米慢跑，实际多数组在70-73，明显快于计划', '速度能力在线，但执行偏快。原本是速度唤醒课，实际跑成高强度400课。后续400控制在目标区间，不抢快。', '10-14km REC/E，不加速，观察小腿跟腱。', NULL, 93.33, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (3, 3, '高质量完成', 'completed_high', 16.00, 4564, 285, 137, 4, 0.00, 0.00, 0.00, 0.00, 0.00, 8.35, 79, NULL, NULL, '沉', '小腿', 1, '16k有氧跑', '稍快于计划', NULL, NULL, 100.00, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (4, 4, '高质量完成', 'completed_high', 16.00, 3508, 246, 164, 7, 2.00, 0.00, 6.00, 0.00, 0.00, 8.00, 75, NULL, NULL, '一般', '足底', 1, '2km@3:29 + 2km@3:28 + 2km@3:24 + 2km@3:07；前两组400m慢跑间歇，第三组后站休2-3分钟，最后一组拆成2×1km。', '实际强度高于原计划。前3组为T2，最后一组偏I强度。心肺压力明显，腿部尚可。下次T课需控制前两组，不把T课跑成测试。', NULL, NULL, 100.00, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (5, 5, '高质量完成', 'completed_high', 12.00, 3300, 288, 137, 4, 0.00, 0.00, 0.00, 0.00, 0.80, 7.00, 86, NULL, 68.80, '一般', '无', 0, '游泳1000米 + 1km540 + 10km436+4×200m（32、32、29、31）', '感觉还行，游泳舒服', NULL, NULL, 120.00, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (6, 6, '休息', 'rest', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, 8.00, 89, NULL, NULL, '轻', '无', 0, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (7, 7, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (8, 8, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (9, 9, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (10, 10, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (11, 11, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (12, 12, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (13, 13, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (14, 14, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (15, 15, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (16, 16, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (17, 17, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (18, 18, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (19, 19, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (20, 20, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (21, 21, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (22, 22, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (23, 23, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (24, 24, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (25, 25, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (26, 26, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (27, 27, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (28, 28, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (29, 29, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (30, 30, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (31, 31, '没完成', 'missed', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (32, 32, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (33, 33, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (34, 34, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (35, 35, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (36, 36, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (37, 37, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (38, 38, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (39, 39, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (40, 40, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (41, 41, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (42, 42, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (43, 43, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (44, 44, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (45, 45, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (46, 46, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (47, 47, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (48, 48, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (49, 49, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (50, 50, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (51, 51, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (52, 52, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (53, 53, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (54, 54, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (55, 55, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (56, 56, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (57, 57, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (58, 58, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (59, 59, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (60, 60, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (61, 61, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (62, 62, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (63, 63, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (64, 64, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (65, 65, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (66, 66, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (67, 67, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (68, 68, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (69, 69, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (70, 70, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (71, 71, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (72, 72, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (73, 73, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (74, 74, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (75, 75, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (76, 76, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (77, 77, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (78, 78, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (79, 79, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (80, 80, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (81, 81, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (82, 82, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (83, 83, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (84, 84, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (85, 85, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (86, 86, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (87, 87, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (88, 88, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (89, 89, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (90, 90, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (91, 91, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (92, 92, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (93, 93, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (94, 94, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (95, 95, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (96, 96, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (97, 97, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);
INSERT INTO `workout_logs` VALUES (98, 98, NULL, 'not_started', NULL, NULL, NULL, NULL, NULL, 0.00, 0.00, 0.00, 0.00, 0.00, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, '2026-06-06 12:07:14', '2026-06-06 21:46:43', 1);

SET FOREIGN_KEY_CHECKS = 1;
