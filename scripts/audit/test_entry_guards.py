"""Anonymous API entry checks, explicitly restricted to a synthetic MySQL DB."""
import json
import os
import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def test_anonymous_protected_route_matrix():
    url = make_url(os.environ['GAITLOGIC_COACH_CHAT_TEST_DATABASE_URL'])
    assert url.host == '127.0.0.1' and url.port == 3307 and url.database.startswith('gaitlogic_test_')
    os.environ.update(MCP_HTTP_ENABLED='false', GARMIN_SMART_SYNC_ENABLED='false', AGENT_TRACING_ENABLED='false')
    from planner_core.config import get_settings
    get_settings.cache_clear()
    from server.main import create_app
    from server.api.deps import get_db
    app = create_app()
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    def isolated_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = isolated_db
    def guards(dep):
        names = set()
        for child in dep.dependencies:
            names.add(getattr(child.call, '__name__', ''))
            names.update(guards(child))
        return names
    contexts = []
    for route in app.routes:
        if hasattr(route, 'effective_route_contexts'):
            contexts.extend(route.effective_route_contexts())
        elif hasattr(route, 'dependant'):
            contexts.append(route)
    observations = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for route in contexts:
                names = guards(route.dependant)
                if not {'get_current_user', 'require_admin_user'} & names:
                    continue
                for method in sorted(route.methods):
                    path = re.sub(r'\{[^}]+\}', '1', route.path)
                    response = client.request(method, path)
                    observations.append(dict(method=method, path=route.path, status=response.status_code))
        Path('.audit-private/entry-guards.json').write_text(json.dumps(observations, indent=2), encoding='utf-8')
        failures = [r for r in observations if r['status'] != 401]
        assert not failures, [(r['method'], r['path'], r['status']) for r in failures]
        print(f'Anonymous entry checks: {len(observations)} rejected with 401')
    finally:
        engine.dispose()
