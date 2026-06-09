# GaitLogic Planner

GaitLogic Planner 是一个面向严肃跑者的训练计划与训练日志 Web 系统。

系统支持训练计划制定、Excel 标准模板导入、训练日志填写、Dashboard 统计、配速规则、VDOT / 丹尼尔斯配速计算器和内测反馈收集，适合跑者把周期计划、每日执行和训练复盘集中管理。

当前版本聚焦内测可用，不包含 Garmin 同步、AI 教练、App、小程序、社交、支付或复杂训练计划自动生成。

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

![配速规则](docs/images/pace-rules.png)

![系统架构](docs/images/architecture.png)

## 本地运行

### 1. 后端环境准备

在项目根目录安装依赖：

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

JWT_SECRET_KEY=please-change-this-to-a-long-random-secret
ACCESS_TOKEN_EXPIRE_DAYS=7
```

`JWT_SECRET_KEY` 必须替换为自己的长随机字符串，不要使用示例值。

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

脚本会创建 `gaitlogic_planner` 数据库并初始化所有表。已有数据库不会被删除。

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
- v0.6 训练模板库
- v0.7 设备数据同步预留
