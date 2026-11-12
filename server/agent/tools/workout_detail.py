"""Coach access to the shared, ownership-checked MCP fact projection."""
from pydantic import Field
from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContractModel
from server.agent.tool import AgentTool
from server.mcp.facts_v2 import McpTrainingDetail, read_training_detail


class WorkoutDetailInput(AgentContractModel):
    record_ref: str = Field(pattern=r'^(workout_log|external_activity):[1-9][0-9]{0,17}$')
    activity_ref: str | None = Field(default=None, pattern=r'^external_activity:[1-9][0-9]{0,17}$')


class GetWorkoutDetailTool(AgentTool):
    name = "get_workout_detail"
    description = "Read a stable record_ref, scoped RPE and selected-activity laps. Legacy segments may be overlapping rollups; use normalized_segments and segment_validation for structure. Never infer repetitions or combine different activities. Ask for selection when needed. No upstream Garmin requests or writes."
    input_model = WorkoutDetailInput
    output_model = McpTrainingDetail
    allowed_intents = (AgentIntent.PERSONAL_TRAINING_ANALYSIS, AgentIntent.PERSONAL_TRAINING_STATUS,
        AgentIntent.WEEKLY_REVIEW, AgentIntent.TODAY_RECOMMENDATION, AgentIntent.PLAN_ADJUSTMENT_ANALYSIS)
    provided_fact_domains = ("recent_intensity", "training_volume")

    def __init__(self, dependencies):
        self.dependencies = dependencies

    def execute(self, arguments, context):
        result = read_training_detail(self.dependencies.db, context.user_id, arguments.record_ref, arguments.activity_ref)
        if len(result.segments) > 24:
            result = result.model_copy(update={"segments": result.segments[:24], "segments_complete": False,
                "limitations": [*result.limitations, "Coach context includes at most 24 stored laps; remaining laps are not included."]})
        if len(result.normalized_segments) > 24:
            result = result.model_copy(update={'normalized_segments':result.normalized_segments[:24],
                'segment_validation':{**result.segment_validation, 'structure_complete':False,
                    'confidence':'INCOMPLETE', 'context_truncated':True},
                'activity_classification':{'primary_type':'UNKNOWN','requires_confirmation':True}})
        return result
