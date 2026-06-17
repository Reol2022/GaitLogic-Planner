# 贡献指南

感谢你愿意参与 GaitLogic Planner。这个项目面向严肃跑者，贡献时请优先考虑数据安全、训练安全和长期可维护性。

## 开发环境

### 后端

要求：

- Python 3.11+
- MySQL 8.0+
- PyMySQL

安装依赖并初始化数据库：

```bash
python -m pip install -e .
python scripts/init_db.py
```

启动后端：

```bash
uvicorn server.main:app --reload
```

后端文档默认地址：

```text
http://127.0.0.1:8000/docs
```

### 前端

要求：

- Node.js LTS
- npm

```bash
cd web
npm install
npm run dev
```

前端默认通过 `/api` 访问后端。开发代理可通过 `VITE_DEV_API_PROXY_TARGET` 配置。

## 分支和提交规范

推荐分支命名：

- `fix/short-description`
- `feat/short-description`
- `docs/short-description`
- `test/short-description`

提交信息建议使用简洁前缀：

- `fix: 修复训练日历状态显示`
- `feat: 增加快速打卡入口`
- `docs: 补充部署说明`
- `test: 增加 AI 输出校验测试`
- `chore: 更新忽略规则`

一个 Pull Request 尽量只解决一个主要问题。避免把格式化、重构和功能改动混在一起。

## Issue 流程

提交 Bug 时请包含：

- 问题描述；
- 复现步骤；
- 预期结果；
- 实际结果；
- 后端或前端版本；
- 浏览器、操作系统和数据库环境；
- 脱敏后的日志或截图。

提交功能建议时请说明：

- 使用场景；
- 目标用户；
- 为什么现有功能不能满足；
- 可能影响的数据表、API 或页面；
- 是否涉及训练安全逻辑。

## Pull Request 流程

PR 描述应包含：

- 改动摘要；
- 关联 Issue；
- 测试方式；
- 是否影响数据库；
- 是否影响 API；
- 是否影响前端路由或移动端；
- 是否涉及 AI、训练安全或权限隔离；
- 是否使用 AI 工具辅助生成或大幅修改代码。

PR 合并前应确保：

```bash
python -m compileall -q planner_core server scripts tests
python -m pytest -q
```

如果修改了前端，还应运行：

```bash
cd web
npm run build
```

如果本地没有可用 MySQL，允许跳过真实数据库集成测试，但不能跳过纯结构、解析、Prompt 和服务逻辑测试。

## 数据库迁移要求

当前项目没有引入 Alembic。涉及数据库结构变更时：

1. 更新 SQLAlchemy Models；
2. 更新 `sql/schema.sql`；
3. 新增或更新 `scripts/upgrade_*.py` 升级脚本；
4. 更新 `.env.example` 或部署文档中新增的配置；
5. 补充模型或服务测试；
6. 在 PR 中明确写出迁移步骤和回滚风险。

不要在业务代码启动时隐式改表。生产环境升级必须通过明确脚本执行。

## AI 辅助代码披露

允许使用 AI 工具辅助开发，但贡献者必须对最终代码负责。

如果 AI 参与了核心实现、复杂重构、训练逻辑或安全相关代码，请在 PR 中说明：

- 使用了 AI 辅助；
- AI 参与的范围；
- 人工审查和测试方式。

不得将以下内容发送给第三方模型：

- 生产 API Key、JWT Secret、数据库密码；
- 真实用户训练日志；
- 真实健康、伤病、联系方式；
- 私有 Prompt、商业策略或未公开训练模板。

不得复制来源和许可证不明确的代码。

## 数据与密钥

禁止提交：

- `.env` 和任何真实环境配置；
- API Key、Token、JWT Secret、数据库密码；
- 生产数据库导出；
- 日志文件；
- 上传文件；
- 未脱敏的用户训练数据；
- 真实邮箱、手机号、身份证明或精确位置。

测试数据必须虚构或不可逆匿名化。

## 训练安全原则

涉及训练计划、强度、跑量、恢复、AI 生成规则的改动，应遵守：

- 不承诺一定 PB 或避免受伤；
- 不鼓励带伤硬顶；
- 不把软件输出描述为医疗诊断；
- 不默认连续安排高强度训练；
- 有伤病风险时优先降低强度和跑量；
- AI 训练计划只能作为草稿，用户确认后才应用。

更多治理规则见 [OPEN_SOURCE_POLICY.md](OPEN_SOURCE_POLICY.md)。
