"""Synthetic console authorization and schema tests; no real accounts or keys."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from server.main import create_app
from server.api.deps import get_current_user, get_db
from server.schemas.admin_console import PlanConfig
from server.services.admin_console_service import read_config, fingerprint


@pytest.mark.parametrize('method,path',[
    ('GET','/api/admin/console/overview'),('GET','/api/admin/console/users'),
    ('GET','/api/admin/console/ai'),('GET','/api/admin/console/audit'),
    ('GET','/api/admin/console/ai/revisions'),('POST','/api/admin/console/ai/drafts'),
    ('POST','/api/admin/console/ai/revisions/1/publish'),('POST','/api/admin/console/ai/revisions/1/rollback-draft'),
    ('PATCH','/api/admin/console/users/1')])
def test_every_console_route_rejects_runner(method,path):
    app=create_app(); db=Mock()
    app.dependency_overrides[get_current_user]=lambda:SimpleNamespace(id=101,role='user',status='active')
    app.dependency_overrides[get_db]=lambda:db
    with TestClient(app) as client:
        response=client.request(method,path,json={})
    assert response.status_code==403
    db.execute.assert_not_called(); db.scalar.assert_not_called(); db.commit.assert_not_called()


def test_config_forbids_credentials_and_safety_switches():
    config=read_config().model_dump()
    for field in ('api_key','base_url','disable_validator','user_id'):
        with pytest.raises(ValidationError): PlanConfig(**config,**{field:'forbidden'})
    config['temperature']=0.333
    with pytest.raises(ValidationError): PlanConfig(**config)


def test_config_fingerprint_tracks_values_and_endpoint_not_secrets():
    config=read_config()
    a=fingerprint(config,'https://provider.invalid')
    assert len(a)==64
    assert a!=fingerprint(config.model_copy(update={'model_name':'synthetic-model'}),'https://provider.invalid')
    assert a!=fingerprint(config,'https://other.invalid')
