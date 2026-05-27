from pydantic import BaseModel
from uuid import UUID
from datetime import date


class WorkoutPlanRequest(BaseModel):
    user_id: UUID
    date: date
    goal: str


class WorkoutSessionRequest(BaseModel):
    user_id: UUID
    session_id: UUID
