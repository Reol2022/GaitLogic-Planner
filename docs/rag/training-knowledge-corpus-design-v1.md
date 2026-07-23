# Training Knowledge Corpus Design v1

## 1. 目标与边界

Training Knowledge Corpus 为后续检索提供结构化、可审计的训练理论与解释材料。本阶段只建设文档、来源、确定性切分、校验和 Manifest，不生成 Embedding，不接入 Vector Store、Retriever 或 Coach Agent。

职责边界如下：

```text
Structured Tools  -> 用户训练事实
Deterministic Rules -> 状态、决策与安全边界
Knowledge Corpus  -> 原则、解释、限制与来源
Future Retriever  -> 选择相关知识片段
LLM               -> 组织自然语言解释
Validator         -> 阻止越权或无依据结论
```

`server/knowledge_retrieval` 不依赖 `server/agent`。现有可执行规则继续位于 `planner_core/training_knowledge` 和 `config/training`，不能被知识文档覆盖。

## 2. 目录结构

- `knowledge/documents`：可检索 Markdown 知识。
- `knowledge/sources`：独立的来源和授权元数据。
- `knowledge/taxonomy`：分类词表。
- `knowledge/rules`：确定性规则边界说明，不承载可执行规则副本。
- `knowledge/manifests`：由构建器生成的派生索引元数据。
- `server/knowledge_retrieval`：运行时 Schema、Loader、Chunker、Validator 和 Service。

## 3. Knowledge Schema

每篇文档使用严格 YAML Front Matter。必填字段包括 `document_id`、标题、分类、标签、适用阶段、来源引用、来源类型、证据级别、知识版本、语言和状态。未知字段拒绝，ID 使用小写 kebab-case，版本使用 SemVer，日期使用 ISO 8601。

`applicable_phases` 复用产品的 `TrainingPhaseState`：`BASE`、`BUILD`、`SPECIFIC`、`PEAK`、`TAPER`、`RACE`、`RECOVERY`、`UNKNOWN`。知识侧不另造 `SPECIAL` 等自由文本。

正文必须包含：

1. 适用场景
2. 核心原则
3. 判断条件
4. 推荐策略
5. 注意事项

Front Matter 不进入 Chunk 正文。

## 4. 来源模型与版权

来源记录独立于文档，包含来源类型、作者、版本、出版信息、许可状态和使用策略。公开仓库仅保存：

- 原创内容；
- 自己撰写的来源摘要；
- 明确开放许可或获得授权的内容；
- 仅用于追溯的书目信息。

不得保存付费书籍正文、未授权论文全文或将其按片段切入 Manifest。`SUMMARY_ONLY + SELF_WRITTEN_SUMMARY` 表示只保留独立撰写摘要。

## 5. Loader

Loader 只扫描配置知识根下的 `.md`、`.yaml`、`.yml` 文件，采用 UTF-8、稳定相对路径排序和 SHA-256。它拒绝：

- 绝对路径、目录穿越和越界符号链接；
- 未知 Front Matter 字段、重复 ID、缺失来源和来源类型不一致；
- 缺失必需章节、HTML script 和远程 include；
- 超过 512 KiB 的单文件和非 UTF-8 文件。

隐藏文件、临时文件、`node_modules`、`dist`、`uploads` 和缓存目录不会被加载。错误消息使用相对路径，不输出机器绝对路径。

## 6. 确定性 Chunker

首版算法为：

```text
文档
-> Markdown 标题分段
-> 段落组合
-> 超长普通段落按句子边界继续拆分
```

列表、代码块和 Markdown 表格作为保护块，不在中间切断。无法找到安全语义边界的单个连续 token 会完整保留，而不是按固定字符粗切。

Chunk ID 为：

```text
<document-id>#<stable-section-path>#<global-ordinal>
```

内容使用 UTF-8 SHA-256。`estimated_token_count` 是稳定近似值，不是真实模型 Token 数，也不参与模型计费。

## 7. Manifest 与 root hash

`knowledge/manifests/corpus-v1.json` 保存文档、来源、Chunk、版本和统计。root hash 只基于：

- 排序后的 document ID 与文件 hash；
- 排序后的 source ID 与记录 hash；
- 排序后的 chunk ID 与内容 hash；
- chunker version；
- schema version。

`generated_at`、耗时、绝对路径、遍历顺序和机器信息不参与 root hash。因此相同输入在不同时间和机器上可得到相同语义标识。

构建使用同目录临时文件和原子替换。相同 root hash 不重复写入；不同结果默认拒绝覆盖；`--force` 只能替换派生 Manifest，不能改写知识源文档。

## 8. 状态策略

- `ACTIVE` 默认进入语料。
- `DRAFT` 仅在 `--include-draft` 时进入。
- `DEPRECATED` 仅在 `--include-deprecated` 时进入。
- `ARCHIVED` 不进入 active corpus。

状态过滤会改变 Manifest root hash，调用方必须明确使用一致构建参数。

## 9. 错误处理与隐私

所有领域错误使用 `KnowledgeCorpusError` 子类。CLI 返回非零退出码，不吞掉结构错误。Validator 检查明显的凭据、邮箱、手机号和本机路径模式；这是一道公开边界防线，不替代代码审查。

知识库不得包含真实用户训练记录、身份映射、Coach 对话、Provider Key、本地缓存或私有竞赛材料。

## 10. 后续 Retriever 接入点

后续阶段可读取已验证 Manifest，将 Chunk 内容交给 Embedding Provider 和 Vector Store。Retriever 必须返回 `chunk_id`、来源、版本和引用信息，并保持：

- 不修改确定性规则；
- 不把检索内容当成用户事实；
- 不允许知识结果触发写工具；
- 索引必须绑定 corpus root hash。
