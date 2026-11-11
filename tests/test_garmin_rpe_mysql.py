"""Real MySQL tests using existing strictly local synthetic fixtures."""
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from sqlalchemy import delete
from tests.test_mcp_facts_v3_mysql import engine, sample, DAY
from planner_core.database.models import WorkoutLogExternalActivity
from server.integrations.activity_provider.self_evaluation import normalize_rpe
from server.services.garmin_sync_service import _recalculate_log_from_linked_activities
from server.services.training_load_service import get_recent_training_read
from server.services.runner_state_service import RunnerStateService
from server.mcp.facts_v2 import read_training_detail
from server.agent.tools.workout_detail import GetWorkoutDetailTool, WorkoutDetailInput
from server.agent.schemas import AgentContext, AgentRequest
from server.agent.enums import AgentIntent


def test_rating_update_persists_through_training_state_mcp_and_coach(sample):
    db,users,log,acts=sample
    db.execute(delete(WorkoutLogExternalActivity).where(WorkoutLogExternalActivity.workout_log_id==log.id,
        WorkoutLogExternalActivity.external_activity_id != acts[1].id))
    activity=acts[1]
    activity.field_sources_json={'rpe_evidence':normalize_rpe({'summaryDTO':{'directWorkoutRpe':80}})}
    log.source_type='garmin_sync';log.rpe=None
    _recalculate_log_from_linked_activities(db,log);db.commit();db.expire_all()
    assert log.rpe==8 and log.field_sources_json['rpe']=='garmin'
    recent=get_recent_training_read(db,user_id=users[0].id,days=7,limit=20,as_of_date=DAY)
    assert recent.items[0].rpe==8 and recent.items[0].rpe_metadata['source']=='GARMIN'
    state=RunnerStateService(db).get_current(users[0],generated_at=datetime.combine(DAY,datetime.min.time(),tzinfo=timezone.utc))
    assert state.recent_training.completed_sessions_7d==recent.total_sessions
    assert state.recent_training.average_rpe_7d==8
    detail=read_training_detail(db,users[0].id,f'workout_log:{log.id}')
    assert detail.record.rpe==8 and detail.selected_activity.rpe==8 and len(detail.segments)==2
    assert detail.selected_activity.actual_training_type=='UNKNOWN'
    request=AgentRequest(user_id=users[0].id,intent=AgentIntent.PERSONAL_TRAINING_ANALYSIS,message='Synthetic detail')
    context=AgentContext(request_id=request.request_id,user_id=users[0].id,intent=request.intent,
        current_time=datetime.now(timezone.utc),timezone='Asia/Shanghai')
    tool=GetWorkoutDetailTool(SimpleNamespace(db=db))
    assert tool.execute(WorkoutDetailInput(record_ref=f'workout_log:{log.id}'),context).record.rpe==8
    from server.agent.tools.factory import build_coach_agent_tool_registry
    from server.agent.tools.dependencies import CoachAgentToolDependencies
    from server.agent.training_context_builder import AgentTrainingContextBuilder
    registry=build_coach_agent_tool_registry(CoachAgentToolDependencies.from_session(db))
    builder=AgentTrainingContextBuilder(registry=registry,clock=lambda:datetime.combine(DAY,datetime.min.time(),tzinfo=timezone.utc))
    request=request.model_copy(update={'message':f'分析workout_log:{log.id}的训练分段'})
    built=builder.build(request)
    assert built.workout_detail['record']['rpe']==8
    assert any(r.tool_name=='get_workout_detail' and r.status.value=='SUCCEEDED' for r in built.tool_results)
    context=context.model_copy(update={'user_id':users[1].id})
    with pytest.raises(Exception):tool.execute(WorkoutDetailInput(record_ref=f'workout_log:{log.id}'),context)
    # Garmin edits propagate; absent values do not erase; manual edits are protected.
    activity.field_sources_json={'rpe_evidence':normalize_rpe({'summaryDTO':{'directWorkoutRpe':50}})}
    _recalculate_log_from_linked_activities(db,log);db.commit();assert log.rpe==5
    _recalculate_log_from_linked_activities(db,log);db.commit();assert log.rpe==5
    log.rpe=6;log.field_sources_json={**log.field_sources_json,'rpe':'manual'}
    _recalculate_log_from_linked_activities(db,log);db.commit();assert log.rpe==6


def test_unknown_json_fields_and_health_free_text_never_leave_detail(sample):
    db,users,log,acts=sample
    acts[0].field_sources_json={'rpe_evidence':{'value':8,'source':'garmin','raw_field':'summaryDTO.directWorkoutRpe',
        'raw_value':80,'fetched_at':'PRIVATE_SENTINEL','token':'PRIVATE_SENTINEL','health_note':'PRIVATE_SENTINEL',
        'missing_reason':{'nested':'PRIVATE_SENTINEL'}}}
    result=read_training_detail(db,users[0].id,f'external_activity:{acts[0].id}')
    assert result.selected_activity.rpe==8
    assert 'PRIVATE_SENTINEL' not in result.model_dump_json()
