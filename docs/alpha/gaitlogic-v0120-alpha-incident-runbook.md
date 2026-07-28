# GaitLogic v0.12.0 Alpha 故障手册

## 先做什么

1. 暂停新增 Alpha 用户；
2. 保存 request ID、时间、Intent、状态码和安全错误码；
3. 不复制 Prompt、Context、训练正文、知识摘录或 Provider 原始回答；
4. 运行 `python scripts/check_coach_rag_readiness.py --require-enabled`。

## 常见故障

### Chat Provider 故障

确认配置存在但不打印值。必要时设置 `COACH_AGENT_ENABLED=false`，重启后端并验证确定性 Fallback。不得把 Provider 技术错误显示为训练结论。

### Embedding 或 Index 故障

运行 Corpus 和 Index validate。若 stale、missing 或配置不匹配，关闭 `COACH_AGENT_KNOWLEDGE_RETRIEVAL_ENABLED`，保留 v0.11.0 Coach 能力。不要在请求期重建索引。

### 大量 DEGRADED

按 Provider 状态、验证码和工具名聚合排查；检查 timeout、quota 和索引可读权限。不得通过放宽 Validator 恢复成功率。

### 引用异常

立即关闭 Knowledge Retrieval；核对 Canonical Catalog、公开 document ID 和 Index/Corpus root hash。模型提供的标题或 URL 不能作为可信来源。

### 数据误写

暂停 Coach 入口，记录受影响测试账号和时间窗，核对训练计划、日志与快照表。Coach 应为只读；任何写入都按高严重度产品缺陷处理。

### 怀疑凭据泄漏

关闭 Provider、轮换 Key、检查访问和错误日志，并删除含凭据的本地临时产物。不得只在 Git 历史中“覆盖”旧 Key。

## 回滚

1. 回滚后端和前端到上一发布提交；
2. 恢复上一有效 `COACH_AGENT_KNOWLEDGE_INDEX_ID`；
3. 或关闭 Knowledge Retrieval；
4. Provider 故障时关闭 Coach Agent；
5. 本版本没有数据库迁移，无需执行数据库 downgrade。

恢复流量前重新运行健康检查、Readiness、公开 API Smoke 和安全边界检查。
