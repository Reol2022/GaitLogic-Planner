# Reciprocal Rank Fusion

RRF scores each candidate by `Σ 1 / (k + rank)` across result lists. GaitLogic
uses fixed equal weighting and `k=60`. It fuses ranks, not raw cosine and BM25
scores, because those scores have incompatible numerical meaning.

Stable tie-breaking is by `chunk_id`; duplicate chunks contribute at most one
rank per source. The production response retains its existing source-result
schema and never presents the internal RRF score as a user-facing confidence.
