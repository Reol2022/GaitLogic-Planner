# Gaitlogic Planner

Gaitlogic Planner 是一个面向严肃跑者的训练计划与训练日志 Web 系统。当前 v0.1 覆盖 MySQL 数据库层和 FastAPI 后端接口，围绕训练计划制定、训练日志、周/月统计基础数据和配速规则管理。

数据库设计以最新版 Excel《严飞_夏训计划与训练日志_下拉样式版.xlsx》的四个核心 Sheet 为来源：

- 计划索引
- 训练日志
- 每周复盘
- 配速与规则

## 技术栈

- Python 3.11+
- MySQL 8.0+
- SQLAlchemy 2.x
- PyMySQL
- Pydantic 2.x
- pydantic-settings
- pytest
- FastAPI
- Uvicorn

## MySQL 环境要求

- 数据库名：`gaitlogic_planner`
- 字符集：`utf8mb4`
- 默认排序规则：`utf8mb4_unicode_ci`
- 表引擎：`InnoDB`
- 主键：`BIGINT AUTO_INCREMENT`
- 不使用 SQLite
- 不使用 Alembic

## 配置方式

复制 `.env.example` 为 `.env`，并按本地 MySQL 环境填写：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=gaitlogic_planner
```

## 初始化数据库

```bash
python scripts/init_db.py
```

脚本会连接 MySQL。如果数据库不存在，会创建 `gaitlogic_planner`，然后初始化所有表。

## 写入示例数据

```bash
python scripts/seed_demo.py
```

示例数据包括：

- 训练周期：`2026夏训`
- 训练周期目标：`眉山东坡半马 1:11:30`
- 三个训练块：`Week 1：重新启动周`、`Week 2：恢复正常结构`、`6月最后两天`
- 多条计划训练课及默认 `not_started` 训练日志
- `R`、`I`、`T2`、`T1`、`M`、`E`、`REC`、`LSD` 配速规则

## 当前 MVP 范围

- 训练周期
- 训练块
- 计划训练课
- 训练日志
- 训练块复盘
- 配速规则
- Excel 导入任务记录

当前不实现 Excel 解析、FastAPI 业务接口、前端业务、Garmin 同步、AI 教练、App、小程序、多用户 SaaS 或社交功能。

## 测试

```bash
pytest
```

测试只使用 MySQL。若当前环境无法连接 MySQL，数据库集成测试会跳过，不会切换到 SQLite。

## 启动后端 API

```bash
uvicorn server.main:app --reload
```

启动后可打开 `/docs` 查看 FastAPI Swagger 文档。所有业务接口都以 `/api` 开头。

## 启动前端

```bash
cd web
npm install
npm run dev
```

前端默认请求 `http://localhost:8000`。如需调整后端地址，可设置 `VITE_API_BASE_URL`。
