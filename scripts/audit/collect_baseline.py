"""Read-only inventory; never outputs settings or credentials."""
import hashlib
import importlib.metadata as md
import json
import os
import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '.audit-private'


def main():
    OUT.mkdir(exist_ok=True)
    if not (OUT / '.gitignore').exists():
        (OUT / '.gitignore').write_text('*\n', encoding='utf-8')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()
    dirty = subprocess.check_output(['git', 'ls-files', '-m', '-o', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in dirty if p and (ROOT / p).is_file() and not p.startswith(('scripts/audit/', 'docs/audit/'))}
    snapshot = OUT / 'original-hashes.json'
    if not snapshot.exists():
        snapshot.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding='utf-8')
    versions = {n: md.version(n) for n in ('fastapi', 'starlette', 'SQLAlchemy', 'PyMySQL', 'mcp', 'openpyxl', 'garminconnect', 'garth', 'cryptography', 'httpx', 'uvicorn')}
    record = dict(head=git('rev-parse', 'HEAD'), master=git('rev-parse', 'master'), branch=git('branch', '--show-current'), platform=platform.platform(), python=platform.python_version(), cpu_count=os.cpu_count(), versions=versions, dirty_file_count=len(hashes))
    (OUT / 'baseline.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    os.environ.update(GARMIN_SMART_SYNC_ENABLED='false', AGENT_TRACING_ENABLED='false', MCP_HTTP_ENABLED='false')
    from server.main import app
    from fastapi.routing import APIRoute
    def dependencies(dep):
        result = set()
        for item in dep.dependencies:
            result.add(getattr(item.call, '__name__', str(item.call)))
            result.update(dependencies(item))
        return result
    rows = []
    routes = []
    for entry in app.routes:
        if hasattr(entry, 'effective_route_contexts'):
            routes.extend(entry.effective_route_contexts())
        elif isinstance(entry, APIRoute):
            routes.append(entry)
    for route in routes:
        if hasattr(route, 'dependant'):
            deps = dependencies(route.dependant)
            guard = 'ADMIN' if 'require_admin_user' in deps else ('USER' if 'get_current_user' in deps else 'PUBLIC_OR_HANDLER_AUTH')
            rows.append(dict(method='/'.join(sorted(route.methods)), path=route.path, guard=guard, handler=f'{route.endpoint.__module__}.{route.endpoint.__name__}'))
    (OUT / 'routes.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    target = ROOT / 'docs/audit/API_PERMISSION_MATRIX.md'
    target.write_text('# API 权限矩阵\n\n自动盘点入口依赖，不证明对象级/字段级授权。PUBLIC_OR_HANDLER_AUTH 包括处理函数内部校验的 OAuth 入口，不能直接解读为匿名访问。MCP 挂载和默认文档路由另见安全报告。\n\n| Method | Path | Guard | Handler |\n|---|---|---|---|\n' + '\n'.join(f"| {r['method']} | `{r['path']}` | {r['guard']} | `{r['handler']}` |" for r in rows) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))
    print('routes', len(rows), {g: sum(r['guard'] == g for r in rows) for g in {r['guard'] for r in rows}})


if __name__ == '__main__':
    main()
