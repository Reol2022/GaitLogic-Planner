# Training Knowledge RAG Roadmap v1

## v0.12.0-A — Corpus Foundation

交付文档与来源 Schema、安全 Loader、确定性 Chunker、Manifest、root hash、CLI、示例知识和测试。

不含 Embedding、向量索引、Retriever 或 Agent 接入。

## v0.12.0-B — Embedding / Vector Store / Retriever

计划建立受控 Embedding Provider、可替换 Vector Store、索引构建与更新流程，以及 Training Knowledge Retriever。

关键门槛：

- 索引绑定 corpus root hash；
- Provider 配置由服务端控制；
- 不索引用户数据和私有内容；
- 支持隔离测试和可重复重建；
- 检索结果携带来源、版本和 Chunk 引用。

## v0.12.0-C — Agent Tool Integration

计划新增只读知识检索工具，让 Coach Agent 同时使用结构化训练事实与知识引用。知识结果不能覆盖确定性建议，客户端不能指定索引、Provider 或任意路径。

## v0.12.0-D — RAG Evaluation

计划建立无第二个 LLM 裁判的确定性评测，包括召回、引用完整性、来源正确性、无依据声明、冲突处理和降级行为。

## v0.12.0-E — Frontend / Demo / Release

计划展示安全的知识引用、来源和限制，完成浏览器验收、公开 Demo、MySQL 回归与 v0.12.0 发布。

## 明确不在当前 Roadmap 中承诺

- 医疗知识库或诊断；
- 自动修改训练计划；
- 写工具；
- 未审核网页的实时抓取；
- 受版权保护全文索引；
- 用户对话长期记忆；
- 多 Agent 或自治执行。
