from __future__ import annotations

from server.agent.schemas import AgentKnowledgeReference
from server.weekly_review_graph.ports import (
    WeeklyFactsLoader,
    WeeklyKnowledgeRetriever,
    PlanDesigner,
    ProposalMaterializer,
    WeeklyReviewGenerator,
)
from server.weekly_review_graph.schemas import (
    WeeklyReviewDraft,
    WeeklyReviewAnalysis,
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
        plan_designer: PlanDesigner | None = None,
        proposal_materializer: ProposalMaterializer | None = None,
    ) -> None:
        self.facts_loader = facts_loader
        self.generator = generator
        self.knowledge_retriever = knowledge_retriever
        self.plan_designer = plan_designer
        self.proposal_materializer = proposal_materializer

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
            generated = self.generator(state)
        except Exception:
            return {
                "validation_errors": ["WEEKLY_REVIEW_GENERATION_FAILED"],
                "status": WeeklyReviewGraphStatus.FALLBACK,
            }
        if isinstance(generated, WeeklyReviewDraft):
            analysis = WeeklyReviewAnalysis(
                overall_assessment=generated.overview,
                execution_assessment=generated.completion_summary,
                load_assessment=generated.deviation_summary,
                key_session_assessment=generated.key_session_summary,
                recovery_assessment=generated.fatigue_and_risk,
                intensity_assessment=generated.fatigue_and_risk,
                next_week_constraints=generated.next_week_focus,
                recommended_direction=generated.next_week_focus,
                knowledge_reference_ids=generated.knowledge_reference_ids,
            )
        else:
            analysis = generated
        return {"weekly_analysis": analysis, "status": WeeklyReviewGraphStatus.ANALYSIS_READY}

    def validate_weekly_review(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        analysis = state.weekly_analysis
        if analysis is None or state.weekly_facts is None:
            return {
                "validation_errors": ["WEEKLY_REVIEW_DRAFT_MISSING"],
                "status": WeeklyReviewGraphStatus.FALLBACK,
            }
        available = {item.knowledge_reference_id for item in state.knowledge_results}
        errors: list[str] = []
        if len(analysis.knowledge_reference_ids) != len(set(analysis.knowledge_reference_ids)):
            errors.append("DUPLICATE_KNOWLEDGE_REFERENCE")
        if any(item not in available for item in analysis.knowledge_reference_ids):
            errors.append("UNKNOWN_KNOWLEDGE_REFERENCE")
        text = "\n".join(
            [
                analysis.overall_assessment,
                analysis.execution_assessment,
                analysis.load_assessment,
                analysis.key_session_assessment,
                analysis.recovery_assessment,
                analysis.intensity_assessment,
                *analysis.recommended_direction,
            ]
        ).lower()
        if any(term in text for term in ("已修改训练计划", "确诊", "绝对安全")):
            errors.append("UNSUPPORTED_OR_UNSAFE_CLAIM")
        return {
            "validated_review": None,
            "validation_errors": errors,
            "status": (
                WeeklyReviewGraphStatus.FALLBACK
                if errors
                else WeeklyReviewGraphStatus.VALIDATED
            ),
        }

    def generate_plan_design(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if self.plan_designer is None or not state.target_plans:
            return {
                "limitations": [*state.limitations, "PLAN_DESIGN_NOT_AVAILABLE"],
                "status": WeeklyReviewGraphStatus.VALIDATED,
            }
        try:
            design = self.plan_designer(state)
        except Exception:
            return {
                "limitations": [*state.limitations, "PLAN_DESIGN_GENERATION_FAILED"],
                "status": WeeklyReviewGraphStatus.VALIDATED,
            }
        return {"plan_design": design, "status": WeeklyReviewGraphStatus.PLAN_DESIGN_READY}

    def materialize_proposal(self, raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if self.proposal_materializer is None or state.plan_design is None:
            return {"status": state.status}
        try:
            proposal = self.proposal_materializer(state)
        except Exception:
            return {
                "limitations": [*state.limitations, "PROPOSAL_BLOCKED_BY_DETERMINISTIC_VALIDATOR"],
                "status": WeeklyReviewGraphStatus.VALIDATED,
            }
        return {"proposal": proposal, "status": WeeklyReviewGraphStatus.PROPOSAL_READY}

    @staticmethod
    def fallback_weekly_review(raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        facts = state.weekly_facts
        if facts is None:
            analysis = WeeklyReviewAnalysis(
                overall_assessment="本周事实不可用，无法生成周复盘。",
                execution_assessment="暂无可验证的训练完成事实。",
                load_assessment="暂无可验证的训练负荷事实。",
                key_session_assessment="暂无可验证的关键训练事实。",
                recovery_assessment="Runner State 数据不足。",
                intensity_assessment="暂无可验证的强度事实。",
                next_week_constraints=["补充训练记录后重新生成复盘。"],
                recommended_direction=["保持保守并人工复核。"],
            )
        else:
            analysis = WeeklyReviewAnalysis(
                overall_assessment=(
                    f"本周确定性分类为 {facts.classification.primary_status.value}；"
                    f"数据准备度为 {facts.classification.overall_readiness or 'UNKNOWN'}。"
                ),
                execution_assessment=(
                    f"计划 {facts.planned.planned_running_session_count} 次，"
                    f"完成 {facts.completed.completed_running_session_count} 次。"
                ),
                key_session_assessment=(
                    f"关键课计划 {facts.planned.planned_key_session_count} 次，"
                    f"完成 {facts.completed.completed_key_session_count} 次。"
                ),
                load_assessment=f"记录到 {len(facts.deviations)} 项确定性偏差。",
                recovery_assessment=(
                    f"疲劳状态 {facts.runner_state_trend.fatigue_level}；"
                    "不根据缺失恢复数据推断医学风险。"
                ),
                intensity_assessment="强度结论仅使用确定性分类与已记录训练。",
                next_week_constraints=[
                    "结合已记录偏差和数据限制进行人工复核。",
                    *(
                        ["部分决策域数据不完整，未对其生成确定性结论。"]
                        if facts.classification.overall_readiness == "PARTIAL"
                        else []
                    ),
                ],
                recommended_direction=["结合确定性规则进行人工复核。"],
            )
        return {
            "weekly_analysis": analysis,
            "limitations": [*state.limitations, "MODEL_EXPLANATION_UNAVAILABLE"],
            "status": WeeklyReviewGraphStatus.FALLBACK,
        }

    @staticmethod
    def finalize_weekly_review(raw: WeeklyReviewState | dict) -> dict:
        state = _state(raw)
        if state.weekly_facts is None or state.weekly_analysis is None:
            raise ValueError("Validated weekly facts and analysis are required")
        selected = set(state.weekly_analysis.knowledge_reference_ids)
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
        analysis = state.weekly_analysis
        result = WeeklyReviewResult(
            weekly_facts=state.weekly_facts,
            rule_results=state.rule_results,
            overview=analysis.overall_assessment,
            completion_summary=analysis.execution_assessment,
            key_session_summary=analysis.key_session_assessment,
            deviation_summary=analysis.load_assessment,
            fatigue_and_risk=analysis.recovery_assessment,
            next_week_focus=analysis.recommended_direction,
            warnings=list(dict.fromkeys([*state.warnings, *analysis.warnings])),
            limitations=list(dict.fromkeys([*state.limitations, *analysis.limitations])),
            knowledge_references=references,
            fallback_used=state.status == WeeklyReviewGraphStatus.FALLBACK,
        )
        return {"final_review": result, "status": WeeklyReviewGraphStatus.COMPLETED}
