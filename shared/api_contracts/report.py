from pydantic import BaseModel
from uuid import UUID
from datetime import date


class DailyReportRequest(BaseModel):
    user_id: UUID
    date: date


class DailyReportResponse(BaseModel):
    user_id: UUID
    date: date
    summary: str
    total_volume: float
    calories: float
    completion_rate: float
