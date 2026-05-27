from pydantic import BaseModel
from typing import Optional, Dict


class EquipmentContext(BaseModel):
    occupied: bool
    queue: int


class UserState(BaseModel):
    current_exercise: Optional[str] = None
    phase: Optional[str] = None
    fatigue: float
    heart_rate: int
    equipment_context: Dict[str, EquipmentContext]
    location: str
