from abc import ABC, abstractmethod
from typing import Dict


class Skill(ABC):
    """Abstract base class for all agent skills."""

    @abstractmethod
    def run(self, input: Dict) -> Dict:
        pass
