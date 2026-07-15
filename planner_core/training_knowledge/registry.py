from __future__ import annotations

from planner_core.training_knowledge.schemas import TrainingRuleDefinition


class TrainingRuleRegistry:
    def __init__(self, rules: list[TrainingRuleDefinition] | None = None) -> None:
        self._rules = rules or []

    def enabled_for_scope(self, context_type: str) -> list[TrainingRuleDefinition]:
        rules = [
            rule
            for rule in self._rules
            if rule.enabled and (rule.scope in {context_type, "generic", "all"})
        ]
        return sorted(rules, key=lambda rule: (-rule.priority, rule.code))

    def all(self) -> list[TrainingRuleDefinition]:
        return list(self._rules)

