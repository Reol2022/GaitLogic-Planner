# Environment and release isolation

The codebase uses centralized settings. Defaults are safe for development and production:

```dotenv
COMPETITION_MODE=false
ENABLE_EXPERIMENT_DASHBOARD=false
ENABLE_AGENT_TRACE=false
ENABLE_SURVEY_MODULE=false
ENABLE_COMPETITION_DEMO_DATA=false
```

The competition demo environment may set these values to `true` in its own untracked deployment configuration. It must use separate database credentials, storage, API credentials, allowed users, and deployment target. Never change the public production `.env` for a demonstration.

The current product main branch is `master`. The recommended flow is `feat/* -> develop -> release/* -> master`; creating `develop` is not mandatory now, and this policy does not rename or migrate `master`. A temporary local `competition/2026-ai-integration` branch may freeze an already-integrated demo; it is not a long-lived product fork. The competition integration flow is `develop -> competition/2026-ai-integration -> competition-2026-alpha/beta/final` tags after review. Product source remains solely in this repository.
