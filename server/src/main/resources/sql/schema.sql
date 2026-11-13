-- 智能信息管理与辅助决策系统 · MySQL 初始化脚本
-- 使用方式：mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS triage_support
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE triage_support;

-- ---------------------------------------------------------------------------
-- 伤情处置知识（后端按伤情名称查询处置建议）
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS injury_treatment (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  injury_type    VARCHAR(128) NOT NULL COMMENT '伤情名称',
  classification VARCHAR(32)  NOT NULL COMMENT '处置阶段：现场急救/紧急救治/早期治疗',
  description    TEXT         NOT NULL COMMENT '处置内容',
  create_time    DATETIME     DEFAULT CURRENT_TIMESTAMP,
  update_time    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_injury_type (injury_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='伤情处置建议';

INSERT INTO injury_treatment (injury_type, classification, description) VALUES
('头皮裂伤', '现场急救', '压迫止血，保持伤口清洁，尽快包扎。'),
('头皮裂伤', '紧急救治', '评估有无颅骨骨折及颅内损伤，清创缝合。'),
('胸部撞击伤', '现场急救', '保持呼吸道通畅，观察呼吸与意识，必要时吸氧。'),
('胸部撞击伤', '紧急救治', '完善胸部影像检查，排查气胸、血胸与肋骨骨折。'),
('股动脉损伤', '现场急救', '立即加压包扎或止血带止血，记录时间并尽快转运。'),
('股动脉损伤', '紧急救治', '建立静脉通路，抗休克治疗，尽快手术探查。'),
('下肢皮肤撕脱伤', '现场急救', '覆盖清洁敷料，加压包扎，保护撕脱组织。'),
('下肢皮肤撕脱伤', '紧急救治', '清创、止血、抗感染，评估是否需植皮修复。');

-- ---------------------------------------------------------------------------
-- 患者检伤记录
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patient_medical_info (
  uid                  VARCHAR(64) PRIMARY KEY,
  name                 VARCHAR(64),
  sex                  TINYINT COMMENT '0-未知 1-男 2-女',
  age                  INT,
  blood                VARCHAR(16),
  is_trauma_injury     TINYINT(1) DEFAULT 0,
  head_injury          TINYINT(1) DEFAULT 0,
  left_arm             TINYINT(1) DEFAULT 0,
  right_arm            TINYINT(1) DEFAULT 0,
  left_leg             TINYINT(1) DEFAULT 0,
  right_leg            TINYINT(1) DEFAULT 0,
  chest                TINYINT(1) DEFAULT 0,
  abdomen              TINYINT(1) DEFAULT 0,
  glasgow              INT,
  phi                  INT,
  start_color          VARCHAR(16),
  crams                INT,
  heart_rate           INT,
  systolic_pressure    INT,
  diastolic_pressure   INT,
  respiratory_rate     INT,
  oxygen_saturation    INT,
  temperature          DECIMAL(4,1),
  vital_timestamp      VARCHAR(64),
  suggestion           INT,
  gcs_eye_opening      INT,
  gcs_verbal_response  INT,
  gcs_motor_response   INT,
  phi_systolic_pressure INT,
  phi_pulse            INT,
  phi_breathing        INT,
  phi_consciousness    INT,
  crams_breath         INT,
  crams_chest          INT,
  crams_sport          INT,
  create_time          DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='患者检伤记录';

-- ---------------------------------------------------------------------------
-- 账号与权限
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_account (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  username    VARCHAR(64) NOT NULL UNIQUE,
  password    VARCHAR(255) NOT NULL,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户账号';

CREATE TABLE IF NOT EXISTS sys_role (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  role_name   VARCHAR(64) NOT NULL,
  role_code   VARCHAR(64) NOT NULL UNIQUE,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

CREATE TABLE IF NOT EXISTS sys_permission (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  perm_name   VARCHAR(64) NOT NULL,
  perm_code   VARCHAR(64) NOT NULL UNIQUE,
  path        VARCHAR(255),
  method      VARCHAR(16),
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='权限';

CREATE TABLE IF NOT EXISTS sys_role_permission (
  id            BIGINT AUTO_INCREMENT PRIMARY KEY,
  role_id       BIGINT NOT NULL,
  permission_id BIGINT NOT NULL,
  UNIQUE KEY uk_role_perm (role_id, permission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色-权限';

CREATE TABLE IF NOT EXISTS sys_user_role (
  id      BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  role_id BIGINT NOT NULL,
  UNIQUE KEY uk_user_role (user_id, role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户-角色';

CREATE TABLE IF NOT EXISTS sys_operation_log (
  id             BIGINT AUTO_INCREMENT PRIMARY KEY,
  username       VARCHAR(64),
  request_method VARCHAR(16),
  request_path   VARCHAR(255),
  client_ip      VARCHAR(64),
  status_code    INT,
  message        VARCHAR(512),
  create_time    DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY idx_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志';

-- ---------------------------------------------------------------------------
-- 演示数据
-- 账号：admin / admin123（仅用于本地演示，部署前请修改）
-- ---------------------------------------------------------------------------
INSERT INTO user_account (id, username, password) VALUES
(1, 'admin', 'pbkdf2$120000$lM0wrrtV9UTSPnwro+W0cA==$yHrltczU8aJcsNwPqsmAVpeYnRrSxujHOuBVj9ynR2w=');

INSERT INTO sys_role (id, role_name, role_code) VALUES
(1, '管理员', 'ADMIN');

INSERT INTO sys_user_role (user_id, role_id) VALUES (1, 1);

INSERT INTO sys_permission (perm_name, perm_code, path, method) VALUES
('患者管理', 'assessment:manage', '/api/assessments/**', '*'),
('知识库管理', 'knowledge:manage', '/api/admin/knowledge/**', '*'),
('系统管理', 'system:manage', '/api/admin/**', '*');

INSERT INTO sys_role_permission (role_id, permission_id) VALUES
(1, 1), (1, 2), (1, 3);
