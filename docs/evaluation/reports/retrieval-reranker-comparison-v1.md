# Reranker comparison v1

Status: `COMPLETED`.

This report stores no raw query, chunk text, vector, credential, or Provider response.

## dense

- Passed cases: 49/60
- Recall@4: 0.923333
- MRR@4: 0.873333
- nDCG@4: 0.857873
- Forbidden Document Rate: 0.083333
- Filter Violation Rate: 0.0

## bm25

- Passed cases: 52/60
- Recall@4: 0.956667
- MRR@4: 0.923333
- nDCG@4: 0.910589
- Forbidden Document Rate: 0.1
- Filter Violation Rate: 0.0

## hybrid_rrf

- Passed cases: 52/60
- Recall@4: 0.983333
- MRR@4: 0.933333
- nDCG@4: 0.924215
- Forbidden Document Rate: 0.1
- Filter Violation Rate: 0.0

## rerank

- Passed cases: 52/60
- Recall@4: 0.976667
- MRR@4: 0.901667
- nDCG@4: 0.902217
- Forbidden Document Rate: 0.1
- Filter Violation Rate: 0.0

## Provider reliability

- Success: 60
- Failure: 0
- Retried: 5
- Fallback: 0
