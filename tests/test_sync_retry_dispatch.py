from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import BackgroundTasks

from server.api.routes import data_sync, garmin_sync


@pytest.mark.parametrize(
    ('route', 'availability'),
    [(data_sync, 'assert_data_sync_available'), (garmin_sync, 'assert_garmin_sync_available')],
)
@pytest.mark.parametrize('status, expected_count', [('queued', 1), ('failed', 0)])
def test_retry_dispatches_only_queued_jobs(monkeypatch, route, availability, status, expected_count):
    job = SimpleNamespace(id=73, status=status)
    facade = SimpleNamespace(retry_sync_job=Mock(return_value=job))
    monkeypatch.setattr(route, availability, Mock())
    monkeypatch.setattr(route, '_facade', lambda db, user: facade)
    background = BackgroundTasks()

    result = route.retry_sync_job(12, background, db=object(), current_user=object())

    assert result is job
    facade.retry_sync_job.assert_called_once_with(12)
    assert len(background.tasks) == expected_count
    if expected_count:
        assert background.tasks[0].func is route.run_sync_job_in_background
        assert background.tasks[0].args == (73,)
