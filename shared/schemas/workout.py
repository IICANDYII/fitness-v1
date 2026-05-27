from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import List, Optional


class Exercise(BaseModel):
    name: str
    sets: int
    reps: int
    rest: int  # seconds


class Phase(BaseModel):
    phase: str
    exercises: List[Exercise]


class WorkoutPlan(BaseModel):
    plan_id: UUID
    user_id: UUID
    date: date
    goal: str
    phases: List[Phase]


class ExerciseExecution(BaseModel):
    execution_id: UUID
    user_id: UUID
    session_id: UUID
    exercise_name: str
    timestamp: datetime
    reps: int
    sets: int
    tempo: str
    rom: float
    quality_score: float


class WorkoutSession(BaseModel):
    session_id: UUID
    user_id: UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    total_volume: float
    calories: float
    completion_rate: float
