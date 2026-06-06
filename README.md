# GaitLogic Planner

GaitLogic Planner 是一个面向严肃跑者的训练计划与训练日志 Web 系统，用于管理训练周期、训练块、每日训练安排、训练日志、Dashboard 统计和配速规则。

当前版本聚焦基础训练计划系统，不包含 Excel 解析、Garmin 同步、AI 教练、App、小程序或社交功能。

## 当前功能

- 训练周期管理
- 训练块管理
- 每日训练计划
- 今日训练
- 训练日志填写
- Dashboard
- 配速规则

## 界面截图

> 以下为截图预留位置，后续可将对应页面截图保存到 `docs/images/`。

### Dashboard

![Dashboard](docs/images/dashboard.png)

### 今日训练

![今日训练](docs/images/today-workout.png)

### 训练计划列表

![训练计划列表](docs/images/workout-list.png)

### 训练日志填写

![训练日志填写](docs/images/workout-log-edit.png)

### 配速规则

![配速规则](docs/images/pace-rules.png)

### 系统架构

![系统架构](docs/images/architecture.png)

### 数据库 ER 图

![数据库 ER 图](docs/images/database-er.png)

## 技术栈

### 后端

- FastAPI
- SQLAlchemy 2.x
- MySQL 8.0+
- PyMySQL
- Pydantic 2.x
- pydantic-settings
- pytest

### 前端

- Vue 3
- TypeScript
- Vite
- Element Plus
- Axios
- ECharts

## MySQL 环境要求

- 数据库名：`gaitlogic_planner`
- 字符集：`utf8mb4`
- 默认排序规则：`utf8mb4_unicode_ci`
- 表引擎：`InnoDB`
- 不使用 SQLite
- 不使用 Alembic

## 本地运行

### 1. 安装后端依赖

在项目根目录执行：

```bash
pip install -e .
```

如果电脑上有多个 Python 版本，也可以指定 Python 3.11：

```bash
python -m pip install -e .
```

### 2. 配置 `.env`

复制 `.env.example` 为 `.env`，并按本地 MySQL 环境填写：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=gaitlogic_planner
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

脚本会连接 MySQL。如果数据库不存在，会创建 `gaitlogic_planner`，然后初始化所有表。

### 4. 导入测试数据

```bash
python scripts/seed_demo.py
```

示例数据包括训练周期、训练块、计划训练课、默认训练日志和配速规则。

### 5. 启动后端

```bash
uvicorn server.main:app --reload
```

后端默认地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

### 6. 启动前端

进入前端目录：

```bash
cd web
npm install
npm run dev
```

前端默认请求后端：

```text
http://localhost:8000
```

如需调整后端地址，可设置：

```env
VITE_API_BASE_URL=http://localhost:8000
```

## 测试

```bash
pytest
```

测试只使用 MySQL。若当前环境无法连接 MySQL，数据库集成测试会跳过，不会切换到 SQLite。

前端构建：

```bash
cd web
npm run build
```

## 开发路线

- v0.1 基础训练计划系统
- v0.2 登录注册与多用户
- v0.3 Excel 导入
- v0.4 丹尼尔斯配速计算器
- v0.5 设备数据同步预留

## 项目边界

当前阶段优先保证训练计划、训练日志和统计复盘的基础能力。暂不实现 Garmin 同步、AI 教练、App、小程序、社交功能和 Excel 上传解析。
