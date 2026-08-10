from server.main import app


def test_adaptive_plan_api_exposes_only_controlled_operations() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/adaptive-plan/proposals/{proposal_id}"]) == {"get"}
    assert set(paths["/api/adaptive-plan/proposals/{proposal_id}/approve"]) == {"post"}
    assert set(paths["/api/adaptive-plan/proposals/{proposal_id}/reject"]) == {"post"}
    assert set(paths["/api/adaptive-plan/versions"]) == {"get"}
    assert set(paths["/api/adaptive-plan/versions/{version_id}/rollback"]) == {"post"}


def test_adaptive_approval_contract_does_not_accept_user_id() -> None:
    operation = app.openapi()["paths"][
        "/api/adaptive-plan/proposals/{proposal_id}/approve"
    ]["post"]
    parameters = {item["name"] for item in operation.get("parameters", [])}
    assert parameters == {"proposal_id"}
    assert "requestBody" not in operation


def test_weekly_facts_and_graph_contracts_use_authenticated_identity() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/weekly-reviews/facts"]) == {"get"}
    assert set(paths["/api/weekly-reviews/graph"]) == {"post"}

    facts_parameters = {
        item["name"] for item in paths["/api/weekly-reviews/facts"]["get"]["parameters"]
    }
    assert "user_id" not in facts_parameters

    graph_schema = paths["/api/weekly-reviews/graph"]["post"]["requestBody"][
        "content"
    ]["application/json"]["schema"]
    assert graph_schema["$ref"].endswith("/WeeklyGraphRequest")
    request_properties = app.openapi()["components"]["schemas"]["WeeklyGraphRequest"][
        "properties"
    ]
    assert "user_id" not in request_properties
