# GaitLogic Planner

GaitLogic Planner 是一个面向严肃跑者的训练计划与训练日志 Web 系统。

系统支持训练计划制定、Excel 标准模板导入、训练日志填写、Dashboard 统计、配速规则、VDOT / 丹尼尔斯配速计算器、AI 课表草稿生成和内测反馈收集，适合跑者把周期计划、每日执行和训练复盘集中管理。

AI 生成内容仅作为训练计划参考，不构成医疗建议或专业教练处方。实际执行前请结合自身状态、伤病情况和专业建议调整。

## 功能列表

- 登录注册
- 多用户数据隔离
- 训练周期管理
- 训练块管理
- 每日训练计划
- 今日训练
- 训练日志填写
- Dashboard
- Excel 标准模板导入
- 配速规则
- VDOT / 丹尼尔斯配速计算器
- 配速档案保存与一键应用到配速规则
- AI 课表草稿生成器
- 内测反馈提交与我的反馈列表

## 技术栈

后端：

- FastAPI
- SQLAlchemy 2.x
- MySQL 8.0+
- PyMySQL
- Pydantic 2.x
- pydantic-settings
- openpyxl
- OpenAI-compatible SDK
- pytest

前端：

- Vue 3
- TypeScript
- Vite
- Element Plus
- ECharts
- Axios

## 截图占位

后续可将截图保存到 `docs/images/`。

![Dashboard](docs/images/dashboard.png)

![今日训练](docs/images/today-workout.png)

![训练计划列表](docs/images/workout-list.png)

![训练日志填写](docs/images/workout-log-edit.png)

![Excel 导入](docs/images/excel-import.png)

![VDOT 配速计算器](docs/images/pace-calculator.png)

![AI 课表](docs/images/ai-plan.png)

![配速规则](docs/images/pace-rules.png)

![系统架构](docs/images/architecture.png)

## 本地运行

### 1. 后端环境准备

在项目根目录安装依赖：

```bash
python -m pip install -e .
```

### 2. 配置 `.env`

复制 `.env.example` 为 `.env`，并按本地环境填写：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=gaitlogic_planner

JWT_SECRET_KEY=please-change-this-to-a-long-random-secret
ACCESS_TOKEN_EXPIRE_DAYS=7

DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=120
AI_PLAN_DAILY_LIMIT=3
AI_PLAN_COOLDOWN_SECONDS=60
```

`JWT_SECRET_KEY` 和 `DEEPSEEK_API_KEY` 必须放在 `.env` 中，不要写入代码或提交到仓库。

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

脚本会创建 `gaitlogic_planner` 数据库并初始化所有表。v0.6 新增了 AI 课表相关表，已有数据库需要重新执行初始化或按 `sql/schema.sql` 补齐新增表。

### 4. 导入示例数据

```bash
python scripts/seed_demo.py
```

### 5. 启动后端

```bash
uvicorn server.main:app --reload
```

后端地址：

```text
http://127.0.0.1:8000
```

Swagger 文档：

```text
http://127.0.0.1:8000/docs
```

### 6. 启动前端

```bash
cd web
npm install
npm run dev
```

前端默认请求：

```text
http://localhost:8000
```

如需调整后端地址，可在前端环境变量中设置：

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Excel 导入说明

系统只支持后端生成的标准 Excel 模板，不兼容任意非标准 Excel。

使用流程：

1. 进入“Excel 导入”页面。
2. 下载标准模板。
3. 按模板填写训练周期、训练块、训练计划、训练日志、每周复盘和配速规则。
4. 上传 `.xlsx` 文件导入。
5. 页面展示导入成功数量、失败数量和错误明细。

上传数据会自动绑定当前登录用户，前端不会传 `user_id`。

## VDOT 配速计算器

配速计算器支持输入比赛距离和比赛成绩，估算近似 VDOT，并生成 REC、E、M、T1、T2、I、R 七类训练配速区间。

用户可以将计算结果保存为个人配速档案，也可以一键应用到当前账号的配速规则中。

## AI 课表草稿生成

AI 课表功能使用 OpenAI-compatible SDK 调用 DeepSeek API。用户填写跑者水平、近期 PB、当前跑量、训练天数、目标赛事、计划周数和强度风格后，系统会生成结构化训练计划草稿。

重要规则：

- AI 只生成草稿，不直接覆盖正式训练计划。
- 用户必须点击“应用为正式计划”后，才会写入训练周期、训练块、训练计划和默认训练日志。
- 每个用户默认每天最多生成 3 次。
- 同一用户两次生成默认至少间隔 60 秒。
- 24 小时内相同输入会优先命中缓存，不重复调用模型。
- 草稿、调用记录和额度均按当前登录用户隔离。

DeepSeek 配置项：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_TIMEOUT_SECONDS=120
AI_PLAN_DAILY_LIMIT=3
AI_PLAN_COOLDOWN_SECONDS=60
```

## 测试

后端：

```bash
python -m compileall -q planner_core server scripts tests
python -m pytest -q
```

前端：

```bash
cd web
npm run build
```

数据库测试只使用 MySQL。如果当前环境无法连接 MySQL，相关集成测试会跳过，不会切换到 SQLite。

## 开发路线

- v0.1 基础训练计划系统
- v0.2 登录注册与多用户
- v0.3 Excel 导入
- v0.4 VDOT 配速计算器
- v0.5 内测与反馈
- v0.6 AI 课表草稿生成器
- v0.7 训练模板库
- v0.8 设备数据同步预留
