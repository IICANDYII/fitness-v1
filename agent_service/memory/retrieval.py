from typing import List, Dict
from uuid import UUID


class MemoryRetriever:
    """Retrieve relevant memories via pgvector cosine similarity search."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def retrieve(self, user_id: UUID, query: str, top_k: int = 5) -> List[Dict]:
        """Flow: query → embedding → pgvector search → top-k memories."""
        pass
