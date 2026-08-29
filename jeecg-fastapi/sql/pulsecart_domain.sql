-- PulseCart P1 领域表
-- 用法：在 jeecg-boot 数据库中执行本文件；不会删除或修改 sys_* 系统表。
USE `jeecg-boot`;

CREATE TABLE IF NOT EXISTS `pc_dataset_import` (
  `id` varchar(32) NOT NULL,
  `dataset_version` varchar(40) NOT NULL,
  `source_filename` varchar(255) NOT NULL,
  `file_sha256` varchar(64) NOT NULL,
  `storage_path` varchar(500) DEFAULT NULL,
  `status` varchar(24) NOT NULL DEFAULT 'validated',
  `mapping_json` text NOT NULL,
  `quality_rules_json` text NOT NULL,
  `rejection_reasons_json` text NOT NULL,
  `received_rows` int NOT NULL DEFAULT 0,
  `valid_rows` int NOT NULL DEFAULT 0,
  `rejected_rows` int NOT NULL DEFAULT 0,
  `created_by` varchar(32) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pc_dataset_version` (`dataset_version`),
  KEY `idx_pc_dataset_sha` (`file_sha256`),
  KEY `idx_pc_dataset_creator` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PulseCart 数据集导入版本';

CREATE TABLE IF NOT EXISTS `pc_review` (
  `id` varchar(32) NOT NULL,
  `dataset_version` varchar(40) NOT NULL,
  `review_id` varchar(128) NOT NULL,
  `product_id` varchar(128) NOT NULL,
  `category_id` varchar(128) DEFAULT NULL,
  `review_text` text NOT NULL,
  `reviewed_at` datetime NOT NULL,
  `channel` varchar(128) DEFAULT NULL,
  `rating` int DEFAULT NULL,
  `product_version` varchar(64) DEFAULT NULL,
  `language` varchar(16) NOT NULL DEFAULT 'unknown',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pc_review_dataset_review` (`dataset_version`, `review_id`),
  KEY `idx_pc_review_dataset` (`dataset_version`),
  KEY `idx_pc_review_product` (`product_id`),
  KEY `idx_pc_review_time` (`reviewed_at`),
  KEY `idx_pc_review_version` (`product_version`),
  KEY `idx_pc_review_channel` (`channel`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PulseCart 原始评论规范化记录';

CREATE TABLE IF NOT EXISTS `pc_review_task` (
  `id` varchar(32) NOT NULL,
  `task_id` varchar(64) NOT NULL,
  `dataset_version` varchar(40) NOT NULL,
  `review_id` varchar(128) NOT NULL,
  `sampling_group` varchar(40) NOT NULL,
  `sampling_reason` varchar(80) NOT NULL,
  `assigned_role` varchar(64) NOT NULL DEFAULT 'product_operator',
  `review_status` varchar(24) NOT NULL DEFAULT 'pending',
  `model_version` varchar(80) DEFAULT NULL,
  `system_sentiment` varchar(16) DEFAULT NULL,
  `system_aspects_json` text NOT NULL,
  `system_confidence` double DEFAULT NULL,
  `reviewer_sentiment` varchar(16) DEFAULT NULL,
  `reviewer_aspects_json` text NOT NULL,
  `reviewer_note` text NOT NULL,
  `reviewer_id` varchar(32) DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_pc_review_task` (`task_id`),
  KEY `idx_pc_review_task_dataset` (`dataset_version`),
  KEY `idx_pc_review_task_review` (`review_id`),
  KEY `idx_pc_review_task_status` (`review_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PulseCart 人工审核任务';

CREATE TABLE IF NOT EXISTS `pc_analysis_run` (
  `id` varchar(32) NOT NULL,
  `dataset_version` varchar(40) NOT NULL,
  `model_version` varchar(80) NOT NULL,
  `status` varchar(24) NOT NULL DEFAULT 'queued',
  `source_kind` varchar(32) NOT NULL DEFAULT 'human_reviewed',
  `metrics_json` text NOT NULL,
  `error_message` text DEFAULT NULL,
  `created_by` varchar(32) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `started_at` datetime DEFAULT NULL,
  `finished_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_pc_analysis_dataset` (`dataset_version`),
  KEY `idx_pc_analysis_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PulseCart 分析运行';

CREATE TABLE IF NOT EXISTS `pc_issue` (
  `id` varchar(32) NOT NULL,
  `dataset_version` varchar(40) NOT NULL,
  `title` varchar(255) NOT NULL,
  `aspect` varchar(80) NOT NULL,
  `severity` varchar(16) NOT NULL DEFAULT 'medium',
  `status` varchar(24) NOT NULL DEFAULT 'open',
  `description` text NOT NULL,
  `source_review_ids_json` text NOT NULL,
  `owner_user_id` varchar(32) DEFAULT NULL,
  `resolution_note` text DEFAULT NULL,
  `created_by` varchar(32) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_pc_issue_dataset` (`dataset_version`),
  KEY `idx_pc_issue_aspect` (`aspect`),
  KEY `idx_pc_issue_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='PulseCart 商品体验问题卡片';
