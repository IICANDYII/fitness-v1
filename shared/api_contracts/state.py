from pydantic import BaseModel
from uuid import UUID


class StateUpdateRequest(BaseModel):
    user_id: UUID
    biometric: dict
    pose: dict
    equipment: dict


class StateUpdateResponse(BaseModel):
    success: bool
    state_key: str
