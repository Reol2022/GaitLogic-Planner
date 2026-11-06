"""Small console facade. Writes and their value-free audits share one transaction."""
from datetime import datetime
from decimal import Decimal
import hashlib
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from planner_core.database.models import AdminAISettings, AdminConfigRevision, AdminAuditEvent, UserAccount, ExternalSyncJob
from server.common.exceptions import BadRequestError, ConflictError, NotFoundError, ForbiddenError
from server.model_tasks import ModelTaskType, task_model_profile
from server.schemas.admin_console import PlanConfig, DraftRequest, AccountAccessUpdate

MAPPING = {'model_name':'deepseek_model', 'timeout_seconds':'deepseek_timeout_seconds'}


def read_config(row=None):
    settings = get_settings()
    defaults = dict(model_name=settings.deepseek_model, timeout_seconds=settings.deepseek_timeout_seconds,
        ai_plan_daily_limit=settings.ai_plan_daily_limit, ai_plan_cooldown_seconds=settings.ai_plan_cooldown_seconds,
        temperature=0.4, top_p=0.9, max_tokens_per_week=1600, max_tokens_cap=24000)
    return PlanConfig(**({name:getattr(row, MAPPING.get(name,name)) for name in defaults} if row else defaults))


def fingerprint(config, base_url, version=0):
    return hashlib.sha256(json.dumps({'config':config.model_dump(), 'base_url':base_url, 'version':version}, sort_keys=True).encode()).hexdigest()


def current(db, lock=False):
    stmt = select(AdminAISettings).where(AdminAISettings.id == 1)
    row = db.scalar((stmt.with_for_update() if lock else stmt).execution_options(populate_existing=True))
    config = read_config(row)
    base = row.deepseek_base_url if row else get_settings().deepseek_base_url
    return row, config, fingerprint(config, base, row.config_version if row else 0)


def audit(db, actor, action, target_type, target_id, fields):
    db.add(AdminAuditEvent(actor_user_id=actor, action=action, target_type=target_type, target_id=target_id, changed_fields=sorted(fields)))


def overview(db):
    return {'users_total':db.scalar(select(func.count()).select_from(UserAccount)),
        'users_active':db.scalar(select(func.count()).select_from(UserAccount).where(UserAccount.status=='active')),
        'sync_jobs':dict(db.execute(select(ExternalSyncJob.status,func.count()).group_by(ExternalSyncJob.status)).all()),
        'scope':'Aggregate counts only; no user training, chat or health details.'}


def users(db, keyword, page, page_size):
    condition = []
    if keyword and keyword.strip():
        # Treat SQL wildcards as literal search text.
        value = '%' + keyword.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        condition.append(or_(*(field.like(value, escape='\\') for field in (UserAccount.username,UserAccount.nickname,UserAccount.email))))
    return dict(items=list(db.scalars(select(UserAccount).where(*condition).order_by(UserAccount.id.desc()).offset((page-1)*page_size).limit(page_size))),
        total=db.scalar(select(func.count()).select_from(UserAccount).where(*condition)),page=page,page_size=page_size)


def update_access(db, uid, payload: AccountAccessUpdate, actor):
    singleton, _, _ = current(db,lock=True)
    if singleton is None: raise ConflictError('请先执行管理控制台迁移。')
    acting=db.scalar(select(UserAccount).where(UserAccount.id==actor).execution_options(populate_existing=True))
    if acting is None or acting.role!='admin' or acting.status!='active':
        raise ForbiddenError('管理员身份已变化，请重新登录。')
    row = db.scalar(select(UserAccount).where(UserAccount.id==uid).with_for_update())
    if row is None: raise NotFoundError('用户不存在。')
    if row.role != payload.expected_role or row.status != payload.expected_status:
        raise ConflictError('账号状态已变化，请刷新后重试。')
    if uid==actor and (payload.role!='admin' or payload.status!='active'):
        raise BadRequestError('不能停用当前管理员或移除自己的权限。')
    changes = [field for field in ('role','status') if getattr(row,field)!=getattr(payload,field)]
    if changes:
        row.role=payload.role; row.status=payload.status
        audit(db,actor,'USER_ACCESS_UPDATED','user',uid,changes)
        db.commit(); db.refresh(row)
    return row


def ai_state(db):
    row, config, version = current(db)
    settings = get_settings()
    profiles=[]
    for task in ModelTaskType:
        profile=task_model_profile(settings,task)
        profiles.append(dict(task=task.value,profile=profile.profile_name,model=config.model_name if task==ModelTaskType.AI_PLAN_GENERATION else profile.model,
            thinking_enabled=profile.thinking_enabled,timeout_seconds=config.timeout_seconds if task==ModelTaskType.AI_PLAN_GENERATION else profile.request_timeout_seconds,source='database' if task==ModelTaskType.AI_PLAN_GENERATION and row else 'environment',editable=False))
    return dict(config=config.model_dump(),fingerprint=version,config_version=row.config_version if row else 0,initialized=row is not None,
        has_api_key=bool((row and row.deepseek_api_key) or settings.ai_api_key),
        source='database' if row else 'environment_defaults',profiles=profiles,
        notice='此处只发布现有 AI 课表生成配置。Coach / 周复盘档位仍由服务器配置控制。Provider地址及密钥不在控制台编辑或返回。')


def create_draft(db, payload: DraftRequest, actor):
    _, _, version=current(db)
    if version!=payload.expected_fingerprint: raise ConflictError('生效配置已变化，请重新加载。')
    row=AdminConfigRevision(actor_user_id=actor,status='DRAFT',config_json=payload.config.model_dump(),base_fingerprint=version)
    db.add(row); db.flush()
    audit(db,actor,'AI_DRAFT_CREATED','ai_revision',row.id,list(PlanConfig.model_fields))
    db.commit(); db.refresh(row)
    return row


def publish(db, rid, expected, actor):
    # Serialize all publishers through the existing singleton. Require bootstrap
    # via the explicit migration, not a write hidden inside an admin GET.
    row, before, version=current(db,lock=True)
    if row is None: raise ConflictError('请先执行管理控制台迁移初始化配置。')
    revision=db.scalar(select(AdminConfigRevision).where(AdminConfigRevision.id==rid).with_for_update())
    if revision is None: raise NotFoundError('配置版本不存在。')
    if revision.status != 'DRAFT': raise ConflictError('只有未发布草稿可以发布；恢复旧版本请先创建恢复草稿。')
    if expected!=version or (revision.status=='DRAFT' and revision.base_fingerprint!=version):
        raise ConflictError('配置已变化；请重新加载并建立新草稿。')
    after=PlanConfig.model_validate(revision.config_json)
    # Save the pre-change state too: the first publication must be reversible.
    snapshot=AdminConfigRevision(actor_user_id=actor,status='SNAPSHOT',config_json=before.model_dump(),base_fingerprint=version,published_at=datetime.utcnow())
    db.add(snapshot)
    changes=[key for key in PlanConfig.model_fields if getattr(before,key)!=getattr(after,key)]
    for key,value in after.model_dump().items():
        setattr(row,MAPPING.get(key,key),Decimal(str(value)) if key in {'temperature','top_p'} else value)
    row.updated_by_id=actor
    row.config_version+=1
    revision.status='PUBLISHED'; revision.published_at=datetime.utcnow()
    audit(db,actor,'AI_CONFIG_PUBLISHED','ai_revision',rid,changes)
    db.commit()
    return ai_state(db)


def rollback_draft(db, rid, actor):
    original=db.get(AdminConfigRevision,rid)
    if original is None: raise NotFoundError('配置版本不存在。')
    _, _, version=current(db)
    # Rollback is always a new draft with explicit later publication.
    audit(db,actor,'AI_RECOVERY_REQUESTED','ai_revision',rid,[])
    return create_draft(db,DraftRequest(config=PlanConfig.model_validate(original.config_json),expected_fingerprint=version),actor)
