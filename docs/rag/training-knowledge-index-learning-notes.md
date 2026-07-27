# Training Knowledge Index 学习笔记

## 文档 Embedding 与 Query Embedding

索引阶段把60个知识 Chunk 转成向量；查询阶段只把当前问题转成向量。两者必须使用相同模型和维度，否则 cosine 分数没有可比性。

## 为什么不直接依赖 LangChain

当前需要的流程很小：读取 Manifest、批量 Embedding、保存向量、精确过滤和返回引用。直接实现严格接口可以看清每个字段、路径、重试和错误；引入大型编排框架会扩大依赖和隐式行为。

## 为什么当前用 Exact Cosine Store

60个 Chunk 做全量 cosine 比较成本极低。Exact Store 没有近似索引误差、后台服务或 telemetry，更适合验证基础契约。它不是未来规模化方案的承诺。

## Index Manifest 如何工作

Index Manifest 同时绑定：

- Corpus root hash 和 Manifest 文件 hash；
- Provider、模型、维度与归一化；
- Vector Store 和距离指标；
- 每个 Chunk 的内容 hash；
- 每个向量的二进制 SHA-256。

`created_at` 不进入 root hash。确定性 Provider 重复构建得到相同 root hash；远程 Provider 则只能保证配置和输入可追踪。

## 为什么真实远程模型不一定可重复

供应商可能在不改变公开模型别名时升级模型。相同文本日后可能返回不同向量。因此索引报告必须区分“语料确定性”和“供应商向量可重复性”。

## build 流程

```text
Validate Corpus Manifest
-> Select ACTIVE chunks
-> Embed in controlled batches
-> Validate count/dimensions/finite values
-> Build records in temporary directory
-> Write Index Manifest
-> Validate hashes and bindings
-> Atomic publish
```

dry-run 只计算 Chunk 数和批次数，不调用远程 Embedding。

## query 流程

```text
Validate current Corpus and Index
-> Validate Provider binding
-> Embed query
-> Exact cosine + metadata filters
-> Stable sort
-> Map Chunk and Source metadata
-> Return source excerpt
```

没有 LLM，也不持久化查询。

## 如何排查失败

- `Index corpus root hash is stale`：语料改变后需要重建索引。
- `dimensions do not match`：Provider 配置或模型改变。
- `vector hash is invalid`：Store 文件损坏或被修改。
- `provider is disabled`：远程 Embedding 默认关闭。
- 空结果：检查 category/tag/language/min_score，不能当作系统异常。

## 项目负责人验收清单

- [ ] deterministic_test 在 production 拒绝启用。
- [ ] 远程 Provider Key 与 Coach 配置完全独立。
- [ ] HTTP 禁止重定向并执行 SSRF 防护。
- [ ] 自动测试不访问网络。
- [ ] Index 目录已 Git 忽略。
- [ ] Manifest 不含 Key、绝对路径或机器信息。
- [ ] 重复确定性构建 root hash 一致。
- [ ] 过滤和同分排序稳定。
- [ ] 查询没有写入 Index 或数据库。
- [ ] Retriever 没有 Agent 依赖。
- [ ] 尚未注册 Agent Tool。
- [ ] deterministic_test 排序没有被宣传为语义质量。
