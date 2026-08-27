# Legacy worktree file audit

This audit compares dirty legacy worktrees with the canonical workspace. No files or worktrees were copied, reset, removed, or overwritten.

## `rag-v0120`

| File | Decision | Reason |
|---|---|---|
| `.agents/skills/gaitlogic-tutor/SKILL.md` | NEEDS_MANUAL_REVIEW | Local agent skill, not product runtime; absent from canonical workspace. |
| `.agents/skills/gaitlogic-tutor/agents/openai.yaml` | NEEDS_MANUAL_REVIEW | Local agent configuration; ownership and publication intent are unclear. |
| `docs/learning/architecture/.gitkeep` | DUPLICATE | Empty directory marker has no release content. |
| `docs/learning/glossary.md` | NEEDS_MANUAL_REVIEW | Standalone learning draft absent from current versioned learning sets. |
| `docs/learning/interview-cards.md` | NEEDS_MANUAL_REVIEW | Personal interview material; not required by product release. |
| `docs/learning/interview-cram-sheet.md` | NEEDS_MANUAL_REVIEW | Personal interview material; not required by product release. |
| `docs/learning/lessons/01-gaitlogic-problem-and-training-loop.md` | NEEDS_MANUAL_REVIEW | Potential learning value, but version and review status are unknown. |
| `docs/learning/progress.md` | OUTDATED | Historical progress tracker conflicts with current versioned learning docs. |
| `docs/learning/project-map.md` | NEEDS_MANUAL_REVIEW | Potential documentation value; must be checked against current architecture. |
| `docs/learning/resume-evidence.md` | NEEDS_MANUAL_REVIEW | Personal career artifact, outside product release boundary. |
| `docs/learning/reviews/.gitkeep` | DUPLICATE | Empty directory marker has no release content. |

Action: `KEEP`. No directory-level migration is justified.

## `rag-v0160`

- All 41 Daniels knowledge documents and `docs/images/architecture1.png`: `ALREADY_MERGED` (byte-identical).
- `docs/knowledge/daniels-import-report.md`: `REPORT_ONLY`; absent from canonical workspace, not runtime input.
- `docs/knowledge/daniels-reconstruction-review.md`: `REPORT_ONLY`; absent from canonical workspace, not runtime input.
- `README.md`, corpus manifest/source YAML, knowledge loader and knowledge tests: `OUTDATED`; canonical workspace contains the expanded corpus plus later consolidation.
- Garmin provider, capability, enum, daily-state and sync files: `OUTDATED`; canonical versions add nullable health fields, activity-date semantics, partial-failure handling and later provider/reasoning changes.

Action: `NEEDS_MANUAL_REVIEW`. Only the two report-only files remain candidates for a deliberate documentation import.

## `recovery-v0161`

- `server/services/garmin_daily_state_sync_service.py`: `ALREADY_MERGED` (byte-identical).
- `server/services/recovery_checkin_service.py`: `ALREADY_MERGED` apart from line-ending representation.
- Provider interfaces, Garmin/mock adapters, capabilities and `garmin_sync_service.py`: `OUTDATED`; canonical workspace contains the same recovery design plus later partial-failure and date-semantics fixes.
- `planner_core/database/models.py` and `sql/schema.sql`: `OUTDATED`; canonical workspace additionally contains Provider Reasoning persistence schema.
- `planner_core/enums.py`: `OUTDATED`; canonical workspace contains later enum additions.

Action: `NEEDS_MANUAL_REVIEW` until the dirty worktree owner accepts the classification. No unique runtime capability was found.
