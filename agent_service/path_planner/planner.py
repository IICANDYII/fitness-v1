from typing import List, Dict


class PathPlanner:
    """A* / Dijkstra-based gym equipment route optimizer."""

    def plan(
        self,
        equipment_graph: Dict,
        current_location: str,
        target_exercises: List[str],
    ) -> Dict:
        """
        Input:  {equipment_graph, current_location, target_exercises}
        Output: {optimized_route: [...]}
        """
        pass

    def _build_graph(self, equipment_graph: Dict) -> Dict:
        pass

    def _astar(self, graph: Dict, start: str, targets: List[str]) -> List[str]:
        pass
