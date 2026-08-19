from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: str | None = None
    city: str | None = None


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str | None
    city: str | None
    role: str

    class Config:
        from_attributes = True
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str