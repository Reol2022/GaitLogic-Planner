# Sparse Retrieval

Sparse Retrieval 用词项及其频率表示文本，而非把文本压缩为稠密向量。当前 `Bm25IndexService` 将已版本化的稳定 chunk 转成词频索引，写入独立的 `var/knowledge_bm25_indexes`。索引 manifest 绑定 corpus root hash、corpus manifest hash、策略、analyzer version、BM25 参数和 chunk hash；任一绑定变化都会让旧索引失效并要求重建。

中英混合语料不能直接套英文 stopword 或 stemming。`BM25Analyzer` 做 Unicode NFKC、小写化，保留技术术语、缩写和数字单位；中文同时生成单字和相邻双字 token。这个规则对所有内容一致，不针对评测案例增加 alias。

未来 Qdrant Sparse Adapter 可以接入相同的 public response 与 retriever 边界，但本阶段不依赖远程服务或 FastEmbed，以保证离线测试和可复现性。
