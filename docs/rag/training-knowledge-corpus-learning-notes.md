# Training Knowledge Corpus 学习笔记

## RAG 解决什么问题

结构化工具擅长回答“这个用户最近跑了多少”，确定性规则擅长回答“产品允许做出什么状态判断”，但它们不适合承载大量理论解释、适用条件和来源。RAG 的职责是从受控语料中找到相关解释材料，再交给模型组织表达。

检索到的文字不是新事实，也不能覆盖规则输出。

## 为什么数据库不等于知识库

业务数据库保存用户、计划、训练日志和同步活动，强调事务、一致性和权限。知识语料强调来源、版本、章节结构、切分和引用。把书面原则塞进业务表既不能形成可靠检索，也会把公开材料与用户隐私混在一起。

## 为什么规则不能全部放 Prompt

Prompt 难以独立测试、版本化和审计，模型还可能忽略它。决定状态、风险和权限的规则必须保留在确定性代码与配置中；知识文档只解释规则背景和限制。

## 为什么 Chunk 不是随便截断

固定字符切分会拆坏列表、代码、表格和论证上下文。首版 Chunker 先理解 Markdown 标题，再组合自然段；只有普通超长段落才沿句子边界拆分。这样生成的引用更容易被人检查。

## 为什么来源和版本重要

同一个训练问题可能存在不同观点，内容也会随评审更新。`source_id` 说明材料从哪里来，`knowledge_version` 说明使用的是哪一版，Manifest root hash 则绑定整个语料状态。缺少这些信息，检索回答无法复现。

## 为什么不立即上向量数据库

如果 Schema、来源和 Chunk 都不稳定，向量索引只会快速放大混乱。本阶段先证明语料可验证、可重复构建、可安全公开；下一阶段再比较 Embedding 和 Vector Store。

## 为什么不能复制书籍全文

购买书籍不等于获得再发布权。公开仓库只能保存原创内容、明确许可内容或自己撰写的摘要。书名、作者和出版信息用于引用，不授权复制正文、训练表或课程材料。

## Manifest 和 root hash 如何工作

Manifest 是语料构建后的清单。它列出每个文档、来源和 Chunk 的稳定 hash。root hash 把排序后的稳定标识再次计算 SHA-256：

```text
documents + sources + chunks + schema version + chunker version
-> canonical JSON
-> SHA-256 root hash
```

生成时间不参与，因此同一语料重复构建 root hash 不变。任何文档、来源或 Chunk 内容变化都会改变对应 hash，进而改变 root hash。

## 后续 Embedding 如何接入

v0.12.0-B 应从已验证 Manifest 读取 Chunk，记录 `corpus root hash + embedding model version + vector record ID`。构建新索引时不能覆盖未知旧索引；Retriever 返回结果时必须携带 Chunk 和来源引用。

Embedding 是派生资产，不应提交真实用户数据，也不能把 Provider Key 写入索引或报告。

## 项目负责人验收清单

- [ ] `server/knowledge_retrieval` 没有依赖 Agent。
- [ ] 现有确定性规则没有搬入 documents。
- [ ] 12 篇示例均为原创或自写摘要。
- [ ] Loader 拒绝越界路径、未知字段和缺失来源。
- [ ] Chunk ID 与内容 hash 重复构建稳定。
- [ ] `generated_at` 不影响 root hash。
- [ ] Manifest 不含绝对路径和机器信息。
- [ ] CLI 支持 validate/build/list/inspect。
- [ ] 默认排除 draft、deprecated 和 archived。
- [ ] 没有 Embedding、Vector Store、Retriever 或 Agent Tool。
- [ ] 没有真实用户数据、凭据和私有竞赛材料。
