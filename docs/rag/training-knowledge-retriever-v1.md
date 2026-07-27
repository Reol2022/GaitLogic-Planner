# Training Knowledge Retriever v1

## 1. 职责

`TrainingKnowledgeRetriever` 接收结构化查询，生成 Query Embedding，在已验证索引中搜索，并把结果映射回 Corpus Chunk 与来源。

Retriever：

- 不调用 LLM；
- 不生成回答或总结；
- 不重新解释知识；
- 不读写用户数据库；
- 不持久化查询；
- 目前不注册为 Agent Tool。

## 2. 请求

```json
{
  "query": "最近疲劳较高是否应该减少间歇训练",
  "top_k": 4,
  "categories": ["RECOVERY"],
  "tags": ["fatigue"],
  "language": "zh-CN",
  "min_score": null
}
```

`top_k` 范围1～10，query 去除首尾空白后不能为空，最大4000字符。Category 使用枚举，tag 和 language 使用精确 metadata filter。

## 3. 响应

每个结果包含 rank、score、Chunk/document ID、标题、章节、最多600字符原文 excerpt、分类、标签、来源、知识版本、证据等级、相对路径和限制。

Excerpt 只能从保存的 Chunk 原文截取，不由模型改写，也不返回完整文档。

## 4. Index 绑定

每次检索前验证：

- 当前 Corpus root hash；
- Corpus Manifest 文件 SHA-256；
- Index Manifest root hash 和 Index ID；
- Embedding provider/model/dimensions；
- Vector Store 类型和 cosine 指标；
- Chunk ID、内容 hash、vector hash 和记录数量。

任一不匹配都拒绝使用索引，不自动选择另一个 Provider。

## 5. 空结果与限制

没有匹配项时返回空 `results` 和结构化 limitation，不伪造相似知识。使用 deterministic_test 时响应始终说明它只验证索引链路，不代表语义检索质量。

## 6. 安全与隐私

- 查询只存在于调用栈和返回值；
- 不写文件、数据库或普通日志；
- 结果不含绝对路径、Key、向量和用户身份；
- deprecated/archived 默认不进入索引；
- Retriever 不能触发训练计划写入。

## 7. 下一阶段接入点

v0.12.0-C 可把 Retriever 包装成只读 `retrieve_training_knowledge` Agent Tool。Tool 必须由服务端注入索引和 Provider，限制 top_k/filter，并清楚区分：

```text
Training Tools -> 用户事实
Knowledge Tool -> 理论与来源
Rule Engine -> 决策边界
```

知识结果不能覆盖确定性 Runner State、Training Readiness 或今日建议。
