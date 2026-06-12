-- ============================================================
-- AI 智能客服系统 — 数据库初始化脚本
-- 数据库：MySQL 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS simplerag
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE simplerag;

-- -----------------------------------------------------------
-- 1. 用户表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INT           AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    email       VARCHAR(255)  NOT NULL COMMENT '邮箱，登录凭据',
    password_hash VARCHAR(255) NOT NULL COMMENT 'bcrypt 哈希密码',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表';

-- -----------------------------------------------------------
-- 2. 会话表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id          INT           AUTO_INCREMENT PRIMARY KEY COMMENT '会话ID',
    user_id     INT           NOT NULL COMMENT '所属用户',
    thread_id   VARCHAR(64)   NOT NULL COMMENT 'LangChain/LangGraph 线程ID，用于管理短期记忆',
    title       VARCHAR(100)  NULL COMMENT '会话标题',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后活跃时间',

    UNIQUE INDEX idx_thread_id (thread_id),
    INDEX idx_user_id (user_id),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='会话表';

-- -----------------------------------------------------------
-- 3. 知识库文档表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_docs (
    id                INT           AUTO_INCREMENT PRIMARY KEY COMMENT '文档ID',
    file_path         VARCHAR(500)  NOT NULL COMMENT 'knowledges/ 下的相对路径，如 auperator/README.md',
    original_filename VARCHAR(255)  NOT NULL COMMENT '原始文件名，前端展示用',
    file_size         INT           NOT NULL DEFAULT 0 COMMENT '文件大小（字节）',
    content_hash      VARCHAR(64)   NOT NULL COMMENT '文件 MD5，用于重复检测',
    status            VARCHAR(20)   NOT NULL DEFAULT 'processing' COMMENT '处理状态：processing / ready / failed',
    chunk_count       INT           NOT NULL DEFAULT 0 COMMENT '分块数量',
    error_message     TEXT          NULL COMMENT '失败时的错误信息',
    created_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    updated_at        DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    UNIQUE INDEX idx_file_path (file_path),
    INDEX idx_content_hash (content_hash),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='知识库文档表';
