from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class IMUData(BaseModel):
    acc_x: float
    acc_y: float
    acc_z: float


class BiometricStream(BaseModel):
    id: Optional[int] = None
    user_id: UUID
    timestamp: datetime
    heart_rate: int
    hrv: float
    fatigue_score: float
    steps: int
    imu_data: IMUData
