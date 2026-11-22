from datetime import datetime, timedelta
import hashlib
import hmac
from ipaddress import ip_address, ip_network
import math
import secrets
import re

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.mysql import insert
from planner_core.config import get_settings
from planner_core.database.models import SecurityRateBucket, SecurityRequestLease
from server.common.exceptions import ServiceUnavailableError, TooManyRequestsError
from server.services.auth_service import signing_key

# Attempt budgets, not successful-draft quotas. Never retain request bodies.
POLICIES = {
    'ip': (300, 60), 'login_ip': (60, 60), 'login_account': (30, 900),
    'login_pair': (8, 300), 'register': (5, 3600), 'oauth': (60, 60),
    'coach_minute': (6, 60), 'coach_day': (100, 86400),
    'plan_hour': (6, 3600), 'plan_day': (12, 86400),
    'sync': (12, 3600), 'import': (10, 3600), 'mcp': (120, 60), 'knowledge': (30, 60),
}


def factory_for(request):
    factory = getattr(request.app.state, 'security_session_factory', None)
    if factory is None:
        from planner_core.database.session import SessionLocal
        factory = SessionLocal
    return factory


def opaque_key(policy, subject):
    return hmac.new(signing_key(), f'security-v1:{policy}:{subject}'.encode(), hashlib.sha256).hexdigest()


def client_ip(request):
    # Only ASGI client: proxy trust is configured on the server, never here.
    try:
        address = ip_address(request.client.host if request.client else '')
        return str(getattr(address, 'ipv4_mapped', None) or address)
    except ValueError:
        return 'unknown'


def ip_subject(request):
    value = client_ip(request)
    try:
        address = ip_address(value)
        return str(ip_network(f'{address}/64', strict=False)) if address.version == 6 else value
    except ValueError:
        return value


def admin_ip_allowed(request, networks):
    if not networks.strip():
        return True
    try:
        address = ip_address(client_ip(request))
        return any(address in ip_network(item.strip(), strict=False) for item in networks.split(',') if item.strip())
    except ValueError:
        return False


def _locked_bucket(db, key, now):
    statement = insert(SecurityRateBucket).values(key_hash=key, count=0, expires_at=now)
    db.execute(statement.on_duplicate_key_update(key_hash=statement.inserted.key_hash))
    return db.scalar(select(SecurityRateBucket).where(SecurityRateBucket.key_hash == key)
        .with_for_update().execution_options(populate_existing=True))


def consume(factory, entries, *, now=None, settings=None):
    settings = settings or get_settings()
    now = (now or datetime.utcnow()).replace(microsecond=0)
    try:
        with factory() as db:
            for policy, subject in sorted(set(entries)):
                default, seconds = POLICIES[policy]
                limit = settings.security_rate_limits.get(policy, default)
                bucket = _locked_bucket(db, opaque_key(policy, subject), now)
                if bucket.expires_at <= now:
                    bucket.count = 0
                    bucket.expires_at = now+timedelta(seconds=seconds)
                if bucket.count >= limit:
                    raise TooManyRequestsError('请求过于频繁，请稍后再试。', 'RATE_LIMITED',
                        retry_after=max(1, math.ceil((bucket.expires_at-now).total_seconds())))
                bucket.count += 1
            db.commit()
    except TooManyRequestsError:
        raise
    except Exception:
        # Never fall back to per-process counters after a database failure.
        raise ServiceUnavailableError('安全检查暂不可用，请稍后重试。', 'SECURITY_CHECK_UNAVAILABLE') from None


def acquire(factory, gates, *, now=None, settings=None):
    settings = settings or get_settings()
    now = (now or datetime.utcnow()).replace(microsecond=0)
    tokens = []
    try:
        with factory() as db:
            for subject, limit in sorted(gates):
                key = opaque_key('concurrency', subject)
                bucket = _locked_bucket(db, key, now)
                bucket.expires_at = now+timedelta(seconds=settings.security_lease_seconds)
                db.execute(delete(SecurityRequestLease).where(SecurityRequestLease.gate_hash == key,
                    SecurityRequestLease.expires_at <= now))
                count = db.scalar(select(func.count()).select_from(SecurityRequestLease).where(
                    SecurityRequestLease.gate_hash == key, SecurityRequestLease.expires_at > now))
                if count >= limit:
                    raise TooManyRequestsError('已有请求正在处理中，请稍后再试。', 'CONCURRENCY_LIMITED', retry_after=5)
                token = secrets.token_hex(24)
                db.add(SecurityRequestLease(token=token, gate_hash=key,
                    expires_at=now+timedelta(seconds=settings.security_lease_seconds)))
                tokens.append(token)
            db.commit()
        return tokens
    except TooManyRequestsError:
        raise
    except Exception:
        raise ServiceUnavailableError('安全检查暂不可用，请稍后重试。', 'SECURITY_CHECK_UNAVAILABLE') from None


def release(factory, tokens):
    if tokens:
        with factory() as db:
            db.execute(delete(SecurityRequestLease).where(SecurityRequestLease.token.in_(tokens)))
            db.commit()


def renew(factory, tokens):
    if tokens:
        with factory() as db:
            db.execute(update(SecurityRequestLease).where(SecurityRequestLease.token.in_(tokens),
                SecurityRequestLease.expires_at > datetime.utcnow()).values(
                    expires_at=datetime.utcnow()+timedelta(seconds=get_settings().security_lease_seconds)))
            db.commit()


def login_admission(request, account):
    if get_settings().security_controls_enabled:
        source = ip_subject(request)
        consume(factory_for(request), [('login_account', account), ('login_pair', f'{account}:{source}')])


def user_admission(request, user_id):
    if request is None or not get_settings().security_controls_enabled or request.method != 'POST':
        return
    path = request.url.path.rstrip('/')
    subject = f'user:{user_id}'
    entries, ai = [], False
    if path == '/api/coach/query' or (path.startswith('/api/coach/conversations/') and path.endswith('/messages')):
        entries, ai = [('coach_minute', subject), ('coach_day', subject)], True
    elif path == '/api/ai-plan/generate':
        entries, ai = [('plan_hour', subject), ('plan_day', subject)], True
    elif re.fullmatch(r'/api/weekly-reviews/(generate|graph|[0-9]+/proposal/revise)', path):
        entries, ai = [('coach_minute', subject), ('coach_day', subject)], True
    elif path.startswith(('/api/integrations/garmin/', '/api/data-sync/')):
        entries = [('sync', subject)]
    elif path.startswith(('/api/plan-imports', '/api/workout-imports', '/api/excel/import')):
        entries = [('import', subject)]
    if not entries:
        return
    state = request.scope.setdefault('state', {})
    if state.get('security_user_admitted'):
        return
    factory = factory_for(request)
    consume(factory, entries)
    if ai:
        limits = get_settings().security_rate_limits
        tokens = acquire(factory, [(f'ai:{subject}', limits.get('ai_concurrency', 1)),
            ('ai:global', limits.get('global_ai_concurrency', 10))])
        state.setdefault('security_leases', []).extend(tokens)
    state['security_user_admitted'] = True
