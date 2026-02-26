"""
Path Planner - Navigation Graph based path planning

Uses the navigation_graph.yaml to plan routes between waypoints.
"""
import yaml
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set
import heapq
import math

import logging
logger = logging.getLogger('fms.path_planner')


class NavigationGraph:
    """
    Navigation Graph for waypoint-based path planning

    Reads navigation_graph.yaml and provides:
    - Shortest path finding between waypoints
    - Route calculation for robot navigation
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize navigation graph from YAML config"""
        if config_path is None:
            # Try multiple possible config locations
            possible_paths = [
                # Source directory
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'navigation_graph.yaml'),
                # Workspace config directory
                '/home/gw/kitchmatics/roscamp-repo-1/fms/config/navigation_graph.yaml',
                # Install directory
                os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'config', 'navigation_graph.yaml'),
            ]

            config_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if config_path is None:
                raise FileNotFoundError(f"navigation_graph.yaml not found in: {possible_paths}")

        self.vertices: Dict[str, Tuple[float, float]] = {}
        self.adjacency: Dict[str, List[str]] = defaultdict(list)

        self._load_graph(config_path)
        logger.info(f"NavigationGraph loaded: {len(self.vertices)} vertices, "
                    f"{sum(len(v) for v in self.adjacency.values())//2} edges")

    def _load_graph(self, config_path: str):
        """Load navigation graph from YAML file"""
        try:
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            # Load vertices
            for vertex in data.get('vertices', []):
                name = vertex['name']
                x = vertex['x']
                y = vertex['y']
                self.vertices[name] = (x, y)

            # Load lanes (bidirectional edges)
            for lane in data.get('lanes', []):
                if len(lane) >= 2:
                    v1, v2 = lane[0], lane[1]
                    if v1 in self.vertices and v2 in self.vertices:
                        self.adjacency[v1].append(v2)
                        self.adjacency[v2].append(v1)

            logger.info(f"Loaded navigation graph from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load navigation graph: {e}")
            raise

    def _distance(self, v1: str, v2: str) -> float:
        """Calculate Euclidean distance between two vertices"""
        if v1 not in self.vertices or v2 not in self.vertices:
            return float('inf')

        x1, y1 = self.vertices[v1]
        x2, y2 = self.vertices[v2]
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def find_path(self, start: str, goal: str, blocked_nodes: Optional[Set[str]] = None) -> List[str]:
        """
        Find shortest path between two waypoints using Dijkstra's algorithm

        Args:
            start: Start waypoint name
            goal: Goal waypoint name
            blocked_nodes: Set of node names to exclude from path search (optional).
                           Start and goal nodes are never blocked even if in this set.

        Returns:
            List of waypoint names forming the path (including start and goal)
            Empty list if no path exists
        """
        if start not in self.vertices:
            logger.warning(f"Start waypoint {start} not in graph")
            return []
        if goal not in self.vertices:
            logger.warning(f"Goal waypoint {goal} not in graph")
            return []

        if start == goal:
            return [start]

        # Normalize blocked_nodes: exclude start and goal from blocking
        effective_blocked = set()
        if blocked_nodes:
            effective_blocked = blocked_nodes - {start, goal}

        # Dijkstra's algorithm
        distances = {v: float('inf') for v in self.vertices}
        distances[start] = 0
        previous = {v: None for v in self.vertices}

        # Priority queue: (distance, vertex)
        pq = [(0, start)]
        visited = set()

        while pq:
            dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == goal:
                break

            for neighbor in self.adjacency[current]:
                if neighbor in visited:
                    continue

                # Skip blocked nodes (but allow goal even if technically blocked)
                if neighbor in effective_blocked:
                    continue

                new_dist = dist + self._distance(current, neighbor)
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        # Reconstruct path
        if distances[goal] == float('inf'):
            if blocked_nodes:
                logger.warning(f"No path found from {start} to {goal} (avoiding {len(effective_blocked)} blocked nodes)")
            else:
                logger.warning(f"No path found from {start} to {goal}")
            return []

        path = []
        current = goal
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()

        if blocked_nodes:
            logger.info(f"Path found (avoiding blocked): {' -> '.join(path)} (distance: {distances[goal]:.3f}m)")
        else:
            logger.info(f"Path found: {' -> '.join(path)} (distance: {distances[goal]:.3f}m)")
        return path

    def find_path_avoiding_nodes(self, start: str, goal: str, blocked_nodes: Set[str]) -> List[str]:
        """
        Find path avoiding specified blocked nodes (Dijkstra variant)

        This is a convenience wrapper around find_path with blocked_nodes parameter.
        Start and goal nodes are never blocked even if in the blocked_nodes set.

        Args:
            start: Start waypoint name
            goal: Goal waypoint name
            blocked_nodes: Set of node names to exclude from path search

        Returns:
            List of waypoint names forming the path (including start and goal)
            Empty list if no path exists
        """
        return self.find_path(start, goal, blocked_nodes)

    def get_position(self, waypoint: str) -> Optional[Tuple[float, float]]:
        """Get (x, y) position of a waypoint"""
        return self.vertices.get(waypoint)

    def get_nearest_waypoint(self, x: float, y: float) -> Optional[str]:
        """Find the nearest waypoint to a given position"""
        min_dist = float('inf')
        nearest = None

        for name, (wx, wy) in self.vertices.items():
            dist = math.sqrt((x - wx)**2 + (y - wy)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = name

        return nearest


class PathPlanner:
    """
    Path Planner for robot navigation

    Provides:
    - Route planning from current position to destination
    - Sequential waypoint navigation management
    """

    def __init__(self, graph: Optional[NavigationGraph] = None):
        """Initialize path planner with navigation graph"""
        self.graph = graph or NavigationGraph()

        # Current navigation state per robot
        self.robot_routes: Dict[str, List[str]] = {}
        self.robot_current_index: Dict[str, int] = {}

    def plan_route(self, robot_id: str, current_position: str, destination: str) -> List[str]:
        """
        Plan a route from current position to destination

        Args:
            robot_id: Robot ID
            current_position: Current waypoint name or nearest waypoint
            destination: Destination waypoint name

        Returns:
            List of waypoints to visit (excluding current position)
        """
        path = self.graph.find_path(current_position, destination)

        if path and len(path) > 1:
            # Exclude current position from route
            route = path[1:]
            self.robot_routes[robot_id] = route
            self.robot_current_index[robot_id] = 0
            logger.info(f"Route planned for {robot_id}: {' -> '.join(route)}")
            return route

        return []

    def get_next_waypoint(self, robot_id: str) -> Optional[str]:
        """
        Get next waypoint for robot to navigate to

        Args:
            robot_id: Robot ID

        Returns:
            Next waypoint name, or None if route complete
        """
        if robot_id not in self.robot_routes:
            return None

        route = self.robot_routes[robot_id]
        index = self.robot_current_index.get(robot_id, 0)

        if index < len(route):
            return route[index]
        return None

    def advance_waypoint(self, robot_id: str) -> Optional[str]:
        """
        Mark current waypoint as reached and get next one

        Args:
            robot_id: Robot ID

        Returns:
            Next waypoint name, or None if route complete
        """
        if robot_id not in self.robot_routes:
            return None

        self.robot_current_index[robot_id] = self.robot_current_index.get(robot_id, 0) + 1
        return self.get_next_waypoint(robot_id)

    def is_route_complete(self, robot_id: str) -> bool:
        """Check if robot has completed its route"""
        if robot_id not in self.robot_routes:
            return True

        route = self.robot_routes[robot_id]
        index = self.robot_current_index.get(robot_id, 0)
        return index >= len(route)

    def clear_route(self, robot_id: str):
        """Clear robot's current route"""
        if robot_id in self.robot_routes:
            del self.robot_routes[robot_id]
        if robot_id in self.robot_current_index:
            del self.robot_current_index[robot_id]

    def get_route_progress(self, robot_id: str) -> Tuple[int, int]:
        """
        Get route progress for robot

        Returns:
            (current_index, total_waypoints)
        """
        if robot_id not in self.robot_routes:
            return (0, 0)

        route = self.robot_routes[robot_id]
        index = self.robot_current_index.get(robot_id, 0)
        return (index, len(route))

    def get_occupied_nodes(self) -> Set[str]:
        """
        Get all nodes currently occupied by robots

        Returns all nodes that robots are currently at or will visit next
        (i.e., the current waypoint being navigated to for each robot with an active route).

        Returns:
            Set of waypoint names currently occupied
        """
        occupied = set()

        for robot_id, route in self.robot_routes.items():
            index = self.robot_current_index.get(robot_id, 0)

            # Add current target waypoint (the one robot is heading to)
            if index < len(route):
                occupied.add(route[index])

        return occupied

    def get_nodes_on_path(self, robot_id: str) -> Set[str]:
        """
        Get all nodes on a specific robot's remaining path

        Args:
            robot_id: Robot ID

        Returns:
            Set of waypoint names on the robot's remaining route
        """
        if robot_id not in self.robot_routes:
            return set()

        route = self.robot_routes[robot_id]
        index = self.robot_current_index.get(robot_id, 0)

        # Return all remaining waypoints on the route
        return set(route[index:])

    def plan_route_with_avoidance(
        self,
        robot_id: str,
        start: str,
        goal: str,
        blocked_nodes: Set[str]
    ) -> Optional[List[str]]:
        """
        Plan a route avoiding specified blocked nodes (for collision avoidance)

        This method plans a route that avoids the specified blocked nodes.
        If no alternative path exists, returns None instead of an empty list
        to distinguish between "no path exists" and "route is already at destination".

        Args:
            robot_id: Robot ID
            start: Current waypoint name
            goal: Destination waypoint name
            blocked_nodes: Set of nodes to avoid (e.g., occupied by other robots)

        Returns:
            List of waypoints to visit (excluding current position),
            or None if no alternative route exists
        """
        path = self.graph.find_path(start, goal, blocked_nodes)

        if not path:
            logger.warning(
                f"No alternative route for {robot_id} from {start} to {goal} "
                f"(blocked: {blocked_nodes})"
            )
            return None

        if len(path) > 1:
            # Exclude current position from route
            route = path[1:]
            self.robot_routes[robot_id] = route
            self.robot_current_index[robot_id] = 0
            logger.info(
                f"Alternative route planned for {robot_id}: {' -> '.join(route)} "
                f"(avoiding {len(blocked_nodes)} nodes)"
            )
            return route

        # Path has only one node (start == goal case handled in find_path)
        return []

    def get_all_occupied_nodes_except(self, exclude_robot_id: str) -> Set[str]:
        """
        Get all nodes occupied by robots except the specified robot

        Useful for planning alternative routes for a specific robot
        while avoiding other robots' positions.

        Args:
            exclude_robot_id: Robot ID to exclude from occupied nodes

        Returns:
            Set of waypoint names occupied by other robots
        """
        occupied = set()

        for robot_id, route in self.robot_routes.items():
            if robot_id == exclude_robot_id:
                continue

            index = self.robot_current_index.get(robot_id, 0)

            # Add current target waypoint
            if index < len(route):
                occupied.add(route[index])

        return occupied

    def get_all_path_nodes_except(self, exclude_robot_id: str) -> Set[str]:
        """
        Get all nodes on all robots' remaining paths except the specified robot

        This is more conservative than get_all_occupied_nodes_except as it
        considers all future waypoints, not just the immediate next one.

        Args:
            exclude_robot_id: Robot ID to exclude from path nodes

        Returns:
            Set of waypoint names on other robots' remaining routes
        """
        path_nodes = set()

        for robot_id in self.robot_routes:
            if robot_id == exclude_robot_id:
                continue

            path_nodes.update(self.get_nodes_on_path(robot_id))

        return path_nodes
