# GaitLogic Planner 部署文档

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
```

注意：

* `JWT_SECRET_KEY` 必须使用足够长的随机字符串；
* `DEEPSEEK_API_KEY` 不要提交到仓库；
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

## 12. 安全建议

生产环境建议：

* 不要提交 `.env`；
* 不要将后端 8000 端口直接暴露到公网；
* 使用 HTTPS；
* 定期备份 MySQL 数据；
* 为 demo 账号限制权限或定期重置数据；
* DeepSeek / OpenAI-compatible API Key 仅保存在服务端；
* 前端不要出现任何真实 API Key。
