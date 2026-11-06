"""Explicit-target console migration with a Windows-user-encrypted preimage.

No credentials or existing configuration values are printed. The backup is
DPAPI-bound to the invoking Windows user and must stay outside the repository.
This tool only adds console schema; it never restores or drops production data.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session
from planner_core.config import get_settings
from planner_core.database.models import AdminAuditEvent, AdminConfigRevision
from scripts.upgrade_admin_console import upgrade
from server.services.admin_console_service import ai_state

TABLES = ('admin_ai_settings', 'admin_config_revisions', 'admin_audit_events')


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data: bytes, *, decrypt: bool = False) -> bytes:
    if sys.platform != 'win32':
        raise RuntimeError('DPAPI backup requires Windows')
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    api = ctypes.windll.crypt32
    call = api.CryptUnprotectData if decrypt else api.CryptProtectData
    call.restype = wintypes.BOOL
    ok = call(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result))
    if not ok:
        raise RuntimeError('DPAPI operation failed')
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(result.data, ctypes.c_void_p))


def snapshot(engine):
    result = {}
    names = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        for table in TABLES:
            if table not in names:
                result[table] = None
                continue
            count = connection.execute(text(f'SELECT COUNT(*) FROM `{table}`')).scalar_one()
            if count > 10000:
                raise RuntimeError('Affected table exceeds bounded backup size')
            ddl = connection.execute(text(f'SHOW CREATE TABLE `{table}`')).one()[1]
            rows = [dict(row) for row in connection.execute(text(f'SELECT * FROM `{table}` ORDER BY id')).mappings()]
            result[table] = {'ddl': ddl, 'rows': rows}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-host', required=True)
    parser.add_argument('--expected-port', required=True, type=int)
    parser.add_argument('--database', required=True)
    parser.add_argument('--backup-dir', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    settings = get_settings()
    if (settings.mysql_host, settings.mysql_port, settings.mysql_database) != (args.expected_host, args.expected_port, args.database):
        raise RuntimeError('Configured database does not match the explicit target')
    destination = args.backup_dir.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise RuntimeError('Backup must be outside the source repository')
    if not args.apply:
        raise RuntimeError('Explicit --apply is required')
    engine = create_engine(settings.database_url, connect_args={'connect_timeout': 8, 'read_timeout': 30, 'write_timeout': 30})

    @event.listens_for(engine, 'connect')
    def bound_ddl_wait(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION lock_wait_timeout=8')
            cursor.execute('SET SESSION innodb_lock_wait_timeout=8')

    try:
        before = snapshot(engine)
        if before['admin_ai_settings'] is None or not any(row['id'] == 1 for row in before['admin_ai_settings']['rows']):
            raise RuntimeError('Existing singleton is required; refusing to seed production defaults')
        payload = json.dumps({'format': 'gaitlogic-admin-preimage-v1', 'database': args.database,
            'created_at': datetime.now(timezone.utc).isoformat(), 'tables': before}, default=str, sort_keys=True).encode()
        encrypted = crypt(payload)
        destination.mkdir(parents=True, exist_ok=True)
        backup = destination / ('admin-before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.dpapi')
        with backup.open('xb') as handle:
            handle.write(encrypted)
        if crypt(backup.read_bytes(), decrypt=True) != payload:
            raise RuntimeError('Backup verification failed; migration not executed')
        print('BACKUP: encrypted and verified; ' + str(backup), flush=True)
        upgrade(engine)
        after = snapshot(engine)
        # Ignore only the newly added version column. Never replace values.
        before_rows = before['admin_ai_settings']['rows']
        after_rows = after['admin_ai_settings']['rows']
        if before_rows and 'config_version' not in before_rows[0]:
            after_rows = [{key: value for key, value in row.items() if key != 'config_version'} for row in after_rows]
        if before_rows != after_rows:
            raise RuntimeError('Settings changed during migration; manual review required, no automatic restoration')
        for table in TABLES[1:]:
            if after[table] is None:
                raise RuntimeError('Expected console table missing')
            if before[table] is not None and before[table]['rows'] != after[table]['rows']:
                raise RuntimeError('Existing console records changed; manual review required')
        with Session(engine) as db:
            ai_state(db)
            db.query(AdminAuditEvent).limit(1).all()
            db.query(AdminConfigRevision).limit(1).all()
        print('VERIFY: schema and ORM reads PASS; existing AI values unchanged; no training tables modified')
        print('BACKUP_SHA256: ' + hashlib.sha256(encrypted).hexdigest())
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Connection/SQL exceptions can contain parameters. Do not echo them.
        print('UPGRADE_STOPPED: ' + type(error).__name__ + '; inspect schema and the encrypted backup before retrying', file=sys.stderr)
        sys.exit(1)
