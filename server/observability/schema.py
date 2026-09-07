"""Stable, privacy-safe domain names for GaitLogic traces.

Business code may keep its existing ``component`` / ``operation`` pairs.  The
mapping here gives exporters and aggregators one stable vocabulary without
forcing a broad observability refactor through every domain module.
"""

from __future__ import annotations

from enum import StrEnum


class DomainSpanName(StrEnum):
    HTTP_REQUEST = "gaitlogic.http.request"
    COACH_REQUEST = "coach.request"
    RUNNER_STATE_LOAD = "runner_state.load"
    TOOL_CALL = "tool.call"
    EVIDENCE_JUDGE = "evidence.judge"
    EVIDENCE_REFLECT = "evidence.reflect"
    DECISION_OUTCOME = "decision.outcome"
    RULE_EVALUATE = "rule.evaluate"
    RAG_RETRIEVE = "rag.retrieve"
    RAG_METADATA_FILTER = "rag.metadata_filter"
    RAG_VECTOR_SEARCH = "rag.vector_search"
    RAG_RERANK = "rag.rerank"
    LLM_GENERATE = "llm.generate"
    VALIDATOR_CHECK = "validator.check"
    WEEKLY_REVIEW_REQUEST = "weekly_review.request"
    WEEKLY_REVIEW_EVALUATE = "weekly_review.evaluate"
    PROPOSAL_GENERATE = "proposal.generate"
    PROPOSAL_VALIDATE = "proposal.validate"
    APPROVAL_EVALUATE = "approval.evaluate"
    PLAN_APPLY = "plan.apply"
    MCP_CALL = "mcp.call"
    CAPABILITY_SELECT = "capability.select"
    CAPABILITY_PLAN = "capability.plan"
    CAPABILITY_EXECUTE = "capability.execute"
    SKILL_EXECUTE = "skill.execute"
    FACT_LOOKUP = "fact.lookup"
    FACT_INVALIDATE = "fact.invalidate"


_LEGACY_DOMAIN_NAMES: dict[tuple[str, str], DomainSpanName] = {
    ("http", "request"): DomainSpanName.HTTP_REQUEST,
    ("coach_api", "query"): DomainSpanName.COACH_REQUEST,
    ("agent", "request"): DomainSpanName.COACH_REQUEST,
    ("tool", "invoke"): DomainSpanName.TOOL_CALL,
    ("knowledge", "retrieve"): DomainSpanName.RAG_RETRIEVE,
    ("knowledge", "vector_search"): DomainSpanName.RAG_VECTOR_SEARCH,
    ("knowledge", "sparse_search"): DomainSpanName.RAG_METADATA_FILTER,
    ("knowledge", "hybrid_retrieval"): DomainSpanName.RAG_RETRIEVE,
    ("knowledge", "rerank"): DomainSpanName.RAG_RERANK,
    ("provider", "generate"): DomainSpanName.LLM_GENERATE,
    ("validator", "validate_output"): DomainSpanName.VALIDATOR_CHECK,
    ("validator", "check"): DomainSpanName.VALIDATOR_CHECK,
    ("evidence", "judge"): DomainSpanName.EVIDENCE_JUDGE,
    ("evidence", "rejudge"): DomainSpanName.EVIDENCE_REFLECT,
    ("reflect", "evaluate"): DomainSpanName.EVIDENCE_REFLECT,
    ("reflect", "tool"): DomainSpanName.EVIDENCE_REFLECT,
    ("reflect", "outcome"): DomainSpanName.EVIDENCE_REFLECT,
    ("decision", "outcome"): DomainSpanName.DECISION_OUTCOME,
    ("langgraph", "weekly_review"): DomainSpanName.WEEKLY_REVIEW_REQUEST,
    ("approval", "approve_proposal"): DomainSpanName.APPROVAL_EVALUATE,
    ("approval", "reject_proposal"): DomainSpanName.APPROVAL_EVALUATE,
    ("mcp", "tool"): DomainSpanName.MCP_CALL,
    ("capability", "select"): DomainSpanName.CAPABILITY_SELECT,
    ("capability", "plan"): DomainSpanName.CAPABILITY_PLAN,
    ("capability", "execute"): DomainSpanName.CAPABILITY_EXECUTE,
    ("skill", "execute"): DomainSpanName.SKILL_EXECUTE,
    ("fact", "hit"): DomainSpanName.FACT_LOOKUP,
    ("fact", "miss"): DomainSpanName.FACT_LOOKUP,
    ("fact", "invalidate"): DomainSpanName.FACT_INVALIDATE,
    ("rules", "evaluate"): DomainSpanName.RULE_EVALUATE,
    ("proposal", "materialize"): DomainSpanName.PROPOSAL_GENERATE,
    ("provider", "plan_design"): DomainSpanName.PROPOSAL_GENERATE,
}


def domain_span_name(component: str, operation: str) -> str:
    """Return a stable domain name, preserving unknown legacy names safely."""

    known = _LEGACY_DOMAIN_NAMES.get((component, operation))
    if known is not None:
        return known.value
    if component == "workflow" and operation == "rules.evaluate":
        return DomainSpanName.RULE_EVALUATE.value
    if component == "workflow" and operation == "weekly_facts":
        return "weekly_data.load"
    if component == "workflow" and operation == "proposal.materialize":
        return DomainSpanName.PROPOSAL_GENERATE.value
    if component == "workflow" and operation == "provider.plan_design":
        return DomainSpanName.PROPOSAL_GENERATE.value
    if component == "workflow" and operation == "validator":
        return DomainSpanName.VALIDATOR_CHECK.value
    return f"{component}.{operation}"
