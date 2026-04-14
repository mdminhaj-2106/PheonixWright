from pydantic import BaseModel, EmailStr
from typing import Literal, Optional

LicenseType = Literal["none", "microsoft365", "google-workspace", "adobe-cc"]

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    license: LicenseType = "none"

class UserUpdate(BaseModel):
    license: LicenseType
    password: Optional[str] = None
