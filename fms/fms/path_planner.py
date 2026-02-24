"""
Dijkstra-based Path Planner for Navigation Graph
Uses navigation_graph.yaml to calculate waypoint paths
"""

import yaml
import heapq
import math
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Vertex:
    """Graph vertex (waypoint)"""
    name: str
    x: float
    y: float


class PathPlanner:
    """
    Dijkstra-based path planner using navigation graph

    Calculates optimal waypoint paths between any two locations.
    FMS uses this for high-level routing, then Nav2 handles
    pixel-level path planning between waypoints.
    """

    def __init__(self, graph_file: str = None):
        """
        Initialize path planner

        Args:
            graph_file: Path to navigation_graph.yaml
        """
        self.vertices: Dict[str, Vertex] = {}
        self.adjacency: Dict[str, List[str]] = {}  # vertex_name -> [connected vertices]
        self.edges: Dict[Tuple[str, str], float] = {}  # (v1, v2) -> distance

        if graph_file:
            self.load_graph(graph_file)

    def load_graph(self, graph_file: str):
        """
        Load navigation graph from YAML file

        Args:
            graph_file: Path to navigation_graph.yaml
        """
        try:
            with open(graph_file, 'r') as f:
                data = yaml.safe_load(f)

            # Load vertices
            for v in data.get('vertices', []):
                name = v['name']
                self.vertices[name] = Vertex(
                    name=name,
                    x=v['x'],
                    y=v['y']
                )
                self.adjacency[name] = []

            # Load lanes (edges)
            for lane in data.get('lanes', []):
                v1_name = lane[0]
                v2_name = lane[1]
                options = lane[2] if len(lane) > 2 else {}
                bidirectional = options.get('bidirectional', True)

                if v1_name not in self.vertices or v2_name not in self.vertices:
                    logger.warning(f"Lane references unknown vertex: {v1_name} or {v2_name}")
                    continue

                # Calculate distance
                v1 = self.vertices[v1_name]
                v2 = self.vertices[v2_name]
                distance = math.sqrt((v2.x - v1.x)**2 + (v2.y - v1.y)**2)

                # Add edge
                self._add_edge(v1_name, v2_name, distance)
                if bidirectional:
                    self._add_edge(v2_name, v1_name, distance)

            logger.info(f"Loaded navigation graph: {len(self.vertices)} vertices, {len(self.edges)} edges")

        except Exception as e:
            logger.error(f"Failed to load navigation graph: {e}")
            raise

    def _add_edge(self, v1: str, v2: str, distance: float):
        """Add directed edge to graph"""
        self.adjacency[v1].append(v2)
        self.edges[(v1, v2)] = distance

    def get_vertex_position(self, name: str) -> Optional[Tuple[float, float]]:
        """
        Get position of a vertex

        Args:
            name: Vertex name

        Returns:
            (x, y) tuple or None if not found
        """
        v = self.vertices.get(name)
        if v:
            return (v.x, v.y)
        return None

    def find_nearest_vertex(self, x: float, y: float) -> Optional[str]:
        """
        Find nearest vertex to given position

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Name of nearest vertex or None
        """
        min_dist = float('inf')
        nearest = None

        for name, v in self.vertices.items():
            dist = math.sqrt((v.x - x)**2 + (v.y - y)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = name

        return nearest

    def find_path(self, start: str, goal: str) -> Optional[List[str]]:
        """
        Find shortest path using Dijkstra algorithm

        Args:
            start: Start vertex name
            goal: Goal vertex name

        Returns:
            List of vertex names from start to goal, or None if no path
        """
        if start not in self.vertices:
            logger.error(f"Start vertex not found: {start}")
            return None
        if goal not in self.vertices:
            logger.error(f"Goal vertex not found: {goal}")
            return None

        if start == goal:
            return [start]

        # Dijkstra algorithm
        distances: Dict[str, float] = {v: float('inf') for v in self.vertices}
        distances[start] = 0
        previous: Dict[str, Optional[str]] = {v: None for v in self.vertices}

        # Priority queue: (distance, vertex_name)
        pq = [(0, start)]
        visited = set()

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == goal:
                break

            # Explore neighbors
            for neighbor in self.adjacency.get(current, []):
                if neighbor in visited:
                    continue

                edge_dist = self.edges.get((current, neighbor), float('inf'))
                new_dist = current_dist + edge_dist

                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        # Reconstruct path
        if distances[goal] == float('inf'):
            logger.warning(f"No path found from {start} to {goal}")
            return None

        path = []
        current = goal
        while current is not None:
            path.append(current)
            current = previous[current]

        path.reverse()

        logger.info(f"Path found: {' -> '.join(path)} (distance: {distances[goal]:.3f}m)")
        return path

    def get_path_positions(self, path: List[str]) -> List[Tuple[float, float]]:
        """
        Convert path (vertex names) to positions

        Args:
            path: List of vertex names

        Returns:
            List of (x, y) positions
        """
        positions = []
        for name in path:
            v = self.vertices.get(name)
            if v:
                positions.append((v.x, v.y))
        return positions

    def get_path_distance(self, path: List[str]) -> float:
        """
        Calculate total path distance

        Args:
            path: List of vertex names

        Returns:
            Total distance in meters
        """
        total = 0.0
        for i in range(len(path) - 1):
            edge_dist = self.edges.get((path[i], path[i+1]), 0)
            total += edge_dist
        return total
