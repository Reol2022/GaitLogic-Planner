# Training Knowledge Vector Store v1

## 1. 为什么需要抽象

Retriever 不应绑定某个数据库产品。`VectorStore` 只暴露 build、search、validate 和 close，使后续可以在不改 Retriever 契约的情况下替换存储实现。

本阶段没有引入 LangChain 或 LlamaIndex，因为当前边界清晰，直接接口更容易审计版本、路径和安全行为。

## 2. Chroma 评估

当前环境没有 Chroma。对于60个 Chunk，引入 Chroma 会增加 Windows 原生依赖、NumPy/Pydantic 兼容面、telemetry 配置和依赖维护成本，而本阶段不需要 ANN 或独立服务。

因此首个实现采用 `ExactCosineVectorStore`：

- 纯本地持久化；
- 无网络和 telemetry；
- 无额外服务；
- 使用严格 Pydantic Record；
- 小语料精确全量 cosine 排序；
- pytest 使用 `tmp_path`。

未来语料规模扩大后，可在相同接口下评估 Chroma 或其他实现。

## 3. Vector Record

每条记录保存：

- Chunk/document ID；
- Chunk content SHA-256；
- vector；
- category、tags、language、status；
- source ID、knowledge version、section；
- 仓库相对路径。

不保存用户数据、查询、Coach 对话、API Key、机器路径或来源全文。

## 4. Cosine Similarity

分数方向统一为“越高越相似”，范围为 `[-1, 1]`。排序规则：

```text
score DESC
chunk_id ASC
```

同分时使用 Chunk ID 保证稳定排序。零范数、非有限值或维度不一致直接拒绝。

## 5. Metadata Filter

- categories：候选记录必须属于任一指定分类；
- tags：候选记录必须包含全部指定 tag；
- language：精确匹配；
- status：索引构建阶段只消费 ACTIVE Chunk。

过滤发生在得分返回之前，不由 LLM 解释。

## 6. 持久化和原子发布

默认目录：

```text
var/knowledge_indexes/<index-id>/
  index-manifest.json
  store/records.json
```

整个 `var/knowledge_indexes/` 已加入 `.gitignore`。

构建流程先写同目录临时目录，验证 Manifest、Chunk、向量数量、维度和 hash 后再原子替换。失败删除临时目录；force 替换时先保留备份，发布失败恢复旧索引。

相同 root hash 返回 unchanged；不同结果默认拒绝覆盖；force 只操作派生索引。

## 7. 损坏检测与关闭

Store 加载使用严格 Schema，检查重复 Chunk ID、维度、有限数值和记录数量。Index Service 还会逐条核对内容 hash 与 vector hash。损坏或过期索引不会降级为“空结果”。

Store 不保持数据库后台线程；`close()` 后拒绝继续使用，明确资源生命周期。
