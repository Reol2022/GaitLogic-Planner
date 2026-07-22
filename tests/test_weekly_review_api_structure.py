from fastapi.testclient import TestClient

from server.main import app
from tests.openapi_assertions import get_openapi_routes


def test_weekly_review_routes_are_registered():
    routes = get_openapi_routes(app)
    assert "GET /api/weekly-reviews/summary" in routes
    assert "POST /api/weekly-reviews/generate" in routes
    assert "GET /api/weekly-reviews/{review_id}" in routes
    assert "PATCH /api/plan-adjustment-drafts/{draft_id}/items/{item_id}" in routes
    assert "POST /api/plan-adjustment-drafts/{draft_id}/apply" in routes


def test_weekly_review_endpoints_require_login():
    client = TestClient(app)
    assert client.get("/api/weekly-reviews/summary?cycle_id=1&block_id=1").status_code == 401
    assert client.post(
        "/api/weekly-reviews/generate",
        json={"cycle_id": 1, "source_block_id": 1, "target_block_id": 2},
    ).status_code == 401
    assert client.post(
        "/api/plan-adjustment-drafts/1/apply", json={"selected_item_ids": [1]}
    ).status_code == 401
