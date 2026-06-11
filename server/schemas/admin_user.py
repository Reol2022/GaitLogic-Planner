from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminUserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    nickname: str | None = None
    role: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserUpdate(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    nickname: str | None = Field(default=None, max_length=64)
    role: str = Field(pattern=r"^(user|admin)$")
    status: str = Field(pattern=r"^(active|disabled)$")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email.")
        return value
