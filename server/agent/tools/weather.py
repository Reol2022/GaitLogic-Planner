from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field, field_validator

from server.agent.enums import AgentIntent
from server.agent.schemas import AgentContext
from server.agent.tool import AgentTool


class WeatherDataKind(str, Enum):
    CURRENT = "current"
    FORECAST = "forecast"
    HISTORICAL = "historical"


class WeatherToolInput(BaseModel):
    # Coarse area labels only. Coordinates, street addresses and postal codes
    # are intentionally rejected before a provider can see them.
    location_label: str = Field(min_length=1, max_length=80)
    target_date: date
    data_kind: WeatherDataKind = WeatherDataKind.FORECAST

    @field_validator("location_label")
    @classmethod
    def coarse_location_only(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if any(char.isdigit() for char in cleaned) or "," in cleaned or "." in cleaned:
            raise ValueError("location must be a coarse city or training-area label")
        return cleaned


class WeatherSnapshot(BaseModel):
    location_label: str
    target_date: date
    data_kind: WeatherDataKind
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: float | None = None
    precipitation_probability: float | None = None
    wind_speed_mps: float | None = None
    wind_gust_mps: float | None = None
    condition: str | None = None
    lightning_risk: bool | None = None
    provider: str
    observed_at: datetime | None = None
    forecast_generated_at: datetime | None = None
    status: str = "available"
    limitation: str | None = None


class WeatherProvider(Protocol):
    name: str
    def get_weather(self, *, location_label: str, target_date: date, data_kind: WeatherDataKind) -> WeatherSnapshot: ...


class UnavailableWeatherProvider:
    name = "disabled"
    def get_weather(self, *, location_label: str, target_date: date, data_kind: WeatherDataKind) -> WeatherSnapshot:
        return WeatherSnapshot(location_label=location_label, target_date=target_date, data_kind=data_kind,
            provider=self.name, status="unavailable", limitation="Weather provider is not configured.")


class GetWeatherTool(AgentTool):
    name = "get_weather"
    description = "Read coarse-area weather facts for a date. It never makes a training decision."
    input_model = WeatherToolInput
    output_model = WeatherSnapshot
    allowed_intents = (AgentIntent.TODAY_RECOMMENDATION, AgentIntent.GENERAL_TRAINING_QUESTION, AgentIntent.WEEKLY_REVIEW)
    provided_fact_domains = ("weather",)

    def __init__(self, provider: WeatherProvider | None = None) -> None:
        self.provider = provider or UnavailableWeatherProvider()

    def execute(self, arguments: WeatherToolInput, context: AgentContext) -> WeatherSnapshot:
        del context
        return self.provider.get_weather(location_label=arguments.location_label, target_date=arguments.target_date, data_kind=arguments.data_kind)
