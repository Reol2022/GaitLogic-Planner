from __future__ import annotations

import inspect

from server.services.weekly_facts_service import WeeklyFactsService


def test_weekly_facts_service_is_read_only_by_construction() -> None:
    source = inspect.getsource(WeeklyFactsService)
    assert ".commit(" not in source
    assert ".flush(" not in source
    assert ".add(" not in source
    assert ".delete(" not in source
    assert "weekly_review_ai_service" not in source
    assert "knowledge_retrieval" not in source
    assert "garmin" not in source.lower()
