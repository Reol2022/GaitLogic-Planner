# GaitLogic v0.12.0 简历与面试指南

## 一页简历版（6 条）

- 独立设计并实现跑步训练管理闭环，使用 FastAPI、SQLAlchemy、MySQL 和 Vue 3 覆盖训练周期、每日计划、训练日志、统计复盘与 Garmin 同步。
- 将 Runner State、近期训练、今日计划、训练周期、规则和数据质量封装为 8 个严格 Schema 的只读 Agent Tools，用户身份只由服务端注入。
- 构建训练知识 RAG：版本化 Corpus、确定性 Chunk、Embedding Provider、Exact Cosine Store、Metadata Retrieval 和 Canonical Knowledge Reference。
- 采用“结构化工具提供事实、规则引擎负责决策、RAG 提供知识、LLM 负责解释、Validator 与 Fallback 约束输出”的分层架构。
- 设计 Canonical Evidence/Knowledge Reference 协议：模型只选择本次请求中存在的引用 ID，服务端物化原文，阻止来源幻觉和任意引用注入。
- 在 96 条完全虚构的真实 Provider RAG 案例中保持 Decision、Canonical Evidence 和 Warning 100% 一致，来源幻觉、规则违规和未授权计划修改为 0；综合 Case Pass Rate 53.13%，检索标签确认和人工盲评仍在进行。

## 项目架构怎么讲

`POST /api/coach/query` 先通过认证取得当前用户，再由 Context Builder 调用只读 Tool Registry。结构化训练事实进入确定性规则；训练知识通过 Retriever 返回请求内临时 Reference ID。LLM 只能编排允许的工具和生成解释，Validator 校验引用、Decision 和安全边界；失败时 Fallback 仍返回规则结果。

### 关键概念

- **Structured Tools**：用 Pydantic 定义输入输出和 Intent Policy，隔离数据库与模型。
- **Rules**：拥有 TODAY Decision、风险提示和计划状态，模型无权覆盖。
- **RAG**：从版本化训练知识库检索解释依据，不生成个人事实。
- **LLM**：负责有限工具编排与自然语言解释。
- **Validator**：拒绝不存在的引用、事实冲突和越权结论。
- **Fallback**：Provider 或工具失败时复述确定性事实。
- **Canonical Evidence**：服务端拥有的个人训练事实依据。
- **Canonical Knowledge Reference**：服务端从本次检索结果物化的公开知识引用。

## 高频面试问题

### 为什么不能让 LLM 直接查数据库？

代码：`server/agent/tools/`、`server/agent/training_context_builder.py`。
设计：数据库权限、用户隔离和查询边界不能交给概率模型；服务端只暴露最小只读工具。
测试：Tool Registry、跨用户访问、非法参数和响应脱敏测试。
问题：早期如果只把大段 Context 拼进 Prompt，容易超长且难追踪来源。
替代：只读 SQL Agent，但仍需查询白名单、租户隔离和结果 Schema，当前复杂度不划算。

### 为什么 RAG 不参与 TODAY 决策？

代码：`server/agent/today_recommendation.py`、`server/agent/validator.py`。
设计：个人训练建议必须来自结构化状态和确定性规则；知识文档只提供解释。
测试：Decision invariance、Canonical Evidence 和禁止计划修改测试。
问题：真实 Provider 曾返回与权威字段形状冲突的 TODAY 数据。
替代：让模型直接生成 Decision，但会降低可追溯性和稳定性。

### 为什么使用请求内 Reference ID？

代码：`server/agent/knowledge_references.py`。
设计：模型只选择 `knowledge_1` 等临时 ID，服务端核验 ID 属于本次检索并还原标题和摘录。
测试：不存在、重复、跨请求和非规范 ID 均拒绝。
问题：直接让模型复写来源容易产生不存在的标题或链接。
替代：让模型返回完整引用对象，但必须接受更大的注入和幻觉面。

### 为什么没有直接使用 LangChain？

代码：`server/agent/orchestrator.py`、`server/knowledge_retrieval/`。
设计：当前链路短，自己维护可以清晰控制 Schema、Tool Policy、Canonical Reference 和失败语义。
测试：每层都是可独立测试的纯服务或协议。
问题：第三方抽象升级可能改变 Tool Calling 或消息格式。
替代：LangChain/LlamaIndex 适合更复杂工作流，但需要额外适配现有确定性边界。

### 为什么采用 Exact Cosine Store？

代码：`server/knowledge_retrieval/vector_store.py`。
设计：当前 Corpus 小，精确余弦结果可重复、易调试、无需独立向量服务。
测试：排序、维度、元数据过滤、索引版本和持久化测试。
问题：数据量增大后线性扫描延迟会上升。
替代：MySQL Vector、pgvector、Milvus 或 FAISS/HNSW；应在规模和召回需求明确后迁移。

### Dense 与 BM25 有什么差异？

BM25 依赖词项匹配，短关键词和专业术语通常稳定；Dense Embedding 更擅长语义改写。当前私有评测中 BM25 是重要基线，Dense + Metadata 负责语义召回和受控过滤，不能只看单一 Recall 指标。

### 如何评价 RAG？

代码：`server/knowledge_retrieval/evaluation/`，私有实验位于独立竞赛仓库。
指标：Recall@K、MRR、nDCG、Forbidden Document Rate、Citation Precision/Recall、Decision Invariance、来源幻觉和规则违规。
测试：公开契约测试使用虚构数据；真实 Provider 结果不进入公共仓库。
问题：Provider 传输失败和 disputed labels 会污染结论。
替代：只做人工主观评分不够可重复，应与自动安全指标和盲评组合。

### Provider 失败如何处理？

Embedding 传输错误会有限重试并重建 HTTP Client；Chat 或 Knowledge Tool 失败进入安全 Fallback。失败不泄露 Key、Prompt、Context 或原始回答。

### 如何防止来源幻觉？

模型不能提交任意标题、路径或 URL，只能选择本次请求中真实存在的 Reference ID；Validator 校验后由服务端物化公开字段，前端也不显示内部 ID、分数和向量。

### 当前不足是什么？

私有 Retrieval 的 forbidden 标签尚需人工确认，首轮盲评未完成；真实 Provider 稳定性影响端到端 Case Pass Rate；Exact Store 尚未面向大 Corpus；没有 Weekly Review Agent、写工具、长期记忆或多 Agent；任何计划修改仍需用户确认。

## 面试验收清单

- 能指出 API、Context Builder、Tool、Retriever、Validator、Fallback 和前端引用组件的真实路径；
- 能解释事实、决策、知识和模型四层边界；
- 能用测试和真实故障说明设计，而不是只背概念；
- 能准确说明安全指标通过但综合 Case Pass Rate 并非 100%；
- 不把未完成的人工标签和盲评写成最终结论。
