from __future__ import annotations

from server.agent.competition_ablation.schemas import AblationConfig, AblationVariant


VARIANT_CONFIGS: dict[AblationVariant, AblationConfig] = {
    AblationVariant.A_LLM_ONLY: AblationConfig(
        variant=AblationVariant.A_LLM_ONLY,
        tools_enabled=False,
        rules_enabled=False,
        rag_enabled=False,
        validator_enabled=False,
        decision_readiness_enabled=False,
        evidence_judge_enabled=False,
        reflect_enabled=False,
    ),
    AblationVariant.B_TOOLS_LLM: AblationConfig(
        variant=AblationVariant.B_TOOLS_LLM,
        tools_enabled=True,
        rules_enabled=False,
        rag_enabled=False,
        validator_enabled=False,
        decision_readiness_enabled=False,
        evidence_judge_enabled=False,
        reflect_enabled=False,
    ),
    AblationVariant.C_TRUSTED_CORE: AblationConfig(
        variant=AblationVariant.C_TRUSTED_CORE,
        tools_enabled=True,
        rules_enabled=True,
        rag_enabled=True,
        validator_enabled=True,
        decision_readiness_enabled=False,
        evidence_judge_enabled=False,
        reflect_enabled=False,
    ),
    AblationVariant.D_PARTIAL_FACTS: AblationConfig(
        variant=AblationVariant.D_PARTIAL_FACTS,
        tools_enabled=True,
        rules_enabled=True,
        rag_enabled=True,
        validator_enabled=True,
        decision_readiness_enabled=True,
        evidence_judge_enabled=False,
        reflect_enabled=False,
    ),
    AblationVariant.E_EVIDENCE_JUDGE: AblationConfig(
        variant=AblationVariant.E_EVIDENCE_JUDGE,
        tools_enabled=True,
        rules_enabled=True,
        rag_enabled=True,
        validator_enabled=True,
        decision_readiness_enabled=True,
        evidence_judge_enabled=True,
        reflect_enabled=False,
    ),
    AblationVariant.F_FULL_GAITLOGIC: AblationConfig(
        variant=AblationVariant.F_FULL_GAITLOGIC,
        tools_enabled=True,
        rules_enabled=True,
        rag_enabled=True,
        validator_enabled=True,
        decision_readiness_enabled=True,
        evidence_judge_enabled=True,
        reflect_enabled=True,
    ),
    AblationVariant.G_FULL_WITHOUT_VALIDATOR: AblationConfig(
        variant=AblationVariant.G_FULL_WITHOUT_VALIDATOR,
        tools_enabled=True,
        rules_enabled=True,
        rag_enabled=True,
        validator_enabled=False,
        decision_readiness_enabled=True,
        evidence_judge_enabled=True,
        reflect_enabled=True,
    ),
}


MAIN_VARIANTS = tuple(AblationVariant)[0:6]
SAFETY_VARIANTS = (
    AblationVariant.F_FULL_GAITLOGIC,
    AblationVariant.G_FULL_WITHOUT_VALIDATOR,
)


def variant_config(variant: AblationVariant) -> AblationConfig:
    return VARIANT_CONFIGS[variant].model_copy(deep=True)
