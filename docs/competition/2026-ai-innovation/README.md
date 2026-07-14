# 2026 AI Innovation Competition: public boundary

GaitLogic Planner remains the public product repository. This directory records only public architecture, product scope, governance, and isolation principles for the 2026 competition.

Competition submissions, raw questionnaires, interviews, unaggregated evaluation results, videos, defense materials, private prompts and parameters belong in the separate private workspace `../gaitlogic-competition-2026`. Neither repository may contain credentials, tokens, real `.env` files, production database backups, or unredacted personal data.

```powershell
python scripts/security/check_public_boundary.py
python scripts/security/check_public_boundary.py --all-tracked
python scripts/competition/check_separation.py
```

The checks only report findings; they never modify files.
