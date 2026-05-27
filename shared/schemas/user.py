from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class UserProfile(BaseModel):
    user_id: UUID
    height: float
    weight: float
    age: int
    gender: str
    fitness_level: str
    goals: str
    created_at: datetime
