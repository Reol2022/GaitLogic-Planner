from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.knowledge_retrieval.evaluation.schemas import (
    EvaluationMode,
    RetrievalEvaluationCase,
)


def test_retrieval_case_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RetrievalEvaluationCase.model_validate(
            {
                "case_id": "ret_valid_001",
                "query": "虚构查询",
                "unknown": True,
            }
        )


def test_abstention_case_rejects_relevance_labels() -> None:
    with pytest.raises(ValidationError, match="abstention"):
        RetrievalEvaluationCase.model_validate(
            {
                "case_id": "ret_abstain_invalid",
                "query": "虚构查询",
                "should_abstain": True,
                "relevant_documents": [
                    {"document_id": "document", "relevance": 3}
                ],
            }
        )


def test_unsafe_ablations_are_explicitly_labelled() -> None:
    assert EvaluationMode.NO_REFERENCE_MATERIALIZATION.unsafe_evaluation_only
    assert EvaluationMode.NO_VALIDATOR_REPLAY.unsafe_evaluation_only
    assert not EvaluationMode.FULL_SYSTEM.unsafe_evaluation_only
