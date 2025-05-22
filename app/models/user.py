from uuid import UUID, uuid4
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

class User(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: EmailStr
    hashed_password: str
    full_name: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        # It's good practice to include an example for the documentation
        schema_extra = {
            "example": {
                "id": "00000000-0000-0000-0000-000000000000",
                "username": "johndoe",
                "email": "johndoe@example.com",
                "full_name": "John Doe",
                "is_active": True,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
            }
        }
