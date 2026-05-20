from pydantic import BaseModel


class LoginPayload(BaseModel):
    email: str | None = None
    password: str | None = None


class LoginResponse(BaseModel):
    token: str


class LocalModel(BaseModel):
    name: str | None = None
    path: str | None = None
