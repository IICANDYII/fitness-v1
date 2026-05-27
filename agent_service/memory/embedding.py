from typing import List, Dict, Any
from uuid import UUID


class MemoryEmbedder:
    """Stores long-term user behavior memories via pgvector."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def store(self, user_id: UUID, content: str, metadata: Dict[str, Any]) -> int:
        """Embed content and persist to memory_embedding table. Returns row id."""
        pass

    def embed_text(self, text: str) -> List[float]:
        """Generate a 1536-dim embedding vector for text."""
        pass
