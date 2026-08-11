# Hybrid Retrieval Interview Guide

**Why not add Dense and BM25 scores directly?** Cosine similarity and BM25 use
different scales and distributions. RRF uses rank positions, avoiding a false
assumption that the scores are commensurate.

**Where does fusion belong?** At the application Retriever layer. That keeps
Exact and Qdrant Dense implementations replaceable and avoids coupling product
policy to a specific vector database client.

**How is safety preserved?** Both candidate generators apply category OR, tags
AND and exact language filters before fusion. Internal ranks and fusion scores
stay out of API responses and traces do not store query/chunk text.

**What did the evaluation show?** Hybrid RRF reached 47/60, between Dense
(43/60) and BM25 (52/60), with forbidden rate 0.083333. That is useful
complementarity evidence, not justification for a default switch.

**When should a reranker be tried?** Only after Oracle candidate analysis shows
relevant documents are already in the union but are ranked below top 4. The
current depth-8/12 oracle result is 1.0 on public cases, so a constrained,
separately evaluated reranker is a reasonable v0.16-D hypothesis.
