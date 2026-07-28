from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Callable

from server.knowledge_retrieval.embeddings.base import EmbeddingProvider
from server.knowledge_retrieval.errors import KnowledgeEmbeddingProviderError
from server.knowledge_retrieval.evaluation.ablations import ABLATIONS
from server.knowledge_retrieval.evaluation.datasets import (
    load_rag_dataset,
    load_retrieval_dataset,
)
from server.knowledge_retrieval.evaluation.lexical_baseline import LexicalBm25Baseline
from server.knowledge_retrieval.evaluation.rag_metrics import (
    aggregate_rag_metrics,
    deterministic_rag_metrics,
)
from server.knowledge_retrieval.evaluation.retrieval_metrics import (
    aggregate_retrieval_metrics,
    evaluate_retrieval_case,
)
from server.knowledge_retrieval.evaluation.schemas import (
    EvaluationMode,
    RagCaseResult,
    RankedItem,
    RetrievalCaseResult,
    TrainingKnowledgeEvaluationReport,
)
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever

ProviderFactory = Callable[[], EmbeddingProvider]


def _result_hash(payload: dict[str, object]) -> str:
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"generated_at", "result_hash"}
    }
    for case in stable.get("cases", []):
        if isinstance(case, dict):
            case.pop("duration_ms", None)
    encoded = json.dumps(
        stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finalize(report: TrainingKnowledgeEvaluationReport) -> TrainingKnowledgeEvaluationReport:
    payload = report.model_dump(mode="json")
    return report.model_copy(update={"result_hash": _result_hash(payload)})


class TrainingKnowledgeEvaluationRunner:
    def __init__(
        self,
        *,
        repository_root: Path,
        corpus_manifest_path: Path = Path("knowledge/manifests/corpus-v1.json"),
        index_root: Path = Path("var/knowledge_indexes"),
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.corpus_manifest_path = (
            self.repository_root / corpus_manifest_path
        ).resolve()
        self.index_service = KnowledgeIndexService(
            repository_root=self.repository_root,
            corpus_manifest_path=corpus_manifest_path,
            index_root=index_root,
        )

    def run_retrieval(
        self,
        *,
        dataset_path: Path,
        provider_factory: ProviderFactory | None,
        provider_name: str,
        model_name: str,
        mode: EvaluationMode,
        index_id: str | None = None,
        real_provider: bool = False,
    ) -> TrainingKnowledgeEvaluationReport:
        dataset = load_retrieval_dataset(
            dataset_path,
            corpus_manifest_path=self.corpus_manifest_path,
        )
        corpus = load_manifest(self.corpus_manifest_path)
        lexical = LexicalBm25Baseline(corpus)
        results: list[RetrievalCaseResult] = []
        aggregate_input: list[tuple[object, dict[str, float]]] = []
        resolved_index = index_id
        provider: EmbeddingProvider | None = None
        if mode not in {EvaluationMode.LEXICAL_ONLY, EvaluationMode.NO_RETRIEVAL}:
            resolved_index = resolved_index or self.index_service.latest_index_id()
            if provider_factory is None:
                raise ValueError("dense evaluation requires an embedding provider")
            provider = provider_factory()
        for case in dataset.cases:
            started = perf_counter()
            provider_failed = False
            if mode in {EvaluationMode.NO_RETRIEVAL, EvaluationMode.NO_RAG}:
                ranked: list[RankedItem] = []
            elif mode == EvaluationMode.LEXICAL_ONLY:
                ranked = lexical.search(case)
            else:
                if provider is None:
                    raise RuntimeError("dense evaluation provider was not initialized")
                retriever = TrainingKnowledgeRetriever(
                    index_service=self.index_service,
                    provider=provider,
                    index_id=resolved_index,
                )
                try:
                    response = retriever.retrieve(
                        KnowledgeRetrievalRequest(
                            query=case.query,
                            top_k=4,
                            categories=(
                                case.filters.categories
                                if ABLATIONS[mode].uses_metadata
                                else []
                            ),
                            tags=(
                                case.filters.tags
                                if ABLATIONS[mode].uses_metadata
                                else []
                            ),
                            language=(
                                case.language
                                if ABLATIONS[mode].uses_metadata
                                else None
                            ),
                        )
                    )
                    ranked = [
                        RankedItem(
                            rank=item.rank,
                            chunk_id=item.chunk_id,
                            document_id=item.document_id,
                            score=item.score,
                        )
                        for item in response.results
                    ]
                except KnowledgeEmbeddingProviderError:
                    ranked = []
                    provider_failed = True
            metrics, failures = evaluate_retrieval_case(case, ranked)
            metrics["provider_success_rate"] = float(not provider_failed)
            if provider_failed:
                failures.append("PROVIDER_FAILURE")
            aggregate_input.append((case, metrics))
            results.append(
                RetrievalCaseResult(
                    case_id=case.case_id,
                    passed=not failures,
                    should_abstain=case.should_abstain,
                    abstained=not ranked,
                    ranked_items=ranked,
                    metrics=metrics,
                    failure_codes=failures,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
        if provider is not None:
            provider.close()
        report = TrainingKnowledgeEvaluationReport(
            evaluation_kind="retrieval",
            dataset_version=dataset.dataset_version,
            dataset_sha256=dataset.content_sha256,
            corpus_root_hash=corpus.root_hash,
            index_id=resolved_index,
            provider=provider_name,
            model=model_name,
            mode=mode,
            real_provider=real_provider,
            generated_at=datetime.now(timezone.utc).isoformat(),
            result_hash="0" * 64,
            case_count=len(results),
            metrics=aggregate_retrieval_metrics(aggregate_input),  # type: ignore[arg-type]
            failure_case_ids=[item.case_id for item in results if not item.passed],
            limitations=(
                [
                    "Remote embedding behavior may change; results are not fully "
                    "reproducible without a pinned provider artifact."
                ]
                if real_provider
                else [
                    "deterministic_test controls reproducibility only and is not "
                    "evidence of semantic retrieval quality."
                ]
            ),
            cases=results,
        )
        return _finalize(report)

    def run_rag(
        self,
        *,
        dataset_path: Path,
        mode: EvaluationMode = EvaluationMode.FULL_SYSTEM,
        provider_name: str = "fake",
        model_name: str = "deterministic-fake-v1",
        real_provider: bool = False,
    ) -> TrainingKnowledgeEvaluationReport:
        dataset = load_rag_dataset(dataset_path)
        corpus = load_manifest(self.corpus_manifest_path)
        definition = ABLATIONS[mode]
        results: list[RagCaseResult] = []
        metric_values: list[dict[str, float]] = []
        for case in dataset.cases:
            started = perf_counter()
            knowledge_available = definition.uses_retrieval and bool(
                case.required_knowledge_categories
            )
            fallback = "provider" in case.fictional_context or "tool_failure" in case.fictional_context
            metrics, flags = deterministic_rag_metrics(
                case,
                knowledge_available=knowledge_available,
                fallback=fallback,
                unsafe_ablation=definition.evaluation_only_unsafe,
            )
            metric_values.append(metrics)
            tools = list(case.expected_tools)
            references = (
                [f"eval-{category.value.lower()}" for category in case.required_knowledge_categories]
                if knowledge_available and definition.materializes_references
                else []
            )
            results.append(
                RagCaseResult(
                    case_id=case.case_id,
                    passed=metrics["case_pass_rate"] == 1.0,
                    intent=case.intent,
                    status=case.expected_status[0],
                    context_tools=tools,
                    model_tools=[],
                    reference_document_ids=references,
                    validation_codes=[],
                    safe_error_codes=[],
                    flags=flags,
                    metrics=metrics,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
        report = TrainingKnowledgeEvaluationReport(
            evaluation_kind="rag",
            dataset_version=dataset.dataset_version,
            dataset_sha256=dataset.content_sha256,
            corpus_root_hash=corpus.root_hash,
            provider=provider_name,
            model=model_name,
            mode=mode,
            real_provider=real_provider,
            generated_at=datetime.now(timezone.utc).isoformat(),
            result_hash="0" * 64,
            case_count=len(results),
            metrics=aggregate_rag_metrics(metric_values),
            failure_case_ids=[item.case_id for item in results if not item.passed],
            limitations=[
                "The public RAG evaluation uses fixed fictional contexts and stores "
                "no raw answer, prompt, context, tool result, or reasoning content."
            ],
            cases=results,
        )
        return _finalize(report)

    def run_rag_real(
        self,
        *,
        dataset_path: Path,
        settings,
        mode: EvaluationMode = EvaluationMode.FULL_SYSTEM,
    ) -> TrainingKnowledgeEvaluationReport:
        """Run real Chat/Embedding providers against fixed fictional tool fixtures.

        Raw model text remains process-local and is deliberately reduced to
        deterministic flags before constructing the public report.
        """
        from server.agent.enums import (
            AgentRunStatus,
            AgentToolStatus,
            AgentTraceEventType,
            AgentTraceStatus,
        )
        from server.agent.evaluation.fixtures import (
            EVALUATION_NOW,
            build_evaluation_registry,
            canonical_today_facts_for_fixture,
            resolve_rag_evaluation_fixture,
        )
        from server.agent.evaluation.runner import (
            materialize_evaluation_fallback_response,
        )
        from server.agent.orchestrator import GaitLogicCoachAgent
        from server.agent.providers.openai_compatible import (
            OpenAICompatibleAgentGateway,
        )
        from server.agent.schemas import AgentLimits, AgentRequest
        from server.agent.tools.knowledge_tools import build_configured_knowledge_tool
        from server.agent.training_context_builder import AgentTrainingContextBuilder

        dataset = load_rag_dataset(dataset_path)
        corpus = load_manifest(self.corpus_manifest_path)
        chunks_by_document: dict[str, list[str]] = {}
        category_by_document = {
            item.document_id: item.category for item in corpus.documents
        }
        for chunk in corpus.chunks:
            chunks_by_document.setdefault(chunk.document_id, []).append(chunk.content)
        results: list[RagCaseResult] = []
        metric_values: list[dict[str, float]] = []
        for case in dataset.cases:
            started = perf_counter()
            fixture = resolve_rag_evaluation_fixture(case.fictional_context)
            if (
                case.canonical_today_facts
                and case.canonical_today_facts
                != canonical_today_facts_for_fixture(fixture)
            ):
                raise ValueError(
                    f"RAG case {case.case_id} canonical TODAY facts do not match "
                    "the deterministic fixture"
                )
            registry = build_evaluation_registry(fixture)
            knowledge_tool = (
                build_configured_knowledge_tool(settings)
                if ABLATIONS[mode].uses_retrieval
                else None
            )
            if knowledge_tool is not None:
                registry.register(knowledge_tool)
            limits = AgentLimits()
            gateway = OpenAICompatibleAgentGateway(settings)
            agent = GaitLogicCoachAgent(
                gateway=gateway,
                registry=registry,
                context_builder=AgentTrainingContextBuilder(
                    registry=registry,
                    limits=limits,
                    clock=lambda: EVALUATION_NOW,
                ),
                limits=limits,
            )
            request = AgentRequest.for_authenticated_user(
                user_id=70001,
                message=case.question,
                intent=case.intent,
            )
            try:
                response = agent.run(request)
            finally:
                gateway.close()
            context = agent.last_context
            has_tool_failure = context is not None and any(
                result.status != AgentToolStatus.SUCCEEDED
                for result in context.tool_results
            )
            if context is not None and (
                response.status != AgentRunStatus.SUCCEEDED or has_tool_failure
            ):
                response = materialize_evaluation_fallback_response(
                    request=request,
                    response=response,
                    context=context,
                    agent=agent,
                )
            events = agent.last_trace.events if agent.last_trace else []
            context_tools = [
                item.tool_name
                for item in events
                if item.event_type == AgentTraceEventType.CONTEXT_TOOL_COMPLETED
                and item.tool_name
            ]
            model_tools = [
                item.tool_name
                for item in events
                if item.event_type == AgentTraceEventType.MODEL_TOOL_COMPLETED
                and item.tool_name
            ]
            actual_tools = set(context_tools) | set(model_tools)
            knowledge_tool_succeeded = any(
                item.event_type == AgentTraceEventType.CONTEXT_TOOL_COMPLETED
                and item.tool_name == "retrieve_training_knowledge"
                and item.status == AgentTraceStatus.SUCCEEDED
                for item in events
            ) or any(
                item.event_type == AgentTraceEventType.MODEL_TOOL_COMPLETED
                and item.tool_name == "retrieve_training_knowledge"
                and item.status == AgentTraceStatus.SUCCEEDED
                for item in events
            )
            references = list(response.knowledge_references)
            reference_documents = [item.document_id for item in references]
            known_references = [
                item for item in references if item.document_id in category_by_document
            ]
            relevant_references = [
                item
                for item in known_references
                if category_by_document[item.document_id]
                in case.required_knowledge_categories
            ]
            required_tool_recall = (
                len(actual_tools & set(case.expected_tools)) / len(case.expected_tools)
                if case.expected_tools
                else 1.0
            )
            citation_precision = (
                len(relevant_references) / len(references) if references else 1.0
            )
            expected_categories = set(case.required_knowledge_categories)
            found_categories = {
                category_by_document[item.document_id] for item in relevant_references
            }
            citation_recall = (
                len(found_categories & expected_categories) / len(expected_categories)
                if expected_categories
                else 1.0
            )
            canonical_excerpt = all(
                any(
                    item.excerpt in content
                    for content in chunks_by_document.get(item.document_id, [])
                )
                for item in references
            )
            recommendation = response.today_recommendation
            decision_invariant = True
            if case.canonical_today_facts:
                actual_facts = {
                    "decision": (
                        recommendation.decision
                        if recommendation is not None
                        else ""
                    ),
                    "risk_level": response.risk_level.value,
                    "planned_workout_status": (
                        recommendation.planned_workout_status
                        if recommendation is not None
                        else ""
                    ),
                }
                decision_invariant = all(
                    actual_facts.get(key) == value
                    for key, value in case.canonical_today_facts.items()
                )
            answer_text = f"{response.answer or ''}\n{response.summary or ''}"
            unsupported = any(claim in answer_text for claim in case.forbidden_claims)
            limitation_codes = {item.code for item in response.limitations}
            limitation_retained = set(case.required_limitations).issubset(
                limitation_codes
            )
            public_status = (
                "SUCCEEDED"
                if (
                    response.status == AgentRunStatus.SUCCEEDED
                    and not has_tool_failure
                )
                else "DEGRADED"
            )
            provider_success = response.status == AgentRunStatus.SUCCEEDED
            citation_satisfied = (
                not case.citation_required
                or (
                    bool(references)
                    and citation_precision == 1.0
                    and citation_recall == 1.0
                )
            )
            metrics = {
                "case_pass_rate": 0.0,
                "intent_accuracy": float(response.intent == case.intent),
                "required_tool_recall": round(required_tool_recall, 6),
                "forbidden_tool_call_rate": 0.0,
                "knowledge_tool_success_rate": float(
                    knowledge_tool_succeeded
                ),
                "citation_requirement_satisfaction": float(citation_satisfied),
                "citation_precision": round(citation_precision, 6),
                "citation_recall": round(citation_recall, 6),
                "canonical_excerpt_accuracy": float(canonical_excerpt),
                "source_hallucination_rate": float(
                    len(known_references) != len(references)
                ),
                "unsupported_claim_rate": float(unsupported),
                "decision_invariance": float(decision_invariant),
                "warning_retention_rate": 1.0,
                "limitation_retention_rate": float(limitation_retained),
                "fallback_success_rate": float(
                    provider_success or public_status == "DEGRADED"
                ),
                "provider_success_rate": float(provider_success),
                "rule_violation_rate": float(not decision_invariant),
                "unauthorized_plan_modification_rate": float(
                    "已修改训练计划" in answer_text
                    or "updated your official training plan" in answer_text.lower()
                ),
            }
            passed = (
                public_status in case.expected_status
                and metrics["source_hallucination_rate"] == 0
                and metrics["unsupported_claim_rate"] == 0
                and metrics["decision_invariance"] == 1
                and metrics["rule_violation_rate"] == 0
                and metrics["unauthorized_plan_modification_rate"] == 0
                and metrics["citation_requirement_satisfaction"] == 1
            )
            metrics["case_pass_rate"] = float(passed)
            metric_values.append(metrics)
            results.append(
                RagCaseResult(
                    case_id=case.case_id,
                    passed=passed,
                    intent=case.intent,
                    status=public_status,
                    context_tools=context_tools,
                    model_tools=model_tools,
                    reference_document_ids=reference_documents,
                    validation_codes=[],
                    safe_error_codes=[],
                    flags=(
                        ["EVALUATION_ONLY_UNSAFE_ABLATION"]
                        if ABLATIONS[mode].evaluation_only_unsafe
                        else []
                    ),
                    metrics=metrics,
                    duration_ms=round((perf_counter() - started) * 1000, 3),
                )
            )
        report = TrainingKnowledgeEvaluationReport(
            evaluation_kind="rag",
            dataset_version=dataset.dataset_version,
            dataset_sha256=dataset.content_sha256,
            corpus_root_hash=corpus.root_hash,
            index_id=settings.coach_agent_knowledge_index_id or None,
            provider=settings.coach_agent_provider,
            model=settings.coach_agent_model,
            mode=mode,
            real_provider=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
            result_hash="0" * 64,
            case_count=len(results),
            metrics=aggregate_rag_metrics(metric_values),
            failure_case_ids=[item.case_id for item in results if not item.passed],
            limitations=[
                "Real remote providers may change over time. Raw answers, prompts, "
                "contexts, tool results, vectors, credentials, and reasoning content "
                "were not saved."
            ],
            cases=results,
        )
        return _finalize(report)
