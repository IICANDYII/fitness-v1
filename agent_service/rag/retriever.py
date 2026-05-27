from typing import List, Dict


class RAGRetriever:
    """Retrieval-Augmented Generation over the fitness knowledge base."""

    def __init__(self, db_url: str):
        self.db_url = db_url

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict]:
        """Return top-k relevant exercise knowledge documents."""
        pass

    def build_context(self, query: str) -> str:
        """Build a context string from top-k retrieved documents for agent prompt."""
        docs = self.retrieve(query)
        return "\n".join(d.get("content", "") for d in docs)
