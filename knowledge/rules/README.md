# Deterministic rule boundary

This directory documents the boundary between retrievable knowledge and product rules.

- Executable training rules remain in `planner_core/training_knowledge` and `config/training`.
- Files under `knowledge/documents` explain principles and limitations; they do not decide product state.
- Future retrieval must never override Runner State, Training Readiness, validators, or plan-write safeguards.
- Moving executable rules into retrieval documents requires a separately reviewed product change.
