from pydantic import BaseModel
from datetime import datetime


class Location(BaseModel):
    x: float
    y: float


class EquipmentState(BaseModel):
    equipment_id: str
    name: str
    location: Location
    occupied: bool
    queue_count: int
    last_updated: datetime
