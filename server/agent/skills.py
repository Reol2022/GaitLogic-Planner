from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Callable

from pydantic import BaseModel, Field

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext
from server.agent.skill import AgentSkill, SkillResult, SkillStatus
from server.agent.tools.weather import WeatherDataKind, WeatherToolInput

if TYPE_CHECKING:
    from server.agent.registry import AgentToolRegistry


class WeeklyReviewSkillInput(BaseModel):
    week_start: date | None = None
    week_end: date | None = None
    mode: str | None = Field(default=None, max_length=40)


class WeeklyReviewSkill(AgentSkill):
    name = "weekly_review"
    description = "Generate a bounded weekly training review through the existing protected Weekly Review workflow."
    input_model = WeeklyReviewSkillInput
    output_model = SkillResult
    allowed_intents = (AgentIntent.WEEKLY_REVIEW, AgentIntent.GENERAL_TRAINING_QUESTION)
    required_capabilities = ("get_runner_state", "get_recent_training", "get_current_training_cycle", "get_training_data_quality")

    def __init__(self, runner: Callable[[WeeklyReviewSkillInput, AgentContext], SkillResult]) -> None:
        self.runner = runner

    def execute(self, arguments: WeeklyReviewSkillInput, context: AgentContext) -> SkillResult:
        return self.runner(arguments, context)


class WeatherAwareTrainingInput(BaseModel):
    target_date: date
    location_label: str = Field(min_length=1, max_length=80)


class WeatherAwareTrainingSkill(AgentSkill):
    name = "weather_aware_training"
    description = "Assess weather-related training risk using weather facts and deterministic rules; it can only propose, never apply, a plan change."
    input_model = WeatherAwareTrainingInput
    output_model = SkillResult
    allowed_intents = (AgentIntent.TODAY_RECOMMENDATION, AgentIntent.GENERAL_TRAINING_QUESTION)
    required_capabilities = ("get_today_workout", "get_runner_state", "get_weather")
    optional_capabilities = ("retrieve_training_knowledge",)

    def __init__(self, registry: "AgentToolRegistry") -> None:
        self.registry = registry

    def execute(self, arguments: WeatherAwareTrainingInput, context: AgentContext) -> SkillResult:
        workout = self.registry.invoke("get_today_workout", {}, context)
        state = self.registry.invoke("get_runner_state", {}, context)
        weather = self.registry.invoke("get_weather", WeatherToolInput(
            location_label=arguments.location_label, target_date=arguments.target_date,
            data_kind=WeatherDataKind.FORECAST).model_dump(mode="json"), context)
        if weather.status.value != "SUCCEEDED" or not isinstance(weather.data, dict) or weather.data.get("status") != "available":
            return SkillResult(skill_name=self.name, status=SkillStatus.PARTIAL,
                summary="Weather evidence is unavailable; no environmental plan adjustment was proposed.",
                facts={"workout": workout.data, "runner_state": state.data},
                warnings=[{"code": "WEATHER_UNAVAILABLE", "message": "Weather evidence is unavailable."}])
        snapshot = weather.data
        risks: list[str] = []
        if (snapshot.get("temperature_c") or -99) >= 32 or (snapshot.get("humidity_percent") or 0) >= 85:
            risks.append("heat_or_humidity")
        if (snapshot.get("wind_gust_mps") or 0) >= 14:
            risks.append("strong_wind")
        if (snapshot.get("precipitation_probability") or 0) >= 80 or snapshot.get("lightning_risk") is True:
            risks.append("precipitation_or_lightning")
        return SkillResult(skill_name=self.name, status=SkillStatus.SUCCESS,
            summary="Environmental risk review completed." if not risks else "Environmental conditions warrant a protected adjustment proposal.",
            facts={"weather": snapshot, "workout": workout.data, "runner_state": state.data, "triggered_rules": risks},
            warnings=[{"code": "ENVIRONMENTAL_RISK", "message": item} for item in risks],
            proposal={"kind": "environmental_adjustment", "status": "draft_only"} if risks else None,
            requires_approval=bool(risks))
