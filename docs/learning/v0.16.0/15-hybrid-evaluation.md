# Hybrid Evaluation

The public report compares the unchanged Dense and BM25 baselines with Hybrid
RRF using the same 60 cases, filters and final top 4. Fixed candidate depth is
8 for each route; depth 4, 8 and 12 are reported only as Oracle diagnostics.

Results: Dense 43/60, BM25 52/60, Hybrid 47/60. Hybrid Recall@4 is 0.886667,
MRR@4 is 0.843333, nDCG@4 is 0.812712, and forbidden-document rate is
0.083333. Therefore Hybrid improves on Dense but regresses from BM25 and is not
promoted to the default strategy.
