"""
Collision Avoidance Controller - 다중 로봇 경로 충돌 회피 시스템

이 모듈은 다중 로봇 환경에서 경로 충돌을 감지하고 회피하는 기능을 제공합니다.

핵심 기능:
- 계획된 경로와 다른 로봇들의 현재 위치/경로 비교
- 점유된 노드, 예약된 노드, 경로 교차 감지
- Dijkstra 기반 대체 경로 탐색
- 대기 위치 결정 및 Pickup 대기열 관리
"""

import logging
import heapq
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# 도메인 레이어: 핵심 비즈니스 엔티티 및 값 객체
# =============================================================================

class ConflictType(Enum):
    """충돌 유형 정의"""
    NO_CONFLICT = "NO_CONFLICT"              # 충돌 없음
    NODE_OCCUPIED = "NODE_OCCUPIED"          # 노드가 다른 로봇에 의해 점유됨
    NODE_RESERVED = "NODE_RESERVED"          # 노드가 다른 로봇에 의해 예약됨
    PATH_CROSSING = "PATH_CROSSING"          # 경로 교차 발생
    PATH_BLOCKED = "PATH_BLOCKED"            # 경로가 완전히 차단됨
    PICKUP_SLOT_OCCUPIED = "PICKUP_SLOT_OCCUPIED"  # 픽업 슬롯 점유됨


class ReplanTrigger(Enum):
    """경로 재계획 트리거 유형"""
    NODE_OCCUPIED = "NODE_OCCUPIED"          # 노드 점유로 인한 재계획
    PATH_BLOCKED = "PATH_BLOCKED"            # 경로 차단으로 인한 재계획
    PICKUP_SLOT_AVAILABLE = "PICKUP_SLOT_AVAILABLE"  # 픽업 슬롯 사용 가능
    ROBOT_MOVED = "ROBOT_MOVED"              # 다른 로봇 이동으로 인한 재계획
    TIMEOUT = "TIMEOUT"                      # 대기 타임아웃


class WaitState(Enum):
    """로봇 대기 상태"""
    NOT_WAITING = "NOT_WAITING"              # 대기 중 아님
    WAITING_FOR_NODE = "WAITING_FOR_NODE"    # 노드 대기 중
    WAITING_FOR_PATH = "WAITING_FOR_PATH"    # 경로 대기 중
    WAITING_FOR_PICKUP = "WAITING_FOR_PICKUP"  # 픽업 슬롯 대기 중


@dataclass
class ConflictResult:
    """
    충돌 감지 결과를 담는 값 객체

    Attributes:
        has_conflict: 충돌 발생 여부
        conflict_type: 충돌 유형
        conflicting_robot_id: 충돌을 일으킨 로봇 ID
        conflicting_nodes: 충돌이 발생한 노드 목록
        blocked_segment_start: 차단된 구간 시작 인덱스
        blocked_segment_end: 차단된 구간 끝 인덱스
        message: 충돌 상세 설명
    """
    has_conflict: bool = False
    conflict_type: ConflictType = ConflictType.NO_CONFLICT
    conflicting_robot_id: Optional[str] = None
    conflicting_nodes: List[str] = field(default_factory=list)
    blocked_segment_start: int = -1
    blocked_segment_end: int = -1
    message: str = ""


@dataclass
class RobotWaitState:
    """
    로봇의 대기 상태 정보

    Attributes:
        robot_id: 로봇 ID
        state: 대기 상태
        waiting_at: 대기 중인 노드
        waiting_for: 대기 원인 (노드 또는 로봇 ID)
        waiting_since: 대기 시작 시간
        original_goal: 원래 목적지
        blocked_nodes: 차단된 노드 목록
    """
    robot_id: str
    state: WaitState = WaitState.NOT_WAITING
    waiting_at: Optional[str] = None
    waiting_for: Optional[str] = None
    waiting_since: Optional[datetime] = None
    original_goal: Optional[str] = None
    blocked_nodes: List[str] = field(default_factory=list)


@dataclass
class PathSegment:
    """
    경로 구간 정보

    Attributes:
        start_node: 시작 노드
        end_node: 끝 노드
        nodes: 구간에 포함된 모든 노드
        estimated_time: 예상 소요 시간 (초)
    """
    start_node: str
    end_node: str
    nodes: List[str] = field(default_factory=list)
    estimated_time: float = 0.0


# =============================================================================
# 애플리케이션 레이어: CollisionAvoidanceController
# =============================================================================

class CollisionAvoidanceController:
    """
    다중 로봇 경로 충돌 회피 컨트롤러

    Clean Architecture 원칙에 따라 설계되었습니다:
    - NavigationGraph, ZoneManager, FleetController에 의존
    - 충돌 감지, 대체 경로 탐색, 대기 위치 결정 기능 제공
    - Pickup 대기열 통합 관리

    사용 예시:
        controller = CollisionAvoidanceController(nav_graph, zone_manager, fleet_controller)
        path, success = controller.plan_path_with_avoidance("pinky1", "pinky1_spot", "table1")
    """

    # 상수 정의
    PICKUP_WAITING_NODE = "pickup_spot"       # 픽업 대기 위치
    # 보조 대기 위치 - 좌측 열(point2,3), 중간 열(point5-8), 우측 열(point9-12)
    SECONDARY_WAITING_NODES = ["point2", "point3", "point5", "point6", "point7", "point8"]
    DEFAULT_WAIT_TIMEOUT = 30.0               # 기본 대기 타임아웃 (초)
    ROBOT_SPEED_MPS = 0.3                     # 로봇 평균 속도 (m/s)
    NODE_OCCUPATION_RADIUS = 0.15             # 노드 점유 반경 (m)

    def __init__(self, navigation_graph, zone_manager, fleet_controller,
                 pickup_slot_manager=None):
        """
        CollisionAvoidanceController 초기화

        Args:
            navigation_graph: NavigationGraph 인스턴스 (경로 탐색용)
            zone_manager: ZoneManager 인스턴스 (존 예약 시스템)
            fleet_controller: FleetController 인스턴스 (로봇 상태 관리)
            pickup_slot_manager: PickupSlotManager 인스턴스 (선택적, 픽업 대기열 관리)
        """
        self.navigation_graph = navigation_graph
        self.zone_manager = zone_manager
        self.fleet_controller = fleet_controller
        self.pickup_slot_manager = pickup_slot_manager

        # 로봇별 경로 추적: {robot_id: [waypoint_list]}
        self.robot_paths: Dict[str, List[str]] = {}

        # 로봇별 현재 경로 인덱스: {robot_id: current_index}
        self.robot_path_indices: Dict[str, int] = {}

        # 로봇별 대기 상태: {robot_id: RobotWaitState}
        self.robot_wait_states: Dict[str, RobotWaitState] = {}

        # 노드별 예약 정보: {node_name: robot_id}
        self.reserved_nodes: Dict[str, str] = {}

        # 픽업 대기열: [robot_id, ...]
        self.pickup_queue: List[str] = []

        # 로봇별 파킹 스팟 매핑
        self.parking_spots = {
            'pinky1': 'pinky1_spot',
            'pinky2': 'pinky2_spot',
            'pinky3': 'pinky3_spot'
        }

        logger.info("CollisionAvoidanceController 초기화 완료")

    # =========================================================================
    # 공개 API: 경로 계획 및 충돌 회피
    # =========================================================================

    def plan_path_with_avoidance(self, robot_id: str, start: str,
                                  goal: str) -> Tuple[List[str], bool]:
        """
        충돌 회피를 고려한 경로 계획

        다른 로봇들의 현재 위치와 경로를 고려하여 안전한 경로를 계획합니다.
        충돌이 감지되면 대체 경로를 탐색하거나 대기 위치를 결정합니다.

        Args:
            robot_id: 경로를 계획할 로봇 ID
            start: 시작 노드
            goal: 목표 노드

        Returns:
            Tuple[List[str], bool]: (경로 노드 리스트, 성공 여부)
            - 성공 시: (경로 리스트, True)
            - 대기 필요 시: (대기 위치만 포함된 리스트, False)
            - 실패 시: (빈 리스트, False)
        """
        logger.info(f"[{robot_id}] 충돌 회피 경로 계획: {start} -> {goal}")

        # 1단계: 기본 경로 계획
        base_path = self.navigation_graph.find_path(start, goal)
        if not base_path:
            logger.warning(f"[{robot_id}] 기본 경로를 찾을 수 없음: {start} -> {goal}")
            return [], False

        # 2단계: 충돌 감지
        conflict = self.detect_collision(robot_id, base_path)

        # 충돌 없음 -> 기본 경로 반환
        if not conflict.has_conflict:
            logger.info(f"[{robot_id}] 충돌 없음, 기본 경로 사용: {' -> '.join(base_path)}")
            self.update_robot_path(robot_id, base_path)
            return base_path, True

        logger.info(f"[{robot_id}] 충돌 감지: {conflict.conflict_type.value} - {conflict.message}")

        # 3단계: 대체 경로 탐색 (단, 기본 경로의 1.5배 이하인 경우만)
        blocked_nodes = set(conflict.conflicting_nodes)
        alternative_path = self.find_alternative_path(robot_id, start, goal, blocked_nodes)
        base_path_length = len(base_path)

        if alternative_path:
            # 대체 경로가 기본 경로의 1.5배 이상이면 대기 선택
            if len(alternative_path) > base_path_length * 1.5:
                logger.info(f"[{robot_id}] 대체 경로가 너무 김 ({len(alternative_path)} vs {base_path_length}), 대기 선택")
                alternative_path = None
            else:
                # 대체 경로에서 다시 충돌 검사
                alt_conflict = self.detect_collision(robot_id, alternative_path)
                if not alt_conflict.has_conflict:
                    logger.info(f"[{robot_id}] 대체 경로 사용: {' -> '.join(alternative_path)}")
                    self.update_robot_path(robot_id, alternative_path)
                    return alternative_path, True
                else:
                    alternative_path = None

        # 4단계: 대기 위치 결정
        waiting_position = self.determine_waiting_position(robot_id, conflict)
        logger.info(f"[{robot_id}] 대기 위치 결정: {waiting_position}")

        # 대기 상태 설정
        self._set_wait_state(
            robot_id,
            WaitState.WAITING_FOR_NODE,
            waiting_position,
            conflict.conflicting_robot_id,
            goal,
            list(blocked_nodes)
        )

        # 대기 위치까지의 경로 반환
        if waiting_position != start:
            wait_path = self.navigation_graph.find_path(start, waiting_position)
            if wait_path:
                self.update_robot_path(robot_id, wait_path)
                return wait_path, False

        return [start], False

    def detect_collision(self, robot_id: str, planned_path: List[str]) -> ConflictResult:
        """
        계획된 경로의 충돌 감지

        다음 항목들을 검사합니다:
        1. 다른 로봇의 현재 위치와의 충돌
        2. 예약된 노드와의 충돌
        3. 다른 로봇의 계획된 경로와의 교차

        Args:
            robot_id: 검사할 로봇 ID
            planned_path: 계획된 경로 (노드 리스트)

        Returns:
            ConflictResult: 충돌 감지 결과
        """
        if not planned_path:
            return ConflictResult(has_conflict=False)

        conflicting_nodes = []
        conflicting_robot = None
        conflict_type = ConflictType.NO_CONFLICT
        blocked_start = -1
        blocked_end = -1

        # 1. 다른 로봇들의 현재 위치 확인
        occupied_nodes = self._get_occupied_nodes(exclude_robot=robot_id)

        for idx, node in enumerate(planned_path):
            if node in occupied_nodes:
                if conflict_type == ConflictType.NO_CONFLICT:
                    conflict_type = ConflictType.NODE_OCCUPIED
                    blocked_start = idx
                    conflicting_robot = occupied_nodes[node]
                conflicting_nodes.append(node)
                blocked_end = idx

        # 2. 예약된 노드 확인 (예약한 로봇이 이미 지나간 노드는 제외)
        for idx, node in enumerate(planned_path):
            if node in self.reserved_nodes and self.reserved_nodes[node] != robot_id:
                reserving_robot_id = self.reserved_nodes[node]

                # 예약한 로봇의 현재 위치 확인
                reserving_robot = self.fleet_controller.get_robot(reserving_robot_id)
                if reserving_robot and reserving_robot.current_pose:
                    # 예약한 로봇이 현재 위치한 노드 찾기
                    rx = reserving_robot.current_pose.position.x
                    ry = reserving_robot.current_pose.position.y
                    reserving_current_node = self.navigation_graph.get_nearest_waypoint(rx, ry)

                    # 예약한 로봇의 경로에서 현재 노드와 예약된 노드의 위치 비교
                    reserving_path = self.robot_paths.get(reserving_robot_id, [])
                    if reserving_path and reserving_current_node:
                        try:
                            current_idx_in_path = reserving_path.index(reserving_current_node)
                            reserved_node_idx = reserving_path.index(node) if node in reserving_path else -1

                            # 예약한 로봇이 이미 해당 노드를 지났으면 (현재 인덱스가 더 크면) 충돌 아님
                            if reserved_node_idx != -1 and current_idx_in_path > reserved_node_idx:
                                # 로봇이 이미 지나간 노드 - 예약 해제
                                del self.reserved_nodes[node]
                                continue
                        except ValueError:
                            pass

                if conflict_type == ConflictType.NO_CONFLICT:
                    conflict_type = ConflictType.NODE_RESERVED
                    blocked_start = idx
                    conflicting_robot = reserving_robot_id
                if node not in conflicting_nodes:
                    conflicting_nodes.append(node)
                blocked_end = max(blocked_end, idx)

        # 3. 다른 로봇의 계획된 경로와 교차 검사
        for other_robot_id, other_path in self.robot_paths.items():
            if other_robot_id == robot_id:
                continue

            # 경로 교차점 찾기
            crossing_nodes = self._find_path_crossing(planned_path, other_path)
            if crossing_nodes:
                if conflict_type == ConflictType.NO_CONFLICT:
                    conflict_type = ConflictType.PATH_CROSSING
                    conflicting_robot = other_robot_id
                    # 교차점의 첫 번째 인덱스 찾기
                    blocked_start = next(
                        (i for i, n in enumerate(planned_path) if n in crossing_nodes),
                        -1
                    )
                for node in crossing_nodes:
                    if node not in conflicting_nodes:
                        conflicting_nodes.append(node)

        # 4. Zone Manager를 통한 존 충돌 검사
        zone_conflicts = self._check_zone_conflicts(robot_id, planned_path)
        for node in zone_conflicts:
            if node not in conflicting_nodes:
                conflicting_nodes.append(node)
                if conflict_type == ConflictType.NO_CONFLICT:
                    conflict_type = ConflictType.NODE_RESERVED

        # 결과 생성
        has_conflict = len(conflicting_nodes) > 0
        message = self._generate_conflict_message(
            conflict_type, conflicting_robot, conflicting_nodes
        )

        return ConflictResult(
            has_conflict=has_conflict,
            conflict_type=conflict_type,
            conflicting_robot_id=conflicting_robot,
            conflicting_nodes=conflicting_nodes,
            blocked_segment_start=blocked_start,
            blocked_segment_end=blocked_end,
            message=message
        )

    def find_alternative_path(self, robot_id: str, start: str, goal: str,
                              blocked_nodes: Set[str]) -> Optional[List[str]]:
        """
        차단된 노드를 피해 대체 경로 탐색

        Dijkstra 알고리즘을 사용하여 blocked_nodes를 제외한 경로를 탐색합니다.

        Args:
            robot_id: 로봇 ID
            start: 시작 노드
            goal: 목표 노드
            blocked_nodes: 제외할 노드 집합

        Returns:
            대체 경로 리스트 또는 None (경로를 찾을 수 없는 경우)
        """
        logger.debug(f"[{robot_id}] 대체 경로 탐색: {start} -> {goal}, 제외: {blocked_nodes}")

        graph = self.navigation_graph
        vertices = graph.vertices
        adjacency = graph.adjacency

        # 시작/목표가 blocked 노드인 경우 탐색 불가
        if start in blocked_nodes or goal in blocked_nodes:
            logger.debug(f"[{robot_id}] 시작 또는 목표 노드가 차단됨")
            return None

        # Dijkstra 알고리즘 (blocked_nodes 제외)
        distances = {v: float('inf') for v in vertices if v not in blocked_nodes}
        if start not in distances:
            return None

        distances[start] = 0
        previous = {v: None for v in distances}
        pq = [(0, start)]
        visited = set()

        while pq:
            dist, current = heapq.heappop(pq)

            if current in visited:
                continue
            visited.add(current)

            if current == goal:
                break

            for neighbor in adjacency.get(current, []):
                # blocked 노드 스킵
                if neighbor in blocked_nodes or neighbor in visited:
                    continue

                if neighbor not in distances:
                    continue

                new_dist = dist + graph._distance(current, neighbor)
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = current
                    heapq.heappush(pq, (new_dist, neighbor))

        # 경로 재구성
        if goal not in distances or distances[goal] == float('inf'):
            logger.debug(f"[{robot_id}] 대체 경로를 찾을 수 없음")
            return None

        path = []
        current = goal
        while current is not None:
            path.append(current)
            current = previous.get(current)
        path.reverse()

        if len(path) > 1:
            logger.info(f"[{robot_id}] 대체 경로 발견: {' -> '.join(path)}")
            return path

        return None

    def determine_waiting_position(self, robot_id: str,
                                    conflict: ConflictResult) -> str:
        """
        충돌 시 대기 위치 결정

        전략:
        1. 대체 경로가 없을 때 막힌 구간 바로 앞에서 대기
        2. 안전한 대기 노드를 탐색하여 반환
        3. 픽업 대기의 경우 point13 또는 파킹 스팟 사용

        Args:
            robot_id: 로봇 ID
            conflict: 충돌 감지 결과

        Returns:
            대기할 노드 이름
        """
        # 픽업 슬롯 대기의 경우
        if conflict.conflict_type == ConflictType.PICKUP_SLOT_OCCUPIED:
            return self._get_pickup_waiting_position(robot_id)

        # 현재 로봇 경로 확인
        current_path = self.robot_paths.get(robot_id, [])
        if not current_path:
            # 경로가 없으면 파킹 스팟으로 대기
            return self.parking_spots.get(robot_id, 'point2')

        # 막힌 구간 바로 앞 노드 찾기
        if conflict.blocked_segment_start > 0:
            waiting_node = current_path[conflict.blocked_segment_start - 1]
            # 해당 노드가 안전한지 확인
            if self._is_safe_waiting_node(robot_id, waiting_node):
                return waiting_node

        # 안전한 대기 노드 탐색
        for node in current_path:
            if node not in conflict.conflicting_nodes:
                if self._is_safe_waiting_node(robot_id, node):
                    return node

        # 최후의 수단: 파킹 스팟 또는 보조 대기 노드
        parking_spot = self.parking_spots.get(robot_id)
        if parking_spot and self._is_safe_waiting_node(robot_id, parking_spot):
            return parking_spot

        for node in self.SECONDARY_WAITING_NODES:
            if self._is_safe_waiting_node(robot_id, node):
                return node

        # 기본값: 현재 위치 유지 (첫 번째 노드)
        return current_path[0] if current_path else 'point2'

    # =========================================================================
    # 공개 API: 경로 관리
    # =========================================================================

    def update_robot_path(self, robot_id: str, path: List[str]):
        """
        로봇 경로 업데이트

        Args:
            robot_id: 로봇 ID
            path: 새로운 경로 노드 리스트
        """
        if not path:
            logger.warning(f"[{robot_id}] 빈 경로로 업데이트 시도됨")
            return

        self.robot_paths[robot_id] = path.copy()
        self.robot_path_indices[robot_id] = 0

        # 경로의 다음 노드들을 예약
        self._reserve_upcoming_nodes(robot_id, path)

        logger.debug(f"[{robot_id}] 경로 업데이트: {' -> '.join(path)}")

    def advance_robot_position(self, robot_id: str, reached_node: str) -> Optional[str]:
        """
        로봇이 노드에 도달했을 때 경로 인덱스 업데이트

        Args:
            robot_id: 로봇 ID
            reached_node: 도달한 노드

        Returns:
            다음 목표 노드 또는 None (경로 완료 시)
        """
        path = self.robot_paths.get(robot_id)
        if not path:
            return None

        current_idx = self.robot_path_indices.get(robot_id, 0)

        # 현재 노드 예약 해제
        if reached_node in self.reserved_nodes and self.reserved_nodes[reached_node] == robot_id:
            del self.reserved_nodes[reached_node]

        # 인덱스 업데이트
        if current_idx < len(path) and path[current_idx] == reached_node:
            self.robot_path_indices[robot_id] = current_idx + 1

            # 다음 노드 반환
            if current_idx + 1 < len(path):
                next_node = path[current_idx + 1]
                logger.debug(f"[{robot_id}] {reached_node} 도달, 다음 목표: {next_node}")
                return next_node

        logger.debug(f"[{robot_id}] 경로 완료")
        return None

    def clear_robot_path(self, robot_id: str):
        """
        로봇 경로 완료/취소 시 제거

        Args:
            robot_id: 로봇 ID
        """
        # 예약된 노드 해제
        nodes_to_remove = [
            node for node, rid in self.reserved_nodes.items()
            if rid == robot_id
        ]
        for node in nodes_to_remove:
            del self.reserved_nodes[node]

        logger.info(f"[{robot_id}] 경로 클리어: 예약 해제 노드 {nodes_to_remove}")

        # 경로 정보 삭제
        if robot_id in self.robot_paths:
            del self.robot_paths[robot_id]
        if robot_id in self.robot_path_indices:
            del self.robot_path_indices[robot_id]

        # 대기 상태 해제
        self._clear_wait_state(robot_id)

        logger.info(f"[{robot_id}] 경로 및 예약 정보 클리어")

    def update_robot_position(self, robot_id: str, x: float, y: float) -> List[str]:
        """
        로봇 위치 업데이트 시 지나간 노드의 예약을 실시간으로 해제

        로봇이 특정 노드를 지나가면 해당 노드의 예약을 즉시 해제하여
        다른 로봇이 해당 노드를 사용할 수 있도록 합니다.

        Args:
            robot_id: 로봇 ID
            x: 현재 X 좌표
            y: 현재 Y 좌표

        Returns:
            해제된 노드 목록
        """
        released_nodes = []

        # 로봇의 경로가 없으면 무시
        path = self.robot_paths.get(robot_id)
        if not path:
            return released_nodes

        # 현재 위치에서 가장 가까운 노드 찾기
        nearest_node = self.navigation_graph.get_nearest_waypoint(x, y)
        if not nearest_node:
            return released_nodes

        # 현재 노드가 경로에 없으면 무시
        if nearest_node not in path:
            return released_nodes

        # 현재 노드의 인덱스 찾기
        try:
            current_idx = path.index(nearest_node)
        except ValueError:
            return released_nodes

        # 현재 노드 이전의 모든 노드 예약 해제
        for i in range(current_idx):
            node = path[i]
            if node in self.reserved_nodes and self.reserved_nodes[node] == robot_id:
                del self.reserved_nodes[node]
                released_nodes.append(node)

        # 경로 인덱스 업데이트
        self.robot_path_indices[robot_id] = current_idx

        if released_nodes:
            logger.info(f"[{robot_id}] 실시간 노드 해제: {released_nodes} (현재 위치: {nearest_node})")

        return released_nodes

    def get_robot_current_node(self, robot_id: str) -> Optional[str]:
        """
        로봇의 현재 노드(경로상 위치) 반환

        Args:
            robot_id: 로봇 ID

        Returns:
            현재 노드 이름 또는 None
        """
        path = self.robot_paths.get(robot_id)
        idx = self.robot_path_indices.get(robot_id, 0)

        if path and idx < len(path):
            return path[idx]
        return None

    def get_robot_remaining_path(self, robot_id: str) -> List[str]:
        """
        로봇의 남은 경로 반환

        Args:
            robot_id: 로봇 ID

        Returns:
            남은 경로 노드 리스트
        """
        path = self.robot_paths.get(robot_id, [])
        idx = self.robot_path_indices.get(robot_id, 0)

        return path[idx:] if path else []

    # =========================================================================
    # 공개 API: Pickup 대기열 관리
    # =========================================================================

    def manage_pickup_queue(self, robot_id: str,
                            action: str) -> Tuple[str, int]:
        """
        Pickup 대기열 통합 관리

        전략:
        - point13에서 1순위 대기
        - 다른 로봇들은 자신의 parking spot이나 point2/point3에서 대기

        Args:
            robot_id: 로봇 ID
            action: "join" (대기열 참가), "leave" (대기열 탈퇴), "check" (상태 확인)

        Returns:
            Tuple[str, int]: (대기 위치, 대기열 순위)
            - 순위 0: 픽업 가능
            - 순위 > 0: 대기 중
            - 순위 -1: 대기열에 없음
        """
        if action == "join":
            return self._join_pickup_queue(robot_id)
        elif action == "leave":
            return self._leave_pickup_queue(robot_id)
        elif action == "check":
            return self._check_pickup_queue(robot_id)
        else:
            logger.warning(f"[{robot_id}] 알 수 없는 pickup queue 액션: {action}")
            return "", -1

    def notify_pickup_complete(self, robot_id: str) -> Optional[str]:
        """
        픽업 완료 알림 및 다음 로봇 호출

        Args:
            robot_id: 픽업을 완료한 로봇 ID

        Returns:
            다음 픽업 차례인 로봇 ID 또는 None
        """
        self._leave_pickup_queue(robot_id)

        if self.pickup_queue:
            next_robot = self.pickup_queue[0]
            logger.info(f"[{next_robot}] 픽업 슬롯 사용 가능 알림")

            # 대기 상태 업데이트
            if next_robot in self.robot_wait_states:
                self._clear_wait_state(next_robot)

            return next_robot

        return None

    # =========================================================================
    # 공개 API: 경로 재계획 트리거
    # =========================================================================

    def handle_replan_trigger(self, robot_id: str,
                               trigger: ReplanTrigger) -> Tuple[List[str], bool]:
        """
        경로 재계획 트리거 처리

        다양한 상황에서 경로 재계획을 수행합니다:
        - NODE_OCCUPIED: 노드 점유 시
        - PATH_BLOCKED: 경로 차단 시
        - PICKUP_SLOT_AVAILABLE: 픽업 슬롯 사용 가능 시
        - ROBOT_MOVED: 다른 로봇 이동 시
        - TIMEOUT: 대기 타임아웃 시

        Args:
            robot_id: 로봇 ID
            trigger: 재계획 트리거 유형

        Returns:
            Tuple[List[str], bool]: (새 경로, 성공 여부)
        """
        logger.info(f"[{robot_id}] 경로 재계획 트리거: {trigger.value}")

        wait_state = self.robot_wait_states.get(robot_id)

        if trigger == ReplanTrigger.PICKUP_SLOT_AVAILABLE:
            # 픽업 슬롯 사용 가능 -> 픽업 위치로 경로 재계획
            current_node = self.get_robot_current_node(robot_id)
            if current_node:
                self._clear_wait_state(robot_id)
                return self.plan_path_with_avoidance(
                    robot_id, current_node, 'pickup_spot'
                )

        elif trigger in (ReplanTrigger.NODE_OCCUPIED, ReplanTrigger.PATH_BLOCKED):
            # 노드 점유 또는 경로 차단 -> 대체 경로 또는 대기
            if wait_state and wait_state.original_goal:
                current_node = self.get_robot_current_node(robot_id)
                if current_node:
                    return self.plan_path_with_avoidance(
                        robot_id, current_node, wait_state.original_goal
                    )

        elif trigger == ReplanTrigger.ROBOT_MOVED:
            # 다른 로봇 이동 -> 기존 경로 재검증
            if wait_state and wait_state.original_goal:
                current_node = wait_state.waiting_at or self.get_robot_current_node(robot_id)
                if current_node:
                    # 경로 재계획 시도
                    path, success = self.plan_path_with_avoidance(
                        robot_id, current_node, wait_state.original_goal
                    )
                    # 성공 시 대기 상태 정리
                    if success:
                        self._clear_wait_state(robot_id)
                    return path, success

        elif trigger == ReplanTrigger.TIMEOUT:
            # 대기 타임아웃 -> 강제 경로 재계획
            if wait_state and wait_state.original_goal:
                current_node = wait_state.waiting_at or self.get_robot_current_node(robot_id)
                if current_node:
                    # 타임아웃 시 충돌 노드 강제 무시 시도
                    self._clear_wait_state(robot_id)
                    return self.plan_path_with_avoidance(
                        robot_id, current_node, wait_state.original_goal
                    )

        return [], False

    def check_wait_timeout(self, robot_id: str) -> bool:
        """
        대기 타임아웃 확인

        Args:
            robot_id: 로봇 ID

        Returns:
            타임아웃 여부
        """
        wait_state = self.robot_wait_states.get(robot_id)
        if not wait_state or wait_state.state == WaitState.NOT_WAITING:
            return False

        if wait_state.waiting_since:
            elapsed = (datetime.utcnow() - wait_state.waiting_since).total_seconds()
            if elapsed > self.DEFAULT_WAIT_TIMEOUT:
                logger.warning(f"[{robot_id}] 대기 타임아웃 ({elapsed:.1f}초)")
                return True

        return False

    # =========================================================================
    # 공개 API: 상태 조회
    # =========================================================================

    def get_robot_wait_state(self, robot_id: str) -> Optional[RobotWaitState]:
        """로봇의 현재 대기 상태 반환"""
        return self.robot_wait_states.get(robot_id)

    def get_all_robot_paths(self) -> Dict[str, List[str]]:
        """모든 로봇의 경로 정보 반환"""
        return self.robot_paths.copy()

    def get_reserved_nodes(self) -> Dict[str, str]:
        """예약된 노드 정보 반환"""
        return self.reserved_nodes.copy()

    def get_pickup_queue_status(self) -> Dict:
        """픽업 대기열 상태 반환 (PickupSlotManager와 동기화)"""
        # PickupSlotManager가 있으면 위임
        if self.pickup_slot_manager is not None:
            queue = list(self.pickup_slot_manager.pickup_queue)
            return {
                'current_holder': self.pickup_slot_manager.current_holder,
                'queue': queue,
                'length': len(queue),
                'positions': {
                    robot_id: idx + 1
                    for idx, robot_id in enumerate(queue)
                }
            }

        # 폴백: 내부 큐 사용
        return {
            'current_holder': None,
            'queue': self.pickup_queue.copy(),
            'length': len(self.pickup_queue),
            'positions': {
                robot_id: idx
                for idx, robot_id in enumerate(self.pickup_queue)
            }
        }

    def get_collision_status_summary(self) -> Dict:
        """
        전체 충돌 회피 시스템 상태 요약

        Returns:
            상태 요약 딕셔너리
        """
        waiting_robots = [
            rid for rid, state in self.robot_wait_states.items()
            if state.state != WaitState.NOT_WAITING
        ]

        return {
            'active_paths': len(self.robot_paths),
            'reserved_nodes_count': len(self.reserved_nodes),
            'reserved_nodes': dict(self.reserved_nodes),
            'waiting_robots': waiting_robots,
            'waiting_states': {
                rid: {
                    'state': state.state.value,
                    'waiting_at': state.waiting_at,
                    'waiting_for': state.waiting_for,
                    'original_goal': state.original_goal
                }
                for rid, state in self.robot_wait_states.items()
                if state.state != WaitState.NOT_WAITING
            },
            'pickup_queue': self.get_pickup_queue_status()
        }

    # =========================================================================
    # 공개 API: 데드락 감지 및 해결
    # =========================================================================

    def detect_deadlock(self) -> Optional[Dict]:
        """
        데드락 상태 감지

        데드락 조건:
        1. 두 개 이상의 로봇이 서로를 대기 중 (순환 대기)
        2. 모든 관련 로봇이 동시에 대기 타임아웃 상태

        Returns:
            데드락 정보 딕셔너리 또는 None (데드락 없음)
            {
                'deadlock_detected': True,
                'involved_robots': ['pinky1', 'pinky2'],
                'wait_cycle': ['pinky1 -> pinky2', 'pinky2 -> pinky1'],
                'resolution_strategy': 'priority_based'
            }
        """
        # 대기 중인 로봇들의 대기 그래프 구성
        wait_graph: Dict[str, str] = {}  # {waiting_robot: blocking_robot}

        for robot_id, wait_state in self.robot_wait_states.items():
            if wait_state.state != WaitState.NOT_WAITING and wait_state.waiting_for:
                wait_graph[robot_id] = wait_state.waiting_for

        if len(wait_graph) < 2:
            return None

        # 순환 대기 감지 (DFS 기반 사이클 탐지)
        visited = set()
        rec_stack = set()
        cycle_path = []

        def dfs(robot: str, path: List[str]) -> bool:
            """DFS로 사이클 탐지"""
            if robot in rec_stack:
                # 사이클 발견
                cycle_start = path.index(robot)
                cycle_path.extend(path[cycle_start:])
                return True
            if robot in visited:
                return False

            visited.add(robot)
            rec_stack.add(robot)
            path.append(robot)

            next_robot = wait_graph.get(robot)
            if next_robot and dfs(next_robot, path):
                return True

            path.pop()
            rec_stack.remove(robot)
            return False

        # 모든 대기 로봇에서 DFS 시작
        for robot in wait_graph:
            if robot not in visited:
                if dfs(robot, []):
                    break

        if not cycle_path:
            return None

        # 데드락 발견
        logger.warning(f"[DEADLOCK] 데드락 감지: {' <-> '.join(cycle_path)}")

        wait_cycle = []
        for i, robot in enumerate(cycle_path):
            next_robot = cycle_path[(i + 1) % len(cycle_path)]
            wait_cycle.append(f"{robot} -> {next_robot}")

        return {
            'deadlock_detected': True,
            'involved_robots': cycle_path,
            'wait_cycle': wait_cycle,
            'resolution_strategy': 'priority_based'
        }

    def resolve_deadlock(self, deadlock_info: Dict) -> Optional[str]:
        """
        데드락 해결

        전략: 우선순위 기반 해결
        1. 가장 낮은 우선순위(높은 번호) 로봇이 양보
        2. 양보하는 로봇은 파킹 스팟으로 이동

        Args:
            deadlock_info: detect_deadlock()의 반환값

        Returns:
            양보하는 로봇 ID 또는 None
        """
        if not deadlock_info or not deadlock_info.get('deadlock_detected'):
            return None

        involved_robots = deadlock_info.get('involved_robots', [])
        if not involved_robots:
            return None

        # 우선순위 결정: pinky1 > pinky2 > pinky3
        # 숫자가 큰 로봇이 양보
        priority_order = {'pinky1': 1, 'pinky2': 2, 'pinky3': 3}
        yield_robot = max(involved_robots, key=lambda r: priority_order.get(r, 99))

        logger.info(f"[DEADLOCK] 해결: {yield_robot}이(가) 양보하여 파킹 스팟으로 이동")

        # 양보하는 로봇의 대기 상태 해제
        self._clear_wait_state(yield_robot)

        # 파킹 스팟으로 경로 재계획 트리거
        parking_spot = self.parking_spots.get(yield_robot)
        if parking_spot:
            current_node = self.get_robot_current_node(yield_robot)
            if current_node:
                # 간단한 파킹 경로 설정
                parking_path = self.navigation_graph.find_path(current_node, parking_spot)
                if parking_path:
                    self.update_robot_path(yield_robot, parking_path)
                    logger.info(f"[DEADLOCK] {yield_robot}: {current_node} -> {parking_spot}")

        return yield_robot

    def check_and_resolve_deadlock(self) -> bool:
        """
        데드락 확인 및 자동 해결

        Returns:
            데드락이 감지되고 해결되었으면 True
        """
        deadlock_info = self.detect_deadlock()
        if deadlock_info:
            yield_robot = self.resolve_deadlock(deadlock_info)
            if yield_robot:
                logger.info(f"[DEADLOCK] 자동 해결 완료: {yield_robot}이(가) 양보")
                return True
        return False

    # =========================================================================
    # 내부 헬퍼 메서드: 충돌 감지
    # =========================================================================

    def _get_occupied_nodes(self, exclude_robot: Optional[str] = None) -> Dict[str, str]:
        """
        다른 로봇들이 점유 중인 노드 목록 반환 (현재 위치 + 실제 남은 경로)

        로봇의 현재 위치를 기반으로 경로상에서 이미 지나간 노드는 제외하고,
        앞으로 지나갈 노드만 점유로 표시합니다.

        Args:
            exclude_robot: 제외할 로봇 ID

        Returns:
            {노드: 로봇ID} 딕셔너리
        """
        occupied = {}

        for robot in self.fleet_controller.get_all_robots():
            if robot.robot_id == exclude_robot:
                continue

            nearest_node = None

            # 1. 로봇의 현재 포즈에서 가장 가까운 노드
            if robot.current_pose:
                x = robot.current_pose.position.x
                y = robot.current_pose.position.y
                nearest_node = self.navigation_graph.get_nearest_waypoint(x, y)
                if nearest_node:
                    occupied[nearest_node] = robot.robot_id

            # 2. 로봇의 경로에서 현재 위치 이후 노드만 점유로 표시
            full_path = self.robot_paths.get(robot.robot_id, [])
            if full_path and nearest_node:
                # 현재 가장 가까운 노드가 경로에 있으면, 그 이후 노드만 포함
                try:
                    current_idx = full_path.index(nearest_node)
                    # 현재 노드 이후의 경로만 점유
                    ahead_path = full_path[current_idx + 1:]
                    for node in ahead_path:
                        if node not in occupied:
                            occupied[node] = robot.robot_id
                except ValueError:
                    # 현재 노드가 경로에 없으면 전체 남은 경로 사용 (fallback)
                    remaining_path = self.get_robot_remaining_path(robot.robot_id)
                    for node in remaining_path:
                        if node not in occupied:
                            occupied[node] = robot.robot_id
            elif full_path:
                # 현재 위치 정보 없으면 기존 방식 사용
                remaining_path = self.get_robot_remaining_path(robot.robot_id)
                for node in remaining_path:
                    if node not in occupied:
                        occupied[node] = robot.robot_id

        return occupied

    def _find_path_crossing(self, path1: List[str],
                            path2: List[str]) -> List[str]:
        """
        두 경로의 교차점 찾기

        Args:
            path1: 첫 번째 경로
            path2: 두 번째 경로

        Returns:
            교차하는 노드 리스트
        """
        return list(set(path1) & set(path2))

    def _check_zone_conflicts(self, robot_id: str,
                              path: List[str]) -> List[str]:
        """
        Zone Manager를 통한 존 충돌 검사

        Args:
            robot_id: 로봇 ID
            path: 검사할 경로

        Returns:
            충돌하는 노드 리스트
        """
        conflicts = []

        for node in path:
            # 노드에 해당하는 존 ID 찾기
            zone_id = self.zone_manager.get_zone_by_location(node)
            if zone_id:
                if self.zone_manager.check_collision_risk(robot_id, zone_id):
                    conflicts.append(node)

        return conflicts

    def _generate_conflict_message(self, conflict_type: ConflictType,
                                    conflicting_robot: Optional[str],
                                    conflicting_nodes: List[str]) -> str:
        """충돌 설명 메시지 생성"""
        if conflict_type == ConflictType.NO_CONFLICT:
            return "충돌 없음"

        robot_info = f"로봇 {conflicting_robot}" if conflicting_robot else "알 수 없는 원인"
        nodes_info = ", ".join(conflicting_nodes[:3])
        if len(conflicting_nodes) > 3:
            nodes_info += f" 외 {len(conflicting_nodes) - 3}개"

        messages = {
            ConflictType.NODE_OCCUPIED: f"{robot_info}이(가) 노드 점유 중: {nodes_info}",
            ConflictType.NODE_RESERVED: f"{robot_info}이(가) 노드 예약 중: {nodes_info}",
            ConflictType.PATH_CROSSING: f"{robot_info}의 경로와 교차: {nodes_info}",
            ConflictType.PATH_BLOCKED: f"경로 완전 차단: {nodes_info}",
            ConflictType.PICKUP_SLOT_OCCUPIED: f"픽업 슬롯이 {robot_info}에 의해 점유됨"
        }

        return messages.get(conflict_type, "알 수 없는 충돌")

    # =========================================================================
    # 내부 헬퍼 메서드: 대기 관리
    # =========================================================================

    def _is_safe_waiting_node(self, robot_id: str, node: str) -> bool:
        """
        노드가 안전한 대기 위치인지 확인

        Args:
            robot_id: 로봇 ID
            node: 확인할 노드

        Returns:
            안전 여부
        """
        # 다른 로봇이 점유 중인지 확인
        occupied = self._get_occupied_nodes(exclude_robot=robot_id)
        if node in occupied:
            return False

        # 다른 로봇이 예약 중인지 확인
        if node in self.reserved_nodes and self.reserved_nodes[node] != robot_id:
            return False

        return True

    def _set_wait_state(self, robot_id: str, state: WaitState,
                        waiting_at: str, waiting_for: Optional[str],
                        original_goal: str, blocked_nodes: List[str]):
        """대기 상태 설정"""
        self.robot_wait_states[robot_id] = RobotWaitState(
            robot_id=robot_id,
            state=state,
            waiting_at=waiting_at,
            waiting_for=waiting_for,
            waiting_since=datetime.utcnow(),
            original_goal=original_goal,
            blocked_nodes=blocked_nodes
        )
        logger.debug(f"[{robot_id}] 대기 상태 설정: {state.value} at {waiting_at}")

    def _clear_wait_state(self, robot_id: str):
        """대기 상태 해제"""
        if robot_id in self.robot_wait_states:
            del self.robot_wait_states[robot_id]
            logger.debug(f"[{robot_id}] 대기 상태 해제")

    # =========================================================================
    # 내부 헬퍼 메서드: 노드 예약
    # =========================================================================

    def _reserve_upcoming_nodes(self, robot_id: str, path: List[str],
                                 lookahead: int = 3):
        """
        경로의 다음 노드들을 예약

        Args:
            robot_id: 로봇 ID
            path: 경로
            lookahead: 미리 예약할 노드 수
        """
        current_idx = self.robot_path_indices.get(robot_id, 0)

        for i in range(current_idx, min(current_idx + lookahead, len(path))):
            node = path[i]
            # 이미 다른 로봇이 예약한 노드는 건너뜀
            if node not in self.reserved_nodes or self.reserved_nodes[node] == robot_id:
                self.reserved_nodes[node] = robot_id

    # =========================================================================
    # 내부 헬퍼 메서드: Pickup 대기열
    # =========================================================================

    def _get_pickup_waiting_position(self, robot_id: str) -> str:
        """
        픽업 대기 위치 결정

        Args:
            robot_id: 로봇 ID

        Returns:
            대기 위치 노드
        """
        # PickupSlotManager가 있으면 해당 큐 사용
        if self.pickup_slot_manager is not None:
            # 현재 점유자인지 확인
            if self.pickup_slot_manager.current_holder == robot_id:
                return self.PICKUP_WAITING_NODE

            queue = list(self.pickup_slot_manager.pickup_queue)
            if not queue or (queue and queue[0] == robot_id):
                # 대기열 1순위: point13
                return self.PICKUP_WAITING_NODE

            queue_position = queue.index(robot_id) if robot_id in queue else -1

            if queue_position == 0:
                # 대기열 1순위: point13
                return self.PICKUP_WAITING_NODE
            elif queue_position == 1:
                # 대기열 2순위: point2
                return 'point2'
            elif queue_position == 2:
                # 대기열 3순위: point3
                return 'point3'
            else:
                # 그 외: 파킹 스팟
                return self.parking_spots.get(robot_id, 'point2')

        # 폴백: 내부 큐 사용
        if not self.pickup_queue or self.pickup_queue[0] == robot_id:
            # 1순위: point13
            return self.PICKUP_WAITING_NODE

        queue_position = self.pickup_queue.index(robot_id) if robot_id in self.pickup_queue else -1

        if queue_position == 1:
            # 2순위: point2 또는 point3
            return 'point2'
        elif queue_position == 2:
            return 'point3'
        else:
            # 그 외: 파킹 스팟
            return self.parking_spots.get(robot_id, 'point2')

    def _join_pickup_queue(self, robot_id: str) -> Tuple[str, int]:
        """픽업 대기열 참가 (PickupSlotManager와 동기화)"""
        # PickupSlotManager가 있으면 위임
        if self.pickup_slot_manager is not None:
            granted = self.pickup_slot_manager.request_pickup_slot(robot_id)
            if granted:
                # 즉시 접근 허용
                return 'pickup_spot', 0
            else:
                # 대기열에 추가됨 - 위치와 순위 계산
                queue = list(self.pickup_slot_manager.pickup_queue)
                if robot_id in queue:
                    position = queue.index(robot_id) + 1  # 1-based (0 = current holder)
                else:
                    position = len(queue)
                waiting_position = self._get_pickup_waiting_position(robot_id)

                if position > 0:
                    first_waiting = queue[0] if queue else None
                    self._set_wait_state(
                        robot_id,
                        WaitState.WAITING_FOR_PICKUP,
                        waiting_position,
                        first_waiting,
                        'pickup_spot',
                        []
                    )
                return waiting_position, position

        # 폴백: 내부 큐 사용
        if robot_id not in self.pickup_queue:
            self.pickup_queue.append(robot_id)
            logger.info(f"[{robot_id}] 픽업 대기열 참가 (순위: {len(self.pickup_queue)})")

        position = self.pickup_queue.index(robot_id)
        waiting_position = self._get_pickup_waiting_position(robot_id)

        if position > 0:
            self._set_wait_state(
                robot_id,
                WaitState.WAITING_FOR_PICKUP,
                waiting_position,
                self.pickup_queue[0],
                'pickup_spot',
                []
            )

        return waiting_position, position

    def _leave_pickup_queue(self, robot_id: str) -> Tuple[str, int]:
        """픽업 대기열 탈퇴 (PickupSlotManager와 동기화)"""
        # PickupSlotManager가 있으면 위임
        if self.pickup_slot_manager is not None:
            self.pickup_slot_manager.release_pickup_slot(robot_id)
            self._clear_wait_state(robot_id)
            logger.info(f"[{robot_id}] 픽업 대기열 탈퇴 (via PickupSlotManager)")
            return "", -1

        # 폴백: 내부 큐 사용
        if robot_id in self.pickup_queue:
            self.pickup_queue.remove(robot_id)
            self._clear_wait_state(robot_id)
            logger.info(f"[{robot_id}] 픽업 대기열 탈퇴")

        return "", -1

    def _check_pickup_queue(self, robot_id: str) -> Tuple[str, int]:
        """픽업 대기열 상태 확인 (PickupSlotManager와 동기화)"""
        # PickupSlotManager가 있으면 위임
        if self.pickup_slot_manager is not None:
            # 현재 점유자인지 확인
            if self.pickup_slot_manager.current_holder == robot_id:
                return 'pickup_spot', 0

            # 대기열에 있는지 확인
            queue = list(self.pickup_slot_manager.pickup_queue)
            if robot_id in queue:
                position = queue.index(robot_id) + 1
                waiting_position = self._get_pickup_waiting_position(robot_id)
                return waiting_position, position
            return "", -1

        # 폴백: 내부 큐 사용
        if robot_id not in self.pickup_queue:
            return "", -1

        position = self.pickup_queue.index(robot_id)
        waiting_position = self._get_pickup_waiting_position(robot_id)

        return waiting_position, position


# =============================================================================
# 팩토리 함수
# =============================================================================

def create_collision_avoidance_controller(
    navigation_graph,
    zone_manager,
    fleet_controller,
    pickup_slot_manager=None
) -> CollisionAvoidanceController:
    """
    CollisionAvoidanceController 팩토리 함수

    의존성 주입을 통한 컨트롤러 생성을 캡슐화합니다.

    Args:
        navigation_graph: NavigationGraph 인스턴스
        zone_manager: ZoneManager 인스턴스
        fleet_controller: FleetController 인스턴스
        pickup_slot_manager: PickupSlotManager 인스턴스 (선택적)

    Returns:
        CollisionAvoidanceController 인스턴스
    """
    return CollisionAvoidanceController(
        navigation_graph=navigation_graph,
        zone_manager=zone_manager,
        fleet_controller=fleet_controller,
        pickup_slot_manager=pickup_slot_manager
    )
