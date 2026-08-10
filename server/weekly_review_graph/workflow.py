from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from server.weekly_review_graph.nodes import WeeklyReviewNodes
from server.weekly_review_graph.ports import (
    WeeklyFactsLoader,
    WeeklyKnowledgeRetriever,
    WeeklyReviewGenerator,
)
from server.weekly_review_graph.schemas import WeeklyReviewGraphStatus, WeeklyReviewState


def _after_validation(state: WeeklyReviewState | dict) -> str:
    value = state if isinstance(state, WeeklyReviewState) else WeeklyReviewState.model_validate(state)
    return "fallback_weekly_review" if value.status == WeeklyReviewGraphStatus.FALLBACK else "finalize_weekly_review"


def build_weekly_review_graph(
    *,
    facts_loader: WeeklyFactsLoader,
    generator: WeeklyReviewGenerator,
    knowledge_retriever: WeeklyKnowledgeRetriever | None = None,
):
    nodes = WeeklyReviewNodes(
        facts_loader=facts_loader,
        generator=generator,
        knowledge_retriever=knowledge_retriever,
    )
    graph = StateGraph(WeeklyReviewState)
    graph.add_node("load_weekly_facts", nodes.load_weekly_facts)
    graph.add_node("evaluate_weekly_rules", nodes.evaluate_weekly_rules)
    graph.add_node("retrieve_training_knowledge", nodes.retrieve_training_knowledge)
    graph.add_node("generate_weekly_review", nodes.generate_weekly_review)
    graph.add_node("validate_weekly_review", nodes.validate_weekly_review)
    graph.add_node("fallback_weekly_review", nodes.fallback_weekly_review)
    graph.add_node("finalize_weekly_review", nodes.finalize_weekly_review)
    graph.add_edge(START, "load_weekly_facts")
    graph.add_edge("load_weekly_facts", "evaluate_weekly_rules")
    graph.add_edge("evaluate_weekly_rules", "retrieve_training_knowledge")
    graph.add_edge("retrieve_training_knowledge", "generate_weekly_review")
    graph.add_edge("generate_weekly_review", "validate_weekly_review")
    graph.add_conditional_edges(
        "validate_weekly_review",
        _after_validation,
        {
            "fallback_weekly_review": "fallback_weekly_review",
            "finalize_weekly_review": "finalize_weekly_review",
        },
    )
    graph.add_edge("fallback_weekly_review", "finalize_weekly_review")
    graph.add_edge("finalize_weekly_review", END)
    return graph.compile()
