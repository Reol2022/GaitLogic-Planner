# Oracle Candidate Analysis

An Oracle Candidate Recall asks a diagnostic-only question: did the union of
Dense and BM25 top-N candidates contain the labelled relevant document? It does
not create a product ranking and must never be exposed by the API.

For the public data, the union reaches 0.963889 at depth 4 and 1.0 at depths 8
and 12. When a relevant item is already in the candidate set but misses final
top 4, a reranker can be a meaningful next experiment. When it is absent from
the union, improve retrieval or corpus coverage instead.
