from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from planner_core.config import get_settings
from server.api.routes import (
    ai_plan,
    ai_coach_preference,
    admin,
    auth,
    coach,
    data_sync,
    dashboard,
    excel,
    feedback,
    garmin_sync,
    health,
    pace_calculator,
    pace_rules,
    plan_imports,
    planned_workouts,
    onboarding,
    recovery_checkins,
    runner_state,
    rule_loop,
    system_settings,
    task_center,
    training_calendar,
    training_blocks,
    training_cycles,
    training_knowledge,
    training_plan,
    training_load,
    training_readiness,
    training_rule_governance,
    training_rules,
    usage_events,
    weekly_reviews,
    workout_imports,
    workout_logs,
)
from server.common.exceptions import (
    AppError,
    app_error_handler,
    database_error_handler,
    http_exception_handler,
    integrity_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Gaitlogic Planner API",
        version="0.15.0",
        description="Backend API for training plans, logs, dashboard stats, and pace rules.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.backend_cors_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(SQLAlchemyError, database_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(coach.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(ai_plan.router, prefix="/api")
    app.include_router(ai_coach_preference.router, prefix="/api")
    app.include_router(excel.router, prefix="/api")
    app.include_router(feedback.router, prefix="/api")
    app.include_router(data_sync.router, prefix="/api")
    app.include_router(garmin_sync.router, prefix="/api")
    app.include_router(onboarding.router, prefix="/api")
    app.include_router(system_settings.router, prefix="/api")
    app.include_router(task_center.router, prefix="/api")
    app.include_router(training_calendar.router, prefix="/api")
    app.include_router(training_knowledge.router, prefix="/api")
    app.include_router(training_rule_governance.router, prefix="/api")
    app.include_router(training_rules.router, prefix="/api")
    app.include_router(training_cycles.router, prefix="/api")
    app.include_router(training_plan.router, prefix="/api")
    app.include_router(training_blocks.router, prefix="/api")
    app.include_router(planned_workouts.router, prefix="/api")
    app.include_router(workout_logs.router, prefix="/api")
    app.include_router(recovery_checkins.router, prefix="/api")
    app.include_router(runner_state.router, prefix="/api")
    app.include_router(rule_loop.router, prefix="/api")
    app.include_router(training_load.router, prefix="/api")
    app.include_router(training_readiness.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(pace_calculator.router, prefix="/api")
    app.include_router(pace_rules.router, prefix="/api")
    app.include_router(plan_imports.router, prefix="/api")
    app.include_router(workout_imports.router, prefix="/api")
    app.include_router(usage_events.router, prefix="/api")
    app.include_router(weekly_reviews.router, prefix="/api")

    @app.get("/api/openapi.json", include_in_schema=False)
    def api_openapi() -> JSONResponse:
        return JSONResponse(app.openapi())

    @app.get("/api/docs", include_in_schema=False)
    def api_docs():
        return get_swagger_ui_html(
            openapi_url="/api/openapi.json",
            title="Gaitlogic Planner API - Docs",
        )

    # Mount last: the SDK sub-application handles only /mcp, while existing
    # REST routes retain their original order and behavior.
    if settings.mcp_http_enabled:
        from server.mcp.http import create_mcp_http_app

        app.mount("", create_mcp_http_app(), name="gaitlogic-mcp-http")

    return app


app = create_app()
