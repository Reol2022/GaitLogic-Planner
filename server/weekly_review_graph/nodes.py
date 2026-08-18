from __future__ import annotations

from server.agent.schemas import AgentKnowledgeReference
from server.weekly_review_graph.ports import (
    WeeklyFactsLoader,
    WeeklyKnowledgeRetriever,
    WeeklyReviewGenerator,
)
from server.weekly_review_graph.schemas import (
    WeeklyReviewDraft,
    WeeklyReviewGraphStatus,
    WeeklyReviewResult,
    WeeklyReviewState,
)


def _state(value: WeeklyReviewState | dict) -> WeeklyReviewState:
    return value if isinstance(value, WeeklyReviewState) else WeeklyReviewState.model_validate(value)


class WeeklyReviewNodes:
    def __init__(
        self,
        *,
        facts_loader: WeeklyFactsLoader,
        generator: WeeklyReviewGenerator,
        knowledge_retriever: WeeklyKnowledgeRetriever | None = None,
    ) -> None:
        self.facts_loader = facts_loader
        self.generator = generator
        self.knowledge_retriever = knowledge_retriever

    def load_weekly_facts(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        facts = self.facts_loader(state.request)
        return {"weekly_facts": facts, "status": WeeklyReviewGraphStatus.FACTS_READY}

    def evaluate_weekly_rules(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if state.weekly_facts is None:
            return {
                "validation_errors": ["WEEKLY_FACTS_MISSING"],
                "status": WeeklyReviewGraphStatus.FALLBACK,
            }
        classification = state.weekly_facts.classification
        return {
            "rule_results": classification.rule_codes,
            "warnings": classification.warnings,
            "limitations": list(dict.fromkeys(classification.limitations)),
            "status": WeeklyReviewGraphStatus.RULES_READY,
        }

    def retrieve_training_knowledge(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if self.knowledge_retriever is None:
            return {
                "limitations": [*state.limitations, "KNOWLEDGE_RETRIEVAL_DISABLED"],
                "status": WeeklyReviewGraphStatus.KNOWLEDGE_READY,
            }
        query = "weekly running review " + " ".join(state.rule_results[:8])
        try:
            output = self.knowledge_retriever(query=query, user_id=state.user_id)
        except Exception:
            return {
                "limitations": [*state.limitations, "KNOWLEDGE_RETRIEVAL_UNAVAILABLE"],
                "status": WeeklyReviewGraphStatus.KNOWLEDGE_READY,
            }
        return {
            "knowledge_results": output.results,
            "limitations": [*state.limitations, *output.limitations],
            "status": WeeklyReviewGraphStatus.KNOWLEDGE_READY,
        }

    def generate_weekly_review(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        try:
            draft = self.generator(state)
        except Exception:
            return {
                "validation_errors": ["WEEKLY_REVIEW_GENERATION_FAILED"],
                "status": WeeklyReviewGraphStatus.FALLBACK,
            }
        return {"review_draft": draft, "status": WeeklyReviewGraphStatus.DRAFT_READY}

    def validate_weekly_review(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        draft = state.review_draft
        if draft is None or state.weekly_facts is None:
            return {
                "validation_errors": ["WEEKLY_REVIEW_DRAFT_MISSING"],
                "status": WeeklyReviewGraphStatus.FALLBACK,
            }
        available = {item.knowledge_reference_id for item in state.knowledge_results}
        errors: list[str] = []
        if len(draft.knowledge_reference_ids) != len(set(draft.knowledge_reference_ids)):
            errors.append("DUPLICATE_KNOWLEDGE_REFERENCE")
        if any(item not in available for item in draft.knowledge_reference_ids):
            errors.append("UNKNOWN_KNOWLEDGE_REFERENCE")
        text = "\n".join(
            [
                draft.overview,
                draft.completion_summary,
                draft.key_session_summary,
                draft.deviation_summary,
                draft.fatigue_and_risk,
                *draft.next_week_focus,
            ]
        ).lower()
        if any(term in text for term in ("已修改训练计划", "确诊", "绝对安全")):
            errors.append("UNSUPPORTED_OR_UNSAFE_CLAIM")
        return {
            "validated_review": None if errors else draft,
            "validation_errors": errors,
            "status": (
                WeeklyReviewGraphStatus.FALLBACK
                if errors
                else WeeklyReviewGraphStatus.VALIDATED
            ),
        }

    @staticmethod
    def fallback_weekly_review(raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        facts = state.weekly_facts
        if facts is None:
            draft = WeeklyReviewDraft(
                overview="本周事实不可用，无法生成周复盘。",
                completion_summary="暂无可验证的训练完成事实。",
                key_session_summary="暂无可验证的关键训练事实。",
                deviation_summary="暂无可验证的计划与实际偏差。",
                fatigue_and_risk="Runner State 数据不足。",
                next_week_focus=["补充训练记录后重新生成复盘。"],
            )
        else:
            draft = WeeklyReviewDraft(
                overview=(
                    f"本周确定性分类为 {facts.classification.primary_status.value}；"
                    f"数据准备度为 {facts.classification.overall_readiness or 'UNKNOWN'}。"
                ),
                completion_summary=(
                    f"计划 {facts.planned.planned_running_session_count} 次，"
                    f"完成 {facts.completed.completed_running_session_count} 次。"
                ),
                key_session_summary=(
                    f"关键课计划 {facts.planned.planned_key_session_count} 次，"
                    f"完成 {facts.completed.completed_key_session_count} 次。"
                ),
                deviation_summary=f"记录到 {len(facts.deviations)} 项确定性偏差。",
                fatigue_and_risk=(
                    f"疲劳状态 {facts.runner_state_trend.fatigue_level}；"
                    "不根据缺失恢复数据推断医学风险。"
                ),
                next_week_focus=[
                    "结合已记录偏差和数据限制进行人工复核。",
                    *(
                        ["部分决策域数据不完整，未对其生成确定性结论。"]
                        if facts.classification.overall_readiness == "PARTIAL"
                        else []
                    ),
                ],
            )
        return {
            "validated_review": draft,
            "limitations": [*state.limitations, "MODEL_EXPLANATION_UNAVAILABLE"],
            "status": WeeklyReviewGraphStatus.FALLBACK,
        }

    @staticmethod
    def finalize_weekly_review(raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if state.weekly_facts is None or state.validated_review is None:
            raise ValueError("Validated weekly facts and review are required")
        selected = set(state.validated_review.knowledge_reference_ids)
        references = [
            AgentKnowledgeReference(
                document_id=item.document_id,
                title=item.title,
                section=item.section,
                source_id=item.source_id,
                source_title=item.source_title,
                knowledge_version=item.knowledge_version,
                evidence_level=item.evidence_level.value,
                excerpt=item.excerpt,
                limitations=item.limitations,
            )
            for item in state.knowledge_results
            if item.knowledge_reference_id in selected
        ]
        draft = state.validated_review
        result = WeeklyReviewResult(
            weekly_facts=state.weekly_facts,
            rule_results=state.rule_results,
            overview=draft.overview,
            completion_summary=draft.completion_summary,
            key_session_summary=draft.key_session_summary,
            deviation_summary=draft.deviation_summary,
            fatigue_and_risk=draft.fatigue_and_risk,
            next_week_focus=draft.next_week_focus,
            warnings=state.warnings,
            limitations=state.limitations,
            knowledge_references=references,
            fallback_used=state.status == WeeklyReviewGraphStatus.FALLBACK,
        )
        return {"final_review": result, "status": WeeklyReviewGraphStatus.COMPLETED}
