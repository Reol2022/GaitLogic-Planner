from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.agent.enums import AgentIntent
from server.agent.knowledge_references import KNOWLEDGE_TOOL_NAME
from server.agent.tools.factory import COACH_AGENT_TOOL_NAMES
from server.knowledge_retrieval.enums import KnowledgeCategory

EVALUATION_VERSION = "training-knowledge-eval-1.0.0"
RETRIEVAL_DATASET_VERSION = "retrieval-cases-v1"
RAG_DATASET_VERSION = "rag-answer-cases-v1"


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RetrievalFilters(StrictEvaluationModel):
    categories: list[KnowledgeCategory] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class RelevantDocument(StrictEvaluationModel):
    document_id: str = Field(min_length=1, max_length=160)
    relevance: int = Field(ge=1, le=3)


class RetrievalEvaluationCase(StrictEvaluationModel):
    case_id: str = Field(pattern=r"^ret_[a-z0-9_]{3,80}$")
    query: str = Field(min_length=2, max_length=500)
    language: Literal["zh-CN", "en-US"] = "zh-CN"
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    relevant_documents: list[RelevantDocument] = Field(default_factory=list)
    acceptable_chunk_ids: list[str] = Field(default_factory=list)
    forbidden_document_ids: list[str] = Field(default_factory=list)
    should_abstain: bool = False
    notes: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_labels(self) -> "RetrievalEvaluationCase":
        relevant = [item.document_id for item in self.relevant_documents]
        if len(relevant) != len(set(relevant)):
            raise ValueError("relevant document IDs must be unique")
        if set(relevant) & set(self.forbidden_document_ids):
            raise ValueError("a document cannot be both relevant and forbidden")
        if self.should_abstain and self.relevant_documents:
            raise ValueError("abstention cases cannot declare relevant documents")
        return self


class RetrievalDataset(StrictEvaluationModel):
    dataset_version: str = RETRIEVAL_DATASET_VERSION
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[RetrievalEvaluationCase] = Field(min_length=60)


class RagAnswerEvaluationCase(StrictEvaluationModel):
    case_id: str = Field(pattern=r"^rag_[a-z0-9_]{3,80}$")
    intent: AgentIntent
    question: str = Field(min_length=2, max_length=1000)
    fictional_context: str = Field(min_length=1, max_length=160)
    expected_tools: list[str] = Field(default_factory=list)
    required_knowledge_categories: list[KnowledgeCategory] = Field(default_factory=list)
    citation_required: bool = False
    canonical_today_facts: dict[str, str] = Field(default_factory=dict)
    required_limitations: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    allowed_numeric_facts: list[str] = Field(default_factory=list)
    expected_status: list[
        Literal["SUCCEEDED", "DEGRADED", "VALIDATION_FAILED", "REJECTED", "UNAVAILABLE"]
    ] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_contract(self) -> "RagAnswerEvaluationCase":
        allowed_intents = {
            AgentIntent.TODAY_RECOMMENDATION,
            AgentIntent.EXPLAIN_RUNNER_STATE,
            AgentIntent.GENERAL_TRAINING_QUESTION,
        }
        if self.intent not in allowed_intents:
            raise ValueError("RAG evaluation only supports public Coach intents")
        registered_tools = COACH_AGENT_TOOL_NAMES | {KNOWLEDGE_TOOL_NAME}
        unknown = set(self.expected_tools) - registered_tools
        if unknown:
            raise ValueError(f"unknown tool names: {sorted(unknown)}")
        if self.intent != AgentIntent.TODAY_RECOMMENDATION and self.canonical_today_facts:
            raise ValueError("only TODAY cases may declare canonical today facts")
        return self


class RagAnswerDataset(StrictEvaluationModel):
    dataset_version: str = RAG_DATASET_VERSION
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[RagAnswerEvaluationCase] = Field(min_length=36)


class EvaluationMode(str, Enum):
    NO_RETRIEVAL = "NO_RETRIEVAL"
    NO_RAG = "NO_RAG"
    LEXICAL_ONLY = "LEXICAL_ONLY"
    DENSE_NO_METADATA = "DENSE_NO_METADATA"
    DENSE_WITH_METADATA = "DENSE_WITH_METADATA"
    FULL_SYSTEM = "FULL_SYSTEM"
    NO_REFERENCE_MATERIALIZATION = "NO_REFERENCE_MATERIALIZATION"
    NO_VALIDATOR_REPLAY = "NO_VALIDATOR_REPLAY"

    @property
    def unsafe_evaluation_only(self) -> bool:
        return self in {
            self.NO_REFERENCE_MATERIALIZATION,
            self.NO_VALIDATOR_REPLAY,
        }


class RankedItem(StrictEvaluationModel):
    rank: int = Field(ge=1)
    chunk_id: str
    document_id: str
    score: float


class RetrievalCaseResult(StrictEvaluationModel):
    case_id: str
    passed: bool
    should_abstain: bool
    abstained: bool
    ranked_items: list[RankedItem]
    metrics: dict[str, float]
    failure_codes: list[str] = Field(default_factory=list)
    duration_ms: float = Field(ge=0)


class RagCaseResult(StrictEvaluationModel):
    case_id: str
    passed: bool
    intent: AgentIntent
    status: str
    context_tools: list[str]
    model_tools: list[str]
    reference_document_ids: list[str]
    validation_codes: list[str]
    safe_error_codes: list[str]
    flags: list[str]
    metrics: dict[str, float]
    duration_ms: float = Field(ge=0)


class TrainingKnowledgeEvaluationReport(StrictEvaluationModel):
    evaluation_version: str = EVALUATION_VERSION
    evaluation_kind: Literal["retrieval", "rag"]
    dataset_version: str
    dataset_sha256: str
    corpus_root_hash: str
    index_id: str | None = None
    provider: str
    model: str
    mode: EvaluationMode
    real_provider: bool
    raw_answers_saved: bool = False
    generated_at: str
    result_hash: str
    case_count: int
    metrics: dict[str, float]
    category_metrics: dict[str, dict[str, float]] = Field(default_factory=dict)
    failure_case_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    cases: list[RetrievalCaseResult | RagCaseResult]
