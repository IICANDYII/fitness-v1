from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional, List, Dict, Any


class MemoryEmbedding(BaseModel):
    id: Optional[int] = None
    user_id: UUID
    content: str
    embedding: Optional[List[float]] = None  # 1536-dim vector
    metadata: Dict[str, Any]
    created_at: datetime
