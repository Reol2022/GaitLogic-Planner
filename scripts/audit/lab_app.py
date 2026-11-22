"""Actual app, with outbound networking denied by the isolated benchmark host."""
import os
import socket
import faulthandler
import threading
import time

assert os.environ['MYSQL_HOST'] == '127.0.0.1'
assert os.environ['MYSQL_PORT'] == '3307'
assert os.environ['MYSQL_DATABASE'].startswith('gaitlogic_test_')
assert os.environ['GARMIN_SMART_SYNC_ENABLED'] == 'false'
connect = socket.socket.connect


def local_only(sock, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise RuntimeError('Audit outbound network prohibited')
    return connect(sock, address)


socket.socket.connect = local_only
from server.main import app  # noqa: E402,F401


def pool_watchdog():
    from planner_core.database.session import engine
    full_since = None
    while True:
        checked = engine.pool.checkedout()
        if checked >= 15:
            full_since = full_since or time.monotonic()
            if time.monotonic() - full_since > 5:
                print('AUDIT_POOL_SATURATION', engine.pool.status(), flush=True)
                faulthandler.dump_traceback()
                return
        else:
            full_since = None
        time.sleep(1)


threading.Thread(target=pool_watchdog, daemon=True).start()
