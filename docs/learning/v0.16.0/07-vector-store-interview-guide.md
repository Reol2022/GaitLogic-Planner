# 面试：可插拔向量检索怎么讲

## 代码在哪里

- 抽象与工厂：`server/knowledge_retrieval/vector_stores/base.py`、`factory.py`；
- Exact 基线：`exact_cosine.py`；
- Qdrant Adapter：`qdrant.py`；
- 索引生命周期：`index_service.py`、`index_manifest.py`；
- 查询边界：`retriever.py`；
- 对比评测：`scripts/evaluate_vector_store_parity.py`。

## 为什么这样设计

先保留 Exact Cosine 作为确定性小语料基线，再通过 Protocol 和 Factory 增加 Qdrant。这样 Agent、Tool Policy、Canonical Reference、Validator 和 TODAY 的确定性字段无需知道向量后端。Manifest 把 Store 类型写入索引身份，防止错误混用。

## 怎么测试

`tests/test_qdrant_vector_store.py` 验证构建、Cosine 查询、Filter、payload 脱敏和异常输入；`tests/test_qdrant_knowledge_index.py` 验证完整索引与 Retriever；`tests/test_vector_store_parity.py` 对未修改的 60 条公开集比较 Exact/Qdrant，并保留既有 43/60、17 个失败基线。

## 出过什么问题

Windows 本地 Qdrant 初版把 collection 存到长 staging 路径下，导致 WinError 206。修复不是缩短 Index ID 或放弃 staging，而是把本地 Qdrant 根固定为索引目录同级的受控 `.qdrant`，collection 仍由不可变 index identity 命名。

## 替代方案

可以直接让业务依赖 Qdrant SDK，但会让离线评测、回滚和未来 Store 替换变难。也可以马上加入 BM25/Hybrid/Reranker，但那会改变检索语义和评测基线；本阶段明确先只验证 Dense Store 替换。
