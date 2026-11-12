from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from server.integrations.activity_provider.base import ProviderError
from server.integrations.activity_provider.garmin import _raise_safe_provider_error, GarminActivityProvider


@pytest.mark.parametrize('error,code', [(TimeoutError('synthetic'), 'NETWORK_TIMEOUT'),
    (ConnectionError('synthetic'), 'NETWORK_ERROR'), (RuntimeError('429'), 'RATE_LIMITED')])
def test_transient_session_failures_do_not_force_reauthentication(error, code):
    with pytest.raises(ProviderError) as captured:
        _raise_safe_provider_error(error, reauth=True)
    assert captured.value.code == code


def test_activity_network_error_is_classified_without_logging_raw_details(caplog):
    from datetime import datetime
    provider = GarminActivityProvider()
    provider._client = SimpleNamespace(garth=SimpleNamespace(timeout=None),
        get_activities=Mock(side_effect=TimeoutError('PRIVATE_SENTINEL')))
    with pytest.raises(ProviderError) as captured:
        provider.fetch_activities(datetime(2026, 1, 1), datetime(2026, 1, 2))
    assert captured.value.code == 'NETWORK_TIMEOUT'
    assert 'PRIVATE_SENTINEL' not in caplog.text
