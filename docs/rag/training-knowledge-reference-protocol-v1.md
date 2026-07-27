# Canonical Knowledge Reference Protocol v1

## 为什么需要引用协议

模型可以选择知识，但不能成为知识来源。若直接信任模型返回的书名、URL、excerpt
或引用正文，就无法证明它们来自当前索引。协议因此把“选择”和“还原”分开：

```text
Canonical Retriever Result
→ request-local knowledge_n
→ Provider selects IDs
→ deterministic validation
→ server materializes public references
```

## 请求级 Catalog

每次成功检索按排名生成 `knowledge_1...n`。ID：

- 只在当前请求有效；
- 不使用 Python `hash()`；
- 不持久化；
- 不进入普通日志或 Trace；
- 不暴露到公共 API；
- 一次请求只允许一次知识检索，避免多个 Catalog 产生 ID 冲突。

Provider Context 可以看到受控 Catalog，但只能在
`knowledge_reference_ids` 中返回精确 ID。空白、未知、重复、大小写变化和数字 ID
都会被拒绝。没有成功检索时，非空引用同样被拒绝。

## Canonical Materialization

Validator 通过后，服务端从 Tool Result 中还原公开结构：

```json
{
  "document_id": "recovery-principles",
  "title": "恢复训练原则",
  "section": "核心原则",
  "source_id": "public-guidance-summary",
  "source_title": "Public Guidance Summary",
  "knowledge_version": "1.0.0",
  "evidence_level": "SECONDARY",
  "excerpt": "Canonical Chunk excerpt.",
  "limitations": []
}
```

公共响应不包含：

- `knowledge_reference_id`
- score
- chunk ID
- relative/absolute path
- 向量
- Provider 原始输出

Excerpt 只取自 Corpus Manifest 的 Canonical Chunk。模型不能提供或修改引用正文。

## Validator 规则

Validator 确定性检查：

- 未检索却声称“根据知识库”；
- 未检索或检索失败却返回 ID；
- 未知、重复或非法 ID；
- GENERAL 成功检索后缺少引用；
- 空结果或失败缺少 limitation；
- 复制 Canonical excerpt 到模型正文；
- 输出 Source Title、URL、论文、书籍、研究或指南式虚构来源；
- EXPLAIN 创造个人训练数字；
- GENERAL 虚构个人训练状态；
- TODAY 改变确定性字段。

校验不使用模糊匹配、Embedding 二次判定或第二个 LLM 裁判。引用按 Canonical
Catalog 原始顺序输出，而不是信任模型排序。

## Evidence 与 Knowledge Reference

两种引用不能混淆：

- `evidence_n` 指向用户当前请求中的确定性训练事实；
- `knowledge_n` 指向版本化训练知识 Chunk。

TODAY 可以同时选择 Evidence 和 Knowledge，但后者只能解释前者，不能改变
decision。公共 API 继续在 `today_recommendation.key_evidence` 返回 Canonical
Evidence，并在顶层可选 `knowledge_references` 返回知识引用。

## 安全边界

Tool Summary 只返回工具名、状态和安全错误码。用户 query、excerpt、完整来源、
Provider 原始响应和内部 ID 不进入 Summary。日志不得记录 query 正文，公共 OpenAPI
也不包含 Provider 内部 Schema。
