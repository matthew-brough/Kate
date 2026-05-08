import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


def normalize_identity(value: str) -> str:
    return value.strip().lower()


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=12)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_identity(value)
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_identity(value)
        return value

    @model_validator(mode="after")
    def validate_password_policy(self) -> RegisterRequest:
        password = self.password
        checks = (
            any(char.islower() for char in password),
            any(char.isupper() for char in password),
            any(char.isdigit() for char in password),
            any(not char.isalnum() for char in password),
        )
        username = self.username.lower()
        email_local = str(self.email).split("@", 1)[0].lower()
        lower_password = password.lower()
        if (
            not all(checks)
            or username in lower_password
            or (email_local and email_local in lower_password)
        ):
            raise ValueError(
                "Password must include lowercase, uppercase, digit, symbol, "
                "and must not contain username or email local part"
            )
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
