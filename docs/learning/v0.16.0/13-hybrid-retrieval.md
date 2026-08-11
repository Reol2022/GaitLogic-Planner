# Hybrid Retrieval

Hybrid Retrieval combines independently generated Dense and BM25 candidate
lists. In GaitLogic it lives in `server/knowledge_retrieval/hybrid/`, above the
Retriever implementations and below the public response materialisation. It
does not depend on `QdrantClient`: Exact Dense + BM25 and Qdrant Dense + BM25
remain interchangeable.

Each retriever applies the same metadata filter before fusion. Candidates are
aligned by stable `chunk_id`, deduplicated, fused, then truncated to the public
top-k. The public API exposes neither source ranks nor fusion scores; Canonical
Reference materialisation remains server-controlled.
