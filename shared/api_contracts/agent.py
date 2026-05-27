from pydantic import BaseModel
from uuid import UUID


class AgentDecideRequest(BaseModel):
    user_id: UUID
    state: dict
    biometric: dict
    environment: dict
    goal: str


class AgentDecideResponse(BaseModel):
    action_type: str
    recommendation: str
    reason: str
    confidence: float
