from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from planner_core.database.models import AdminAuditEvent, AdminConfigRevision, UserAccount
from server.api.deps import get_db, require_admin_user
from server.schemas.admin_console import AccountAccessUpdate, AuditRead, DraftRequest, PublishRequest, RevisionRead, UserPage
from server.schemas.admin_user import AdminUserRead
from server.services import admin_console_service as service

router=APIRouter(prefix='/admin/console',tags=['admin console'],dependencies=[Depends(require_admin_user)])


@router.get('/overview')
def overview(db: Session=Depends(get_db)):
    return service.overview(db)


@router.get('/users',response_model=UserPage)
def users(keyword: str|None=Query(None,max_length=100),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db)):
    return service.users(db,keyword,page,page_size)


@router.patch('/users/{user_id}',response_model=AdminUserRead)
def update_user(user_id:int,payload:AccountAccessUpdate,db:Session=Depends(get_db),actor:UserAccount=Depends(require_admin_user)):
    return service.update_access(db,user_id,payload,actor.id)


@router.get('/ai')
def ai(db:Session=Depends(get_db)):
    return service.ai_state(db)


@router.post('/ai/drafts',response_model=RevisionRead,status_code=201)
def draft(payload:DraftRequest,db:Session=Depends(get_db),actor:UserAccount=Depends(require_admin_user)):
    return service.create_draft(db,payload,actor.id)


@router.get('/ai/revisions',response_model=list[RevisionRead])
def revisions(limit:int=Query(30,ge=1,le=100),db:Session=Depends(get_db)):
    return list(db.scalars(select(AdminConfigRevision).order_by(AdminConfigRevision.id.desc()).limit(limit)))


@router.post('/ai/revisions/{revision_id}/publish')
def publish(revision_id:int,payload:PublishRequest,db:Session=Depends(get_db),actor:UserAccount=Depends(require_admin_user)):
    return service.publish(db,revision_id,payload.expected_fingerprint,actor.id)


@router.post('/ai/revisions/{revision_id}/rollback-draft',response_model=RevisionRead,status_code=201)
def rollback(revision_id:int,db:Session=Depends(get_db),actor:UserAccount=Depends(require_admin_user)):
    return service.rollback_draft(db,revision_id,actor.id)


@router.get('/audit')
def audit(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),db:Session=Depends(get_db)):
    return dict(items=[AuditRead.model_validate(row) for row in db.scalars(select(AdminAuditEvent).order_by(AdminAuditEvent.id.desc()).offset((page-1)*page_size).limit(page_size))],total=db.scalar(select(func.count()).select_from(AdminAuditEvent)))
