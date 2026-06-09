from fastapi.testclient import TestClient

from server.main import app, create_app


def test_app_can_be_created() -> None:
    created = create_app()
    assert created.title == "Gaitlogic Planner API"


def test_health_route_works_without_database() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_required_routes_are_registered() -> None:
    routes = {
        f"{','.join(sorted(route.methods or []))} {route.path}"
        for route in app.routes
        if getattr(route, "path", "").startswith("/api")
    }
    assert "GET /api/health" in routes
    assert "POST /api/auth/register" in routes
    assert "POST /api/auth/login" in routes
    assert "GET /api/auth/me" in routes
    assert "POST /api/auth/logout" in routes
    assert "GET /api/training-cycles" in routes
    assert "POST /api/training-cycles" in routes
    assert "GET /api/training-cycles/{cycle_id}" in routes
    assert "PUT /api/training-cycles/{cycle_id}" in routes
    assert "DELETE /api/training-cycles/{cycle_id}" in routes
    assert "GET /api/training-blocks" in routes
    assert "POST /api/training-blocks" in routes
    assert "GET /api/training-blocks/{block_id}" in routes
    assert "PUT /api/training-blocks/{block_id}" in routes
    assert "DELETE /api/training-blocks/{block_id}" in routes
    assert "GET /api/planned-workouts" in routes
    assert "POST /api/planned-workouts" in routes
    assert "GET /api/planned-workouts/{workout_id}" in routes
    assert "PUT /api/planned-workouts/{workout_id}" in routes
    assert "DELETE /api/planned-workouts/{workout_id}" in routes
    assert "GET /api/today" in routes
    assert "GET /api/workout-logs/{planned_workout_id}" in routes
    assert "PUT /api/workout-logs/{planned_workout_id}" in routes
    assert "GET /api/dashboard" in routes
    assert "GET /api/stats/blocks/{block_id}" in routes
    assert "GET /api/pace-rules" in routes
    assert "POST /api/pace-rules" in routes
    assert "PUT /api/pace-rules/{rule_id}" in routes
    assert "DELETE /api/pace-rules/{rule_id}" in routes
    assert "GET /api/excel/template" in routes
    assert "POST /api/excel/import" in routes
    assert "POST /api/feedback" in routes
    assert "GET /api/feedback/my" in routes
    assert "POST /api/pace-calculator/calculate" in routes
    assert "POST /api/pace-profiles" in routes
    assert "GET /api/pace-profiles" in routes
    assert "GET /api/pace-profiles/{profile_id}" in routes
    assert "DELETE /api/pace-profiles/{profile_id}" in routes
    assert "POST /api/pace-profiles/{profile_id}/apply-to-pace-rules" in routes


def test_business_routes_require_login() -> None:
    client = TestClient(app)
    response = client.get("/api/training-cycles")
    assert response.status_code == 401
    feedback_response = client.post(
        "/api/feedback",
        json={"feedback_type": "bug", "content": "需要登录"},
    )
    assert feedback_response.status_code == 401
