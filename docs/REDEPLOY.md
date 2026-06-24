# 一键重新部署脚本

[返回项目首页](../README.md) · [返回文档中心](README.md)

本项目提供本地部署脚本：

```powershell
.\scripts\deploy.ps1
```

它适合在你本地改完代码后执行，自动完成：

- 后端测试
- 前端构建
- 打包后端、核心模块、脚本、SQL、文档和 `web-dist`
- 通过 SSH 上传到服务器
- 在服务器解压并覆盖部署目录
- 安装后端依赖
- 可选初始化数据库
- 可选重启后端服务
- 可选重载 Nginx

脚本不会上传本地 `.env`，只会带上 `.env.example`。

---

## 常用命令

Supervisor 托管后端时：

```powershell
.\scripts\deploy.ps1 `
  -ServerHost "你的服务器IP或域名" `
  -ServerUser "root" `
  -RemotePath "/www/wwwroot/gaitlogic-planner" `
  -RemoteFrontendDir "/www/wwwroot/gaitlogic-planner/web-dist" `
  -ServiceManager "supervisor" `
  -BackendService "gaitlogic-planner" `
  -ReloadNginx
```

如果你的 Nginx 静态目录仍然指向 `/www/wwwroot/gaitlogic-planner/web/dist`，则把前端目录改成：

```powershell
-RemoteFrontendDir "/www/wwwroot/gaitlogic-planner/web/dist"
```

Systemd 托管后端时：

```powershell
.\scripts\deploy.ps1 `
  -ServerHost "你的服务器IP或域名" `
  -ServerUser "root" `
  -RemotePath "/www/wwwroot/gaitlogic-planner" `
  -ServiceManager "systemd" `
  -BackendService "gaitlogic-planner.service" `
  -ReloadNginx
```

只在本地打包，不上传服务器：

```powershell
.\scripts\deploy.ps1 `
  -ServerHost "example.com" `
  -ServerUser "root" `
  -SkipUpload
```

跳过测试和前端构建，直接用当前已有的 `web-dist` 打包上传：

```powershell
.\scripts\deploy.ps1 `
  -ServerHost "你的服务器IP或域名" `
  -ServerUser "root" `
  -SkipTests `
  -SkipFrontendBuild
```

需要同步数据库表结构时再加：

```powershell
-RunInitDb
```

---

## 运行前服务器需要具备

服务器需要已经安装：

- Python 3.11+
- 项目虚拟环境，推荐路径：`/www/wwwroot/gaitlogic-planner/.venv`
- `pip`
- `unzip`
- `rsync`
- `supervisorctl` 或 `systemctl`
- `nginx`

服务器项目目录内需要已有生产环境 `.env`：

```text
/www/wwwroot/gaitlogic-planner/.env
```

脚本不会覆盖服务器上的 `.env`。

---

## 需要你提供的信息

给我下面这些信息后，我可以帮你把命令整理成你机器可直接运行的一行：

| 信息 | 示例 | 说明 |
| --- | --- | --- |
| 服务器地址 | `1.2.3.4` 或 `example.com` | SSH 连接地址 |
| SSH 用户名 | `root` | 能上传文件并重启服务的用户 |
| SSH 端口 | `22` | 非 22 端口需要注明 |
| 远程项目目录 | `/www/wwwroot/gaitlogic-planner` | 后端代码所在目录 |
| 前端静态目录 | `/www/wwwroot/gaitlogic-planner/web-dist` | Nginx 当前 root 指向的目录 |
| 后端托管方式 | `supervisor` / `systemd` | 用来重启后端 |
| 后端服务名 | `gaitlogic-planner` | Supervisor program 名或 systemd service 名 |
| 是否每次重载 Nginx | 是 / 否 | 一般前端目录没变时也可以重载 |
| 是否执行数据库初始化 | 是 / 否 | 表结构有新增时再执行 |
| 本机 SSH 登录方式 | 密钥 / 密码 | 密钥更适合自动部署 |

---

## 注意事项

- 第一次部署前，建议先手动确认服务器现有系统能正常运行。
- 如果服务器没有 `rsync` 或 `unzip`，请先安装。
- 如果 SSH 用户不是 `root`，重启服务和重载 Nginx 可能需要免密 `sudo`。
- 脚本会在服务器项目目录下创建备份：`.deploy/backup-时间戳`。
- 如果本次只改前端，也可以使用 `-SkipTests` 加快部署。
- 线上接口文档推荐访问 `https://你的域名/api/docs`；本地直连后端时也可以访问 `http://127.0.0.1:8000/docs`。
