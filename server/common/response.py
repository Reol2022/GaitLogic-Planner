from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    app_version: str
    git_commit: str = Field(pattern=r"^(?:unknown|[0-9a-f]{7,40})$")
    environment: str
    build_time: str | None = None
