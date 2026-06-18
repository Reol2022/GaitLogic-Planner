from fastapi.testclient import TestClient

from server.main import app


def test_weekly_review_routes_are_registered():
    routes = {(route.path, ",".join(sorted(route.methods or []))) for route in app.routes}
    assert any(path == "/api/weekly-reviews/summary" and "GET" in methods for path, methods in routes)
    assert any(path == "/api/weekly-reviews/generate" and "POST" in methods for path, methods in routes)
    assert any(path == "/api/weekly-reviews/{review_id}" and "GET" in methods for path, methods in routes)
    assert any(path == "/api/plan-adjustment-drafts/{draft_id}/items/{item_id}" and "PATCH" in methods for path, methods in routes)
    assert any(path == "/api/plan-adjustment-drafts/{draft_id}/apply" and "POST" in methods for path, methods in routes)


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
