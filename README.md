# GaitLogic Planner

GaitLogic Planner 是一个面向严肃跑者的训练计划与训练日志 Web 系统，用于管理训练周期、训练块、每日训练计划、今日训练、训练日志、Dashboard 统计、配速规则和标准 Excel 导入。

当前版本聚焦基础训练计划系统、账号数据隔离和标准模板导入，不包含 Garmin 同步、AI 教练、App、小程序或社交功能。

## 当前功能

- 登录注册与 JWT Bearer Token
- 多用户训练数据隔离
- 训练周期管理
- 训练块管理
- 每日训练计划
- 今日训练
- 训练日志填写
- Dashboard
- 配速规则
- 标准 Excel 模板下载
- 标准 Excel 上传导入

## Excel 导入

系统只支持由后端生成的标准 Excel 模板，不兼容任意非标准 Excel。

使用流程：

1. 进入前端“Excel 导入”页面。
2. 点击“下载标准模板”。
3. 按模板填写训练周期、训练块、训练计划、训练日志、每周复盘和配速规则。
4. 上传 `.xlsx` 文件。
5. 后端校验 Sheet 名称和表头。
6. 校验通过后写入当前登录用户的数据。
7. 页面展示总行数、成功数、失败数和错误明细。

模板包含以下 Sheet：

- 填写说明
- 训练周期
- 训练块
- 训练计划
- 训练日志
- 每周复盘
- 配速规则

导入注意事项：

- 请不要修改 Sheet 名称。
- 请不要修改表头名称。
- 一个 Excel 文件暂时只读取第一条有效训练周期。
- 训练计划通过“训练块名称”匹配训练块。
- 训练日志通过“日期”匹配训练计划。
- 每周复盘通过“训练块名称”匹配训练块。
- 同一用户下重复的配速规则代号会更新，不会重复创建。
- 上传数据会自动绑定当前登录用户，前端不传 `user_id`。

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

### Excel 导入

![Excel 导入](docs/images/excel-import.png)

### 系统架构

![系统架构](docs/images/architecture.png)

### 数据库 ER 图

![数据库 ER 图](docs/images/database-er.png)

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
- Axios
- ECharts

## MySQL 环境要求

- 数据库名：`gaitlogic_planner`
- 字符集：`utf8mb4`
- 默认排序规则：`utf8mb4_unicode_ci`
- 表引擎：`InnoDB`
- 不使用 SQLite
- 不引入 Alembic

## 本地运行

### 1. 安装后端依赖

在项目根目录执行：

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
```

`JWT_SECRET_KEY` 必须替换为自己的长随机字符串，不能使用示例值。

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

脚本会连接 MySQL。如果数据库不存在，会创建 `gaitlogic_planner`，然后初始化所有表。

### 4. 导入示例数据

```bash
python scripts/seed_demo.py
```

示例数据包含一个 demo 用户、训练周期、训练块、计划训练课、默认训练日志和配速规则。

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

后端测试：

```bash
python -m pytest -q
```

前端构建：

```bash
cd web
npm run build
```

测试只使用 MySQL。如果当前环境无法连接 MySQL，数据库集成测试会跳过，不会切换到 SQLite。

## 开发路线

- v0.1 基础训练计划系统
- v0.2 登录注册与多用户
- v0.3 Excel 导入
- v0.4 丹尼尔斯配速计算器
- v0.5 设备数据同步预留
