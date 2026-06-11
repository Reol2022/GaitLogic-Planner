from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError

from server.api.routes import (
    ai_plan,
    ai_coach_preference,
    admin,
    auth,
    dashboard,
    excel,
    feedback,
    health,
    pace_calculator,
    pace_rules,
    planned_workouts,
    training_calendar,
    training_blocks,
    training_cycles,
    workout_logs,
)
from server.common.exceptions import (
    AppError,
    app_error_handler,
    integrity_error_handler,
    validation_error_handler,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gaitlogic Planner API",
        version="0.1.0",
        description="Backend API for training plans, logs, dashboard stats, and pace rules.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(ai_plan.router, prefix="/api")
    app.include_router(ai_coach_preference.router, prefix="/api")
    app.include_router(excel.router, prefix="/api")
    app.include_router(feedback.router, prefix="/api")
    app.include_router(training_calendar.router, prefix="/api")
    app.include_router(training_cycles.router, prefix="/api")
    app.include_router(training_blocks.router, prefix="/api")
    app.include_router(planned_workouts.router, prefix="/api")
    app.include_router(workout_logs.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(pace_calculator.router, prefix="/api")
    app.include_router(pace_rules.router, prefix="/api")
    return app


app = create_app()
