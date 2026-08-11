# RAG Evaluation Complete Guide

Use Legacy v1 for regression and Holdout v2 for generalization. Recall measures coverage, MRR measures the first relevant result, and nDCG rewards high-ranked, graded relevance. Forbidden-document analysis shows whether a labelled inappropriate document entered top-k. Qdrant changes index implementation and scalability, not semantic quality by itself. Oracle candidate recall is a diagnostic: a perfect candidate union may justify reranking, but it is not production quality.
