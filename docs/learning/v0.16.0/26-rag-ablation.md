# RAG Ablation

An ablation changes one bounded retrieval strategy while retaining the same Corpus, filters, top-k and frozen labels. v0.16 compares Dense Exact, optional Dense Qdrant, BM25, Hybrid RRF and Rerank. It reports pass rate, Recall@4, MRR@4, nDCG@4, forbidden-document rate, filter violations and latency rather than inventing one weighted score.
