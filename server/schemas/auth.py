from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    nickname: str | None = Field(default=None, max_length=64)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("Invalid email.")
        return value


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    role: str
    status: str
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
