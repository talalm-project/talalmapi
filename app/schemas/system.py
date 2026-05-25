from typing import Literal

from pydantic import BaseModel


class LoginPayload(BaseModel):
    email: str | None = None
    password: str | None = None


class LoginResponse(BaseModel):
    token: str


class LocalModel(BaseModel):
    name: str | None = None
    type: Literal["inference", "embedding", "embeddings"] | None = None
    path: str | None = None
    context_window_min: int | None = None
    context_window_max: int | None = None
    context_window_recommended: int | None = None
