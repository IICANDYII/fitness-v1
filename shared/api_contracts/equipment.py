from pydantic import BaseModel
from typing import List


class EquipmentStatusResponse(BaseModel):
    equipment_id: str
    name: str
    occupied: bool
    queue_count: int


class GymStatusResponse(BaseModel):
    equipment: List[EquipmentStatusResponse]
