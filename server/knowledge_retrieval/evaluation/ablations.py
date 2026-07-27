from __future__ import annotations

from dataclasses import dataclass

from server.knowledge_retrieval.evaluation.schemas import EvaluationMode


@dataclass(frozen=True)
class AblationDefinition:
    mode: EvaluationMode
    uses_retrieval: bool
    uses_metadata: bool
    materializes_references: bool
    replays_validator: bool
    evaluation_only_unsafe: bool = False


ABLATIONS = {
    mode: AblationDefinition(
        mode=mode,
        uses_retrieval=mode not in {
            EvaluationMode.NO_RETRIEVAL,
            EvaluationMode.NO_RAG,
        },
        uses_metadata=mode in {
            EvaluationMode.DENSE_WITH_METADATA,
            EvaluationMode.FULL_SYSTEM,
            EvaluationMode.NO_REFERENCE_MATERIALIZATION,
            EvaluationMode.NO_VALIDATOR_REPLAY,
        },
        materializes_references=mode != EvaluationMode.NO_REFERENCE_MATERIALIZATION,
        replays_validator=mode != EvaluationMode.NO_VALIDATOR_REPLAY,
        evaluation_only_unsafe=mode.unsafe_evaluation_only,
    )
    for mode in EvaluationMode
}
