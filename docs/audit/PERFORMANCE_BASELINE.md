# Performance Baseline v1.0

日期：2026-11-13。结论：**仅建立了部分隔离性能基线，50 并发稳定性不通过；不是生产容量证明**。

## 1. 环境与方法

- Windows 10，Python 3.11.4，12 个逻辑 CPU，23.8 GiB内存；负载机、应用及 MySQL 共享本机，非专用压测主机。
- MySQL 8.0.46，仅 loopback:3307；每次新建唯一 gaitlogic_test_* 库和只获该库权限的账号，结束删除本次库/账号。没有测试日常库或生产库。
- FastAPI 0.139.0 / Starlette 1.3.1 / SQLAlchemy 2.0.51 / PyMySQL 1.2.0 / MCP 2.0.0 / Uvicorn 0.49.0；单 Uvicorn Worker，无 Nginx/TLS。
- 50 个虚构账号、4,200 条训练日志（每人84天）、1,400个关联活动、14,000个Lap、1,400天恢复记录。无正式计划、有效周期、历史长会话或待应用草稿，相关复杂性能未覆盖。
- 真实 HTTP/TCP、真实 MySQL、真实密码哈希与 OAuth Grant 校验，不以 Mock SQL 代替。Smart Sync 和 Trace export 关闭，测试应用拒绝外部 socket 连接；不调用 Garmin 或付费 LLM。
- Locust 2.47.0，封闭式用户，思考间隔0.1～0.3秒；1/5/10/20用户各15秒，10用户60秒，50用户45秒。50用户以50用户/秒启动，属于短突发，不是长期容量认证。
- 混合权重：dashboard 3、calendar 2、Runner State 2、Plan Context 1、MCP recent 4、detail 2、recovery 1。请求超时10秒；MCP同时检查HTTP与业务失败。每批不重新启动服务。
- CPU 为应用实际解释器进程的 CPU 时间/墙钟时间（单核100%），RSS为采样峰值；排除 Windows venv launcher。未采集 MySQL CPU/内存/锁等待、磁盘与 event-loop 连续指标。
- 测试期间可能存在桌面背景任务；不将本机结果外推腾讯云。相同主机上的 Python静态扫描/回归没有与最终负载批次同时执行。

## 2. 单用户顺序请求

每项12次，包含冷启动；nearest-rank分位。N=12 时P95/P99均为样本最大值，统计稳定性不足。

| Endpoint | N | P50 ms | P95 ms | P99 ms | HTTP |
|---|---:|---:|---:|---:|---|
| `/api/auth/login` | 12 | 79.3 | 342.0 | 342.0 | 200 |
| `/api/dashboard` | 12 | 2.9 | 169.2 | 169.2 | 200 |
| `/api/dashboard/today` | 12 | 11.3 | 28.7 | 28.7 | 200 |
| `/api/training-calendar` | 12 | 4.3 | 5.5 | 5.5 | 200 |
| `/api/runner-state/current` | 12 | 15.2 | 34.6 | 34.6 | 200 |
| `/api/ai-plan/context` | 12 | 29.2 | 41.0 | 41.0 | 200 |
| `/api/admin/console/overview` | 12 | 3.0 | 5.3 | 5.3 | 200 |

这里的首页/今日页面是后端API，不包含浏览器渲染；无计划的今日接口不代表复杂课表详情性能。

## 3. 混合负载结果

分位与RPS来自最终Locust CSV（近似直方图，统计窗口与命令墙钟略有差异）。失败率包含业务失败/客户端超时；测试结束时仍在途的请求不会完整计入，不能将完成请求数当作全部发起量。

| Users | Seconds | Recorded requests | Failures | Failure rate | P50 ms | P95 ms | P99 ms | RPS | App CPU % | Peak RSS MiB |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 15 | 58 | 0 | 0.00% | 11 | 97 | 190 | 4.17 | 10.1 | 197.0 |
| 5 | 15 | 235 | 0 | 0.00% | 81 | 270 | 490 | 16.86 | 54.6 | 203.8 |
| 10 | 15 | 335 | 0 | 0.00% | 200 | 550 | 620 | 23.75 | 82.0 | 210.0 |
| 20 | 15 | 370 | 0 | 0.00% | 550 | 1000 | 1400 | 26.29 | 96.2 | 216.9 |
| 10 | 60 | 1267 | 0 | 0.00% | 270 | 560 | 720 | 21.27 | 90.0 | 217.3 |
| 50 | 45 | 219 | 212 | 96.80% | 10000 | 10000 | 11000 | 4.98 | 2.3 | 217.5 |

累计记录 2484 个混合请求，另有84个顺序请求。10用户60秒仅属于短时稳定性观察，不是小时级soak test。50用户阶段Locust退出码2；其余为0。采集用pytest本身完成不代表性能验收PASS。

## 4. 瓶颈证据

- 最终50用户阶段：连接池采样显示 pool_size=5、overflow=10、checked_out=15、空闲0，超过5秒仍饱和。
- 测试堆栈显示事件循环线程位于 `server/mcp/http.py:125 → _authenticate:194 → SQLAlchemy QueuePool._do_get → queue.get`。这是同步获取连接阻塞异步入口的直接证据。
- 同时出现安全错误 `mcp_http_identity_lookup_failed`。50用户阶段CPU反而下降，不能简单归因为CPU算力不足，也不能认定数据查询本身全部变慢。
- 上一次有效混合尝试在50用户之后运行10用户恢复观察，0个请求完成；该阶段判为失败/无可用分位，不报告“0错误率通过”。最终批次把60秒观察放在50用户之前，避免污染低负载基线。
- 先修复/验证异步入口阻塞和Session释放链，再决定pool/线程/worker预算；未修改业务代码或调大池子。完整锁等待/释放根因尚未逐连接证明，不把此次堆栈称为所有阻塞原因的穷尽分析。

## 5. 数据库查询

- 共享 `get_recent_training_read` 的28天调用：12.48ms，4次SELECT，返回总训练数28，页面上限20。一次样本不是P95。
- 对实际捕获的4个SELECT执行EXPLAIN；日志主查询使用user_id索引，预计扫描该用户84行，存在temporary/filesort。COALESCE(actual_date, planned_date)使日期范围不能简单当作已命中复合日期索引。
- 计划表在本次为空，EXPLAIN的ALL/rows=1不能证明大计划表全扫问题。活动查询预计28行。未执行生产EXPLAIN或重查询。
- 未见此调用逐记录N+1（实际4次SELECT）；不能外推所有详情/草稿/仪表盘都没有N+1。未覆盖多年历史、实际大周期、同时生成/应用计划的锁竞争。

## 6. 已测与未测

| Capability | Status | Scope |
|---|---|---|
| Login / dashboard / today / calendar / Runner State / Plan Context / admin overview | MEASURED | 表2的12次局部样本 |
| MCP recent 28d / detail / recovery | MEASURED | 真实TCP混合负载，不含真实上游同步 |
| MCP six tools / OAuth / recovery scope | FUNCTIONAL REGRESSION | 六工具契约与真实TCP测试；不是六工具各自完整延迟分布 |
| Recent 7d | FUNCTIONAL REGRESSION | 未单独建立与28d相同的性能分布 |
| Coach model / AI Plan generation + apply | NOT MEASURED | 定向功能回归不替代性能；未发送付费请求 |
| RAG / embedding / Garmin upstream | NOT MEASURED | 未让真实Provider参与负载 |
| Mixed automatic sync / long soak / production CPU+DB | NOT MEASURED | 后续隔离阶段补充 |
| Full browser rendering / mobile | NOT MEASURED | 本次不是视觉/交互验收 |

## 7. 执行记录与失败保留

- 定向安全/会话/AI/MCP/Smart Sync：152 passed，0 failed，0 skipped，11.14秒。
- 真实MySQL/TCP/OAuth/事实组：11 passed；同批私人审计断言1 failed（误怀疑跨周期字段写入，已由最终数据库状态反证）。未删除该次报告。
- 修正审计断言后私人复现：1 passed，0 skipped，2.78秒；证明发现可复现，不表示产品安全。
- 首轮Locust脚本将任务命名为context，与框架方法冲突；零请求批次作废。次轮发现50用户后的恢复停滞，采集保护断言触发失败。最终轮增加10秒客户端超时、池采样并调整观察顺序，保留了真实失败，不改业务实现。
- 历史OAuth迁移最终1 passed（首次配置不足1 skipped后显式补配置重跑）；入口矩阵+HITL 8 passed，其中238个匿名API操作均401；六工具/隐私补充60 passed。分组有重复用例，不能相加声称唯一覆盖数。
- 前端Typecheck通过，Vitest 230 passed（44文件，14.17秒），构建通过（10.28秒）；两个JS块超过1MB、登录背景约1.87MB，未实测浏览器Web Vitals。
- 临时受限账号和本次测试库均由运行器finally清理；Windows压测进程树已核验无残留。业务文件48项原始哈希保持不变。

## 8. 重现入口

1. 单独准备本机3307 MySQL 8；在终端安全设置 MYSQL_HOST/PORT/USER/PASSWORD，协调账号只用于创建临时测试库/受限账号。不要把密码写入命令历史或报告。
2. 在私有审计venv安装 bandit、pip-audit、locust、psutil；不升级项目venv。当前脚本约定工具位于 `.audit-private/tools/`。目录必须Git忽略。
3. 从仓库根设置 PYTHONPATH=.；执行 `.venv/Scripts/python.exe -B scripts/audit/run_isolated.py scripts/audit/test_isolated_baseline.py -s`。协调器强制本机3307及唯一gaitlogic_test_*名称，注入受限账号。
4. 对历史迁移单独运行 `scripts/audit/run_isolated.py --empty-schema tests/test_mcp_oauth_mysql_migration.py`；不要与已初始化表的基准共用Schema。
5. Locust只允许127.0.0.1，禁止将其host改为生产。原始CSV/日志、临时合成令牌均在私有目录；结束清理本次数据库/账号/进程，保留脱敏结果。
6. 执行 `scripts/audit/render_results.py` 生成本报告的测量表。不要把原始异常、堆栈、完整SQL参数或测试URL上传公开仓库。

单次结果不是容量上限。下一步建议与验收门槛见 [优化路线图](OPTIMIZATION_ROADMAP.md)。
