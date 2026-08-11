# GaitLogic Planner 部署文档

[返回项目首页](../README.md) · [返回文档中心](README.md)

本文档记录 GaitLogic Planner 的生产环境部署方式。
主项目介绍请查看：[README.md](../README.md)。

---

## 部署结构

推荐使用以下部署结构：

```text
用户浏览器
    ↓
Nginx
    ├── /        -> 前端静态资源 dist
    └── /api/    -> FastAPI 后端服务 127.0.0.1:8000
```

建议：

* 前端使用 `npm run build` 构建后由 Nginx 托管；
* 后端使用 `gunicorn + uvicorn worker` 运行；
* 后端只监听 `127.0.0.1:8000`；
* 由 Nginx 统一对外暴露 80 / 443 端口；
* 不建议生产环境直接暴露 Vite 的 `5173` 端口。

---

## 1. 后端环境准备

进入项目根目录：

```bash
cd /www/wwwroot/gaitlogic-planner
```

创建虚拟环境：

```bash
python3.11 -m venv .venv
```

安装依赖：

```bash
.venv/bin/python -m pip install -U pip setuptools wheel
.venv/bin/python -m pip install -e .
```

如果使用 Excel 上传和 AI 课表功能，确认安装：

```bash
.venv/bin/python -m pip install python-multipart openai
```

---

## 2. 配置后端环境变量

复制环境变量文件：

```bash
cp .env.example .env
```

示例配置：

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
TRAINING_READINESS_ROLLOUT_MODE=off
AI_READINESS_EXPLANATION_ENABLED=false
```

注意：

* `JWT_SECRET_KEY` 必须使用足够长的随机字符串；
* `DEEPSEEK_API_KEY` 不要提交到仓库；
* `TRAINING_READINESS_ROLLOUT_MODE` 允许 `off`、`allowlist`、`all`，生产升级后应先保持 `off`；
* `AI_READINESS_EXPLANATION_ENABLED` v0.9 默认保持 `false`，本版本不新增 AI 训练状态解释调用；
* 生产环境建议将 `.env` 加入 `.gitignore`。

---

## 3. 初始化数据库

执行：

```bash
.venv/bin/python scripts/init_db.py
```

如果需要导入示例数据：

```bash
.venv/bin/python scripts/seed_demo.py
```

---

## 4. 手动测试后端

先手动启动一次，确认后端可以正常运行：

```bash
cd /www/wwwroot/gaitlogic-planner

.venv/bin/python -m gunicorn server.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 2 \
  -b 127.0.0.1:8000 \
  --timeout 180 \
  --access-logfile - \
  --error-logfile -
```

另开终端测试：

```bash
curl -I http://127.0.0.1:8000/docs
```

如果能返回响应，说明后端服务正常。

---

## 5. 使用 Supervisor 托管后端

示例配置：

```ini
[program:gaitlogic-planner]
directory=/www/wwwroot/gaitlogic-planner
command=/www/wwwroot/gaitlogic-planner/.venv/bin/python -m gunicorn server.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 127.0.0.1:8000 --timeout 180 --access-logfile /www/wwwroot/gaitlogic-planner/logs/api-access.log --error-logfile /www/wwwroot/gaitlogic-planner/logs/api-error.log
autostart=true
autorestart=true
startsecs=5
startretries=3
user=root
environment=PYTHONPATH="/www/wwwroot/gaitlogic-planner"

stdout_logfile=/www/wwwroot/gaitlogic-planner/logs/supervisor.out.log
stderr_logfile=/www/wwwroot/gaitlogic-planner/logs/supervisor.err.log
stdout_logfile_maxbytes=20MB
stderr_logfile_maxbytes=20MB
stdout_logfile_backups=5
stderr_logfile_backups=5
redirect_stderr=false
```

创建日志目录：

```bash
mkdir -p /www/wwwroot/gaitlogic-planner/logs
```

重载 Supervisor：

```bash
supervisorctl reread
supervisorctl update
supervisorctl restart gaitlogic-planner
```

查看状态：

```bash
supervisorctl status
```

查看日志：

```bash
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/api-error.log
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/api-access.log
```

---

## 6. 前端构建

进入前端目录：

```bash
cd /www/wwwroot/gaitlogic-planner/web
```

安装依赖：

```bash
npm install
```

配置生产环境 API 地址。

`.env.production`：

```env
VITE_API_BASE_URL=/api
```

构建：

```bash
npm run build
```

构建后会生成：

```text
web/dist
```

---

## 7. Nginx 配置

假设前端构建产物在：

```text
/www/wwwroot/gaitlogic-planner/web/dist
```

后端监听：

```text
127.0.0.1:8000
```

### 后端接口本身带 `/api` 前缀

如果后端真实接口是：

```text
http://127.0.0.1:8000/api/auth/me
```

则 Nginx 配置如下：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /www/wwwroot/gaitlogic-planner/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 后端接口本身不带 `/api` 前缀

如果后端真实接口是：

```text
http://127.0.0.1:8000/auth/me
```

则 Nginx 配置如下：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /www/wwwroot/gaitlogic-planner/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

区别：

```text
proxy_pass http://127.0.0.1:8000;
```

会保留 `/api/` 前缀。

```text
proxy_pass http://127.0.0.1:8000/;
```

会去掉 `/api/` 前缀。

---

## 8. 重载 Nginx

检查配置：

```bash
nginx -t
```

重载：

```bash
nginx -s reload
```

---

## 9. 部署后验证

检查后端端口：

```bash
ss -lntp | grep 8000
```

正常情况下应该看到：

```text
127.0.0.1:8000
```

测试后端本机访问：

```bash
curl -I http://127.0.0.1:8000/docs
```

测试 Nginx 反向代理：

```bash
curl -I http://your-domain.com/api/auth/me
```

如果返回 `401`，通常说明接口路径是通的，只是未登录。

如果返回 `404`，优先检查：

* 后端接口是否带 `/api` 前缀；
* Nginx 的 `proxy_pass` 后面是否应该带 `/`；
* 前端请求是否变成了 `/api/api/...`。

---

## 10. 常见问题

### 10.1 Supervisor 显示 RUNNING，但 8000 端口没占用

检查 Supervisor 实际启动命令：

```bash
supervisorctl status
supervisorctl pid gaitlogic-planner
ps -ww -o pid,ppid,user,stat,etime,cmd -p <PID>
```

确认命令中包含：

```text
-k uvicorn.workers.UvicornWorker
-b 127.0.0.1:8000
```

也可以查看完整命令：

```bash
tr '\0' ' ' < /proc/<PID>/cmdline
echo
```

---

### 10.2 外网访问不到 8000 端口

如果后端绑定的是：

```text
127.0.0.1:8000
```

外网不能直接访问，这是正常的。

生产环境建议通过 Nginx 访问：

```text
http://your-domain.com/api/...
```

而不是直接访问：

```text
http://your-domain.com:8000/...
```

---

### 10.3 前端请求 `localhost:8000` 报错

浏览器中的 `localhost` 指用户自己的电脑，不是服务器。

生产环境前端应配置：

```env
VITE_API_BASE_URL=/api
```

Axios 示例：

```ts
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 120000,
});
```

业务接口建议写成：

```ts
client.get("/auth/me");
```

不要写成：

```ts
client.get("/api/auth/me");
```

否则最终可能变成：

```text
/api/api/auth/me
```

---

### 10.4 上传 Excel 报缺少 `python-multipart`

安装：

```bash
/www/wwwroot/gaitlogic-planner/.venv/bin/python -m pip install python-multipart
```

然后重启后端：

```bash
supervisorctl restart gaitlogic-planner
```

---

### 10.5 AI 课表提示 OpenAI-compatible SDK 未安装

安装：

```bash
/www/wwwroot/gaitlogic-planner/.venv/bin/python -m pip install openai
```

并确认 `.env` 中配置了：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

重启后端：

```bash
supervisorctl restart gaitlogic-planner
```

---

### 10.6 查看运行日志

后端错误日志：

```bash
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/api-error.log
```

后端访问日志：

```bash
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/api-access.log
```

Supervisor 日志：

```bash
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/supervisor.err.log
tail -n 100 /www/wwwroot/gaitlogic-planner/logs/supervisor.out.log
```

---

## 11. 更新部署

后续代码更新后，一般流程：

```bash
cd /www/wwwroot/gaitlogic-planner

git pull

.venv/bin/python -m pip install -e .

.venv/bin/python scripts/init_db.py

cd web
npm install
npm run build

nginx -t && nginx -s reload

supervisorctl restart gaitlogic-planner
```

如果数据库结构没有变化，可以不执行 `scripts/init_db.py`。

---

## 12. v0.9 负荷与恢复灰度上线

生产上线建议流程：

1. 备份 MySQL 数据库；
2. 确认 `.env` 中 `TRAINING_READINESS_ROLLOUT_MODE=off`；
3. 执行正式迁移：

```bash
.venv/bin/python scripts/upgrade_v09_training_readiness.py
```

4. 部署后端；
5. 部署前端；
6. 保持功能关闭，检查日志和数据库表；
7. 使用内部账号授予白名单：

```bash
.venv/bin/python scripts/manage_feature_access.py grant <username_or_user_id>
.venv/bin/python scripts/manage_feature_access.py list
```

8. 将 `.env` 改为：

```env
TRAINING_READINESS_ROLLOUT_MODE=allowlist
```

9. 重启后端，使用内部账号验证恢复打卡、训练状态和周复盘集成；
10. 开启 5-10 名灰度用户，连续观察至少 7 天；
11. 确认无异常后再决定是否改为 `TRAINING_READINESS_ROLLOUT_MODE=all`。

功能关闭时返回 `404 FEATURE_DISABLED`；灰度未开放时返回 `403 FEATURE_NOT_AVAILABLE`；真实服务异常才返回 `503`。

疼痛量表迁移说明：

```text
历史训练日志 0-5 疼痛值 -> 0-10：new_value = old_value × 2
```

迁移后的历史值通过 `pain_scale_version=normalized_0_10` 标记，不应描述为重新测量。

---

## 13. v0.10.3 Runner State 与 Garmin 自动快照迁移

部署 v0.10.3 前必须备份目标数据库，并先在与生产版本一致的隔离 MySQL 环境验证 upgrade、应用启动和 downgrade。不要在生产环境重复执行迁移，也不要把测试账号、测试库名或数据库凭据写入仓库。

升级顺序固定为：

```bash
.venv/bin/python scripts/upgrade_v0103_runner_state_snapshots.py upgrade
.venv/bin/python scripts/upgrade_v0103_garmin_sync_material_change.py upgrade
.venv/bin/python scripts/upgrade_v0103_runner_state_snapshot_receipts.py upgrade
```

如需在隔离验证环境回滚，必须严格反序执行：

```bash
.venv/bin/python scripts/upgrade_v0103_runner_state_snapshot_receipts.py downgrade
.venv/bin/python scripts/upgrade_v0103_garmin_sync_material_change.py downgrade
.venv/bin/python scripts/upgrade_v0103_runner_state_snapshots.py downgrade
```

运行语义：

- Garmin 同步训练事实使用主事务 Session A；只有 Session A 完成后，Pipeline 才进入自动快照后置处理。
- Runner State 自动快照使用独立 Session B；Session B 失败必须 rollback 并关闭，但不得回滚 Session A 或改变同步 Job 终态。
- 自动快照失败采用非阻塞结果；`FAILED_NON_BLOCKING` 不应被展示为 Garmin 同步失败。
- BackgroundTask 与轮询 Worker 必须继续只调用统一 `ActivitySyncPipeline`，不得在路由、任务或 Worker 中增加第二个快照入口。

---

## 14. 安全建议

生产环境建议：

* 不要提交 `.env`；
* 不要将后端 8000 端口直接暴露到公网；
* 使用 HTTPS；
* 定期备份 MySQL 数据；
* 为 demo 账号限制权限或定期重置数据；
* DeepSeek / OpenAI-compatible API Key 仅保存在服务端；
* 前端不要出现任何真实 API Key。

---

## 15. Coach Agent OpenAI-compatible Provider

Coach Agent Provider 默认关闭。生产部署只在服务端配置以下变量，客户端不得提交或覆盖这些值：

```env
COACH_AGENT_ENABLED=false
COACH_AGENT_PROVIDER=openai-compatible
COACH_AGENT_API_KEY=
COACH_AGENT_BASE_URL=https://api.example.com/v1
COACH_AGENT_MODEL=example-model
COACH_AGENT_THINKING_MODE=unset
COACH_AGENT_RESPONSE_FORMAT_MODE=json_schema
COACH_AGENT_CONNECT_TIMEOUT_SECONDS=10
COACH_AGENT_READ_TIMEOUT_SECONDS=60
COACH_AGENT_TOTAL_TIMEOUT_SECONDS=90
COACH_AGENT_MAX_RETRIES=1
COACH_AGENT_MAX_OUTPUT_TOKENS=2000
```

`COACH_AGENT_THINKING_MODE` 只允许：

- `unset`：默认值，不附加 Provider 专用请求字段，保持通用 OpenAI-compatible 行为；
- `disabled`：请求增加受控的 `thinking: {"type": "disabled"}`，用于 DeepSeek V4 非思考模式兼容；
- `enabled`：配置值保留，但 v0.11.0 会在网络调用前安全拒绝。当前工具链不会读取或回传 `reasoning_content`，因此不支持 DeepSeek 思考模式的多轮工具调用。

`COACH_AGENT_RESPONSE_FORMAT_MODE` 只允许：

- `json_schema`：默认值，向支持 JSON Schema Response Format 的端点发送现有严格 `AgentModelOutput` Schema；
- `json_object`：用于不支持最终 JSON Schema Response Format、但支持 JSON Output 的兼容端点。Provider 只保证返回 JSON，服务端仍会执行严格 Pydantic Schema 校验和 Deterministic Validator。

DeepSeek-compatible 的非思考模式部署可显式配置：

```env
COACH_AGENT_THINKING_MODE=disabled
COACH_AGENT_RESPONSE_FORMAT_MODE=json_object
```

系统不会根据 Base URL 或模型名自动探测模式，也不会在 HTTP 400 后自动切换响应格式。配置错误会进入安全降级；当前版本不支持完整的 DeepSeek thinking 工具链。

不提供任意 `extra_body` JSON 配置。生产环境禁止 localhost、私网和包含用户名或密码的 Provider URL；只有 development 环境可通过显式开关允许本地 Provider。API Key 不得进入前端、日志、截图或版本库。

---

## 16. v0.11.0 Coach Agent 发布检查

v0.11.0 没有新增数据库模型或迁移。升级前仍应先完成 v0.10.3 的 Runner State 与 Garmin 自动快照迁移链，并备份目标数据库。

发布前至少验证：

```bash
.venv/bin/python -m compileall planner_core server scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_coach_agent.py

cd web
npm ci
npm run typecheck
npm run test
npm run build
```

数据库回归应在与目标环境隔离的 MySQL 5.7 和 MySQL 8 实例上分别执行。测试账号只需随机测试数据库的创建和删除权限；不得连接生产数据库，不得复用生产账号或数据。测试完成后确认所有随机测试数据库已删除。

Provider 上线顺序：

1. 保持 `COACH_AGENT_ENABLED=false`，验证应用导入、OpenAPI、前端页面和确定性 Fallback；
2. 在隔离环境配置服务端 Provider，使用完全虚构数据执行 TODAY、EXPLAIN 和 GENERAL Smoke；
3. 确认日志和报告不包含 API Key、完整 Prompt、Context、Tool Result、Provider 原始回答或 `reasoning_content`；
4. DeepSeek V4 非思考模式显式设置 `COACH_AGENT_THINKING_MODE=disabled`；仅在端点不支持最终 JSON Schema Response Format 时设置 `COACH_AGENT_RESPONSE_FORMAT_MODE=json_object`；
5. 确认 TODAY 的 decision、计划状态、风险、数据质量、warnings、limitations 与 canonical Evidence 均由服务端装配；
6. 小范围开启 Provider；出现 Provider 异常时应返回 `DEGRADED`，不得改变训练计划或其他训练数据。

v0.11.0 不支持 RAG、Weekly Review Agent、写工具、长期记忆、Streaming、多 Agent 或 DeepSeek thinking 工具链。Coach Agent 只提供非医疗的只读训练参考；Quota 当前为进程内限制。

---

## 18. v0.13.0 Weekly Review 与 Adaptive Coaching

部署 v0.13.0 前先备份数据库并在隔离环境验证 `scripts/upgrade_v0130_adaptive_plan.py` 的 upgrade/downgrade。该脚本只新增计划版本、LangGraph checkpoint 和 pending write 相关结构，不扫描或回填用户训练数据。升级后执行 Python 编译、完整 pytest、前端 typecheck/test/build 与 `python scripts/evaluate_weekly_adaptive.py`。

已运行早期 v0.13 checkpoint schema 的 MySQL 数据库，在部署包含本修复的版本前还必须执行一次前向升级：

```powershell
python scripts/upgrade_v0160_adaptive_checkpoint_hash.py upgrade
```

该脚本保留完整 `task_path`，新增并回填 `task_path_hash BINARY(32)`，再将 pending write 的联合唯一键从完整路径替换为 SHA-256 二进制摘要。它用于解决 `utf8mb4` 下旧 4096-byte 联合索引超过 MySQL 5.7/8 3072-byte 上限的问题。升级前必须备份；这是一项前向迁移，旧的超宽索引在现代 MySQL 上无法安全恢复。详见 `docs/learning/v0.16.0/24-mysql-composite-index-hash-key.md`。

## 19. v0.14.0 Agent Observability and Reliability

v0.14 不新增数据库迁移。默认关闭可选运行时观测：

```env
AGENT_TRACING_ENABLED=false
AGENT_TRACE_EXPORTER=noop
AGENT_METRICS_ENABLED=false
AGENT_METRICS_MAX_LATENCY_SAMPLES=2048
```

启用 OTLP Trace 时设置 `AGENT_TRACING_ENABLED=true`、`AGENT_TRACE_EXPORTER=otlp` 和无凭据、无查询参数的 `OTEL_EXPORTER_OTLP_ENDPOINT`。启用 Metrics 时仅保存有界聚合，不保存原始 Span 或请求正文。所有 Trace/Metrics exporter 故障都会被隔离，不能影响 Coach、Weekly Review、HITL 或计划写事务。

部署前运行：

```powershell
python -m compileall planner_core server scripts tests
pytest -q
python scripts/evaluate_agent.py --suite all
```

评测总状态目前是 `PARTIAL`：Coach、RAG、Weekly Adaptive 通过，Retrieval 保留已知基线的 17 项失败。发布前应确认其未相对基线退化，而不是把该状态替换为 PASS。

生产流程必须保持：Nginx 只代理 `/api/`，FastAPI 从认证上下文注入用户，LangGraph Checkpoint 使用 MySQL 持久化，LLM 无数据库写工具。计划批准由 `AdaptivePlanApprovalService` 在单事务内执行所有权、base version、锁定状态和规则复核；Trace Sink 故障不得影响业务事务。

回滚代码前先停止新审批流量。数据库 downgrade 仅在确认没有需要保留的 v0.13 checkpoint/版本记录后执行；优先关闭自适应入口并回滚应用代码，不得直接删除历史版本证据。MySQL 5.7 与 8 应分别验证 upgrade、审批幂等、rollback 和 downgrade。

## 17. v0.12.0 Training Knowledge RAG

v0.12.0 没有数据库迁移。生产仍使用 Nginx 托管前端静态文件，并将 `/api/` 转发至由 Gunicorn、Uvicorn Worker 和 Supervisor 托管的 FastAPI 进程；仓库没有正式 Docker Compose 部署。默认保持知识检索关闭，只有真实索引构建、校验和 Readiness 全部通过后才启用。

### 服务端配置

除第 15 节的 Chat Provider 配置外，按部署环境配置：

```env
KNOWLEDGE_EMBEDDING_ENABLED=true
KNOWLEDGE_EMBEDDING_PROVIDER=openai_compatible
KNOWLEDGE_EMBEDDING_API_KEY=
KNOWLEDGE_EMBEDDING_BASE_URL=https://embedding.example.com/v1
KNOWLEDGE_EMBEDDING_MODEL=example-embedding-model
KNOWLEDGE_EMBEDDING_DIMENSIONS=1536
KNOWLEDGE_EMBEDDING_BATCH_SIZE=32
KNOWLEDGE_EMBEDDING_CONNECT_TIMEOUT_SECONDS=5
KNOWLEDGE_EMBEDDING_READ_TIMEOUT_SECONDS=30
KNOWLEDGE_EMBEDDING_TOTAL_TIMEOUT_SECONDS=60

COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=true
COACH_AGENT_KNOWLEDGE_INDEX_ID=
COACH_AGENT_KNOWLEDGE_TOP_K=4
KNOWLEDGE_INDEX_RUNTIME_DIRECTORY=var/knowledge_indexes
KNOWLEDGE_INDEX_MAX_AGE_DAYS=30
```

示例值不可直接用于生产。API Key 只能放在服务端安全配置中。Provider URL 不得包含账号、密码、查询参数或 fragment，也不得指向 localhost、私网或云元数据地址；development 的本地例外必须显式开启。

### 部署顺序

```text
部署代码
→ 安装 Python / Node 依赖
→ validate corpus
→ 部署并 validate 指定 index
→ Readiness check
→ 确认本版本无数据库迁移
→ 构建并启动后端和前端
→ health / OpenAPI check
→ 使用虚构数据执行 real-provider smoke
→ 切换流量
```

命令：

```bash
.venv/bin/python scripts/knowledge_corpus.py validate
.venv/bin/python scripts/knowledge_index.py validate \
  --index-id "$COACH_AGENT_KNOWLEDGE_INDEX_ID"
.venv/bin/python scripts/check_coach_rag_readiness.py --require-enabled
.venv/bin/python scripts/smoke_coach_rag.py
```

Readiness 不访问网络，只输出布尔状态、非敏感模式名和稳定错误码。Smoke 使用固定虚构只读 Fixture，不连接数据库，不保存 Provider 原始回答、Prompt、Context、Tool Result、知识摘录或 `reasoning_content`。MySQL 5.7/8 兼容性由独立隔离测试矩阵验证。

### Nginx 与运行目录

- `/api/coach/query` 继续由 `/api/` 代理到 `127.0.0.1:8000`；
- Coach POST 的代理读取超时应不短于 `COACH_AGENT_TOTAL_TIMEOUT_SECONDS`，但不得无限延长；
- 限制请求体大小，例如 `client_max_body_size 1m`；
- 对 Coach POST 使用 `proxy_no_cache 1` 和 `proxy_cache_bypass 1`；
- 不得将 `.env`、`knowledge/manifests/`、`var/knowledge_indexes/` 或向量文件置于 Web Root；
- `var/knowledge_indexes/` 只允许后端运行用户读取，Web 服务不得修改 Corpus 源文件；
- 每次部署显式绑定版本化 Index ID，不在请求期自动构建索引。

### 日志

允许记录 request ID、Intent、最终状态、Provider 状态、工具名、工具结果数量、知识引用数量、验证码、延迟和用量。禁止记录用户问题、训练正文、知识摘录、完整回答、Prompt、Context、向量、API Key、数据库 URL、Provider 原始响应或 `reasoning_content`。

### 回滚

1. 回滚后端和前端发布目录；
2. 恢复上一有效 `COACH_AGENT_KNOWLEDGE_INDEX_ID`；
3. 若索引异常，先设置 `COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED=false`，保留不依赖知识检索的 Coach 能力；
4. 若 Chat Provider 异常，设置 `COACH_AGENT_ENABLED=false`，使用确定性降级；
5. 本版本没有数据库迁移，不执行数据库 downgrade。
## v0.15.0 MCP deployment boundary

MCP stdio is for a local trusted Host. Streamable HTTP remains disabled unless explicitly configured, and must use the scoped MCP token endpoint, the configured origin allowlist, and the existing authenticated application deployment. Do not expose corpus/index runtime paths through Nginx. MCP Tools are read-only; Resources contain only public knowledge projections and never runner data.
