"""Loopback-only synthetic read workload. Never point this at production."""
import itertools
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from locust import HttpUser, between, task

USERS = json.loads(Path(os.environ['GAITLOGIC_AUDIT_USERS_FILE']).read_text(encoding='utf-8'))
COUNTER = itertools.count()


class SyntheticRunner(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self):
        assert urlparse(self.host).hostname == '127.0.0.1', 'loopback only'
        self.account = USERS[next(COUNTER) % len(USERS)]
        self.client.headers.update(Authorization='Bearer ' + self.account['web_token'])

    @task(3)
    def dashboard(self):
        self.client.get('/api/dashboard', name='dashboard', timeout=10)

    @task(2)
    def calendar(self):
        self.client.get('/api/training-calendar', params={'month': self.account['month']}, name='calendar', timeout=10)

    @task(2)
    def state(self):
        self.client.get('/api/runner-state/current', name='runner-state', timeout=10)

    @task(1)
    def plan_context(self):
        self.client.get('/api/ai-plan/context', name='plan-context', timeout=10)

    @task(4)
    def recent(self):
        self.rpc('get_recent_training', {'days': 28})

    @task(2)
    def detail(self):
        self.rpc('get_training_detail', {'record_ref': self.account['record_ref']})

    @task(1)
    def recovery(self):
        self.rpc('get_recovery_trend', {'days': 14})

    def rpc(self, name, arguments):
        with self.client.post('/mcp', name=name, headers={
            'Authorization': 'Bearer ' + self.account['mcp_token'],
            'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2026-07-28',
            'Mcp-Method': 'tools/call', 'Mcp-Name': name,
        }, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': name, 'arguments': arguments, '_meta': {
                'io.modelcontextprotocol/protocolVersion': '2026-07-28',
                'io.modelcontextprotocol/clientCapabilities': {},
                'io.modelcontextprotocol/clientInfo': {'name': 'synthetic-audit', 'version': '1'},
            }}}, catch_response=True, timeout=10) as response:
            if response.status_code == 200:
                body = response.json()
                result = body.get('result', {})
                structured = result.get('structuredContent', {})
                if 'error' in body or result.get('isError') or structured.get('status') == 'FAILED':
                    response.failure('safe business failure (body not retained)')
