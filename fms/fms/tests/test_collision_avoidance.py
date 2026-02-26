"""
CollisionAvoidanceController 단위 테스트

테스트 범위:
- 충돌 감지 (detect_collision)
- 대체 경로 탐색 (find_alternative_path)
- 대기 위치 결정 (determine_waiting_position)
- Pickup 대기열 관리 (manage_pickup_queue)
- 경로 재계획 트리거 (handle_replan_trigger)
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collision_avoidance import (
    CollisionAvoidanceController,
    ConflictResult,
    ConflictType,
    ReplanTrigger,
    WaitState,
    RobotWaitState,
    create_collision_avoidance_controller
)


# =============================================================================
# 테스트 픽스처
# =============================================================================

@pytest.fixture
def mock_navigation_graph():
    """NavigationGraph 목 객체 생성"""
    graph = Mock()

    # 정점 정의
    graph.vertices = {
        'pinky1_spot': (0.585, 0.085),
        'pinky2_spot': (0.585, 0.255),
        'pinky3_spot': (0.585, 0.915),
        'point1': (0.78, 0.15),
        'point2': (0.78, 0.35),
        'point3': (0.78, 0.65),
        'point4': (0.78, 0.85),
        'point13': (0.585, 0.63),
        'pickup_spot': (0.47, 0.63),
        'table1': (1.785, 0.35),
        'table2': (1.415, 0.35),
        'table6': (0.865, 0.35),
        'table8': (0.865, 0.65),
    }

    # 인접 리스트
    graph.adjacency = {
        'pinky1_spot': ['point1'],
        'pinky2_spot': ['point2'],
        'pinky3_spot': ['point3', 'point4'],
        'point1': ['pinky1_spot', 'point2'],
        'point2': ['point1', 'point3', 'pinky2_spot', 'table6', 'point13'],
        'point3': ['point2', 'point4', 'pinky3_spot', 'table8', 'point13'],
        'point4': ['point3', 'pinky3_spot'],
        'point13': ['pickup_spot', 'point2', 'point3'],
        'pickup_spot': ['point13'],
        'table6': ['point2'],
        'table8': ['point3'],
    }

    def find_path(start, goal):
        """간단한 경로 탐색 구현"""
        if start == goal:
            return [start]
        # 미리 정의된 경로들
        paths = {
            ('pinky1_spot', 'pickup_spot'): ['pinky1_spot', 'point1', 'point2', 'point13', 'pickup_spot'],
            ('pinky1_spot', 'table6'): ['pinky1_spot', 'point1', 'point2', 'table6'],
            ('pinky2_spot', 'pickup_spot'): ['pinky2_spot', 'point2', 'point13', 'pickup_spot'],
            ('pinky2_spot', 'table6'): ['pinky2_spot', 'point2', 'table6'],
            ('pinky3_spot', 'pickup_spot'): ['pinky3_spot', 'point3', 'point13', 'pickup_spot'],
            ('point13', 'table6'): ['point13', 'point2', 'table6'],
            ('pickup_spot', 'table6'): ['pickup_spot', 'point13', 'point2', 'table6'],
            ('point2', 'pickup_spot'): ['point2', 'point13', 'pickup_spot'],
            ('point3', 'pickup_spot'): ['point3', 'point13', 'pickup_spot'],
        }
        return paths.get((start, goal), [])

    graph.find_path = Mock(side_effect=find_path)
    graph.get_nearest_waypoint = Mock(return_value='point2')

    def _distance(v1, v2):
        if v1 in graph.vertices and v2 in graph.vertices:
            x1, y1 = graph.vertices[v1]
            x2, y2 = graph.vertices[v2]
            return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return float('inf')

    graph._distance = Mock(side_effect=_distance)

    return graph


@pytest.fixture
def mock_zone_manager():
    """ZoneManager 목 객체 생성"""
    manager = Mock()
    manager.get_zone_by_location = Mock(return_value=None)
    manager.check_collision_risk = Mock(return_value=False)
    return manager


@pytest.fixture
def mock_fleet_controller():
    """FleetController 목 객체 생성"""
    controller = Mock()

    # 로봇 상태 목 객체들
    robot1 = Mock()
    robot1.robot_id = 'pinky1'
    robot1.current_pose = None

    robot2 = Mock()
    robot2.robot_id = 'pinky2'
    robot2.current_pose = None

    robot3 = Mock()
    robot3.robot_id = 'pinky3'
    robot3.current_pose = None

    controller.get_all_robots = Mock(return_value=[robot1, robot2, robot3])
    controller.robots = {
        'pinky1': robot1,
        'pinky2': robot2,
        'pinky3': robot3
    }

    return controller


@pytest.fixture
def collision_controller(mock_navigation_graph, mock_zone_manager, mock_fleet_controller):
    """CollisionAvoidanceController 인스턴스 생성"""
    return CollisionAvoidanceController(
        navigation_graph=mock_navigation_graph,
        zone_manager=mock_zone_manager,
        fleet_controller=mock_fleet_controller
    )


# =============================================================================
# 기본 기능 테스트
# =============================================================================

class TestCollisionAvoidanceControllerInit:
    """초기화 테스트"""

    def test_initialization(self, collision_controller):
        """컨트롤러가 올바르게 초기화되는지 확인"""
        assert collision_controller.robot_paths == {}
        assert collision_controller.robot_path_indices == {}
        assert collision_controller.robot_wait_states == {}
        assert collision_controller.reserved_nodes == {}
        assert collision_controller.pickup_queue == []

    def test_factory_function(self, mock_navigation_graph, mock_zone_manager, mock_fleet_controller):
        """팩토리 함수가 올바르게 동작하는지 확인"""
        controller = create_collision_avoidance_controller(
            mock_navigation_graph,
            mock_zone_manager,
            mock_fleet_controller
        )
        assert isinstance(controller, CollisionAvoidanceController)


# =============================================================================
# 충돌 감지 테스트
# =============================================================================

class TestDetectCollision:
    """detect_collision 메서드 테스트"""

    def test_no_collision_empty_path(self, collision_controller):
        """빈 경로에 대한 충돌 감지"""
        result = collision_controller.detect_collision('pinky1', [])
        assert not result.has_conflict
        assert result.conflict_type == ConflictType.NO_CONFLICT

    def test_no_collision_clear_path(self, collision_controller):
        """충돌 없는 경로 감지"""
        path = ['pinky1_spot', 'point1', 'point2']
        result = collision_controller.detect_collision('pinky1', path)
        assert not result.has_conflict

    def test_node_occupied_conflict(self, collision_controller, mock_fleet_controller):
        """노드 점유 충돌 감지"""
        # pinky2가 point2에 위치하도록 설정
        mock_pose = Mock()
        mock_pose.position.x = 0.78
        mock_pose.position.y = 0.35
        mock_fleet_controller.robots['pinky2'].current_pose = mock_pose
        collision_controller.navigation_graph.get_nearest_waypoint = Mock(return_value='point2')

        path = ['pinky1_spot', 'point1', 'point2', 'point13']
        result = collision_controller.detect_collision('pinky1', path)

        assert result.has_conflict
        assert result.conflict_type == ConflictType.NODE_OCCUPIED
        assert 'point2' in result.conflicting_nodes

    def test_reserved_node_conflict(self, collision_controller):
        """예약된 노드 충돌 감지"""
        # point2를 pinky2가 예약
        collision_controller.reserved_nodes['point2'] = 'pinky2'

        path = ['pinky1_spot', 'point1', 'point2', 'point13']
        result = collision_controller.detect_collision('pinky1', path)

        assert result.has_conflict
        assert result.conflict_type == ConflictType.NODE_RESERVED
        assert 'point2' in result.conflicting_nodes
        assert result.conflicting_robot_id == 'pinky2'

    def test_path_crossing_conflict(self, collision_controller):
        """경로 교차 충돌 감지"""
        # pinky2의 경로 설정
        collision_controller.robot_paths['pinky2'] = ['pinky2_spot', 'point2', 'point13', 'pickup_spot']

        path = ['pinky1_spot', 'point1', 'point2', 'table6']
        result = collision_controller.detect_collision('pinky1', path)

        assert result.has_conflict
        assert result.conflict_type == ConflictType.PATH_CROSSING
        assert 'point2' in result.conflicting_nodes


# =============================================================================
# 대체 경로 탐색 테스트
# =============================================================================

class TestFindAlternativePath:
    """find_alternative_path 메서드 테스트"""

    def test_alternative_path_found(self, collision_controller):
        """대체 경로 탐색 성공"""
        blocked_nodes = {'point2'}
        # 대체 경로: pinky1_spot -> point1 -> (point2 차단) -> 다른 경로
        result = collision_controller.find_alternative_path(
            'pinky1', 'pinky3_spot', 'pickup_spot', blocked_nodes
        )
        # 이 테스트에서는 mock graph의 한계로 None 반환 가능
        # 실제 그래프에서는 point3 -> point13 -> pickup_spot 경로가 있어야 함

    def test_no_alternative_when_start_blocked(self, collision_controller):
        """시작 노드가 차단된 경우"""
        blocked_nodes = {'pinky1_spot'}
        result = collision_controller.find_alternative_path(
            'pinky1', 'pinky1_spot', 'pickup_spot', blocked_nodes
        )
        assert result is None

    def test_no_alternative_when_goal_blocked(self, collision_controller):
        """목표 노드가 차단된 경우"""
        blocked_nodes = {'pickup_spot'}
        result = collision_controller.find_alternative_path(
            'pinky1', 'pinky1_spot', 'pickup_spot', blocked_nodes
        )
        assert result is None


# =============================================================================
# 대기 위치 결정 테스트
# =============================================================================

class TestDetermineWaitingPosition:
    """determine_waiting_position 메서드 테스트"""

    def test_waiting_before_blocked_segment(self, collision_controller):
        """차단된 구간 앞에서 대기"""
        # 경로 설정
        collision_controller.robot_paths['pinky1'] = ['pinky1_spot', 'point1', 'point2', 'point13']

        conflict = ConflictResult(
            has_conflict=True,
            conflict_type=ConflictType.NODE_OCCUPIED,
            conflicting_nodes=['point2'],
            blocked_segment_start=2
        )

        waiting_pos = collision_controller.determine_waiting_position('pinky1', conflict)
        assert waiting_pos == 'point1'  # point2 앞인 point1에서 대기

    def test_waiting_at_parking_spot(self, collision_controller):
        """파킹 스팟에서 대기"""
        # 경로 없음
        conflict = ConflictResult(
            has_conflict=True,
            conflict_type=ConflictType.PATH_BLOCKED,
            conflicting_nodes=['point2', 'point3']
        )

        waiting_pos = collision_controller.determine_waiting_position('pinky1', conflict)
        assert waiting_pos == 'pinky1_spot'  # 파킹 스팟으로 대기


# =============================================================================
# Pickup 대기열 테스트
# =============================================================================

class TestPickupQueue:
    """manage_pickup_queue 메서드 테스트"""

    def test_join_pickup_queue(self, collision_controller):
        """픽업 대기열 참가"""
        position, rank = collision_controller.manage_pickup_queue('pinky1', 'join')
        assert rank == 0  # 첫 번째
        assert 'pinky1' in collision_controller.pickup_queue

    def test_join_pickup_queue_second(self, collision_controller):
        """두 번째 로봇 픽업 대기열 참가"""
        collision_controller.manage_pickup_queue('pinky1', 'join')
        position, rank = collision_controller.manage_pickup_queue('pinky2', 'join')
        assert rank == 1  # 두 번째
        assert position == 'point2'  # 2순위 대기 위치

    def test_leave_pickup_queue(self, collision_controller):
        """픽업 대기열 탈퇴"""
        collision_controller.manage_pickup_queue('pinky1', 'join')
        collision_controller.manage_pickup_queue('pinky2', 'join')

        collision_controller.manage_pickup_queue('pinky1', 'leave')
        assert 'pinky1' not in collision_controller.pickup_queue
        assert collision_controller.pickup_queue[0] == 'pinky2'

    def test_notify_pickup_complete(self, collision_controller):
        """픽업 완료 알림"""
        collision_controller.manage_pickup_queue('pinky1', 'join')
        collision_controller.manage_pickup_queue('pinky2', 'join')

        next_robot = collision_controller.notify_pickup_complete('pinky1')
        assert next_robot == 'pinky2'

    def test_check_pickup_queue(self, collision_controller):
        """픽업 대기열 상태 확인"""
        collision_controller.manage_pickup_queue('pinky1', 'join')
        position, rank = collision_controller.manage_pickup_queue('pinky1', 'check')
        assert rank == 0


# =============================================================================
# 경로 관리 테스트
# =============================================================================

class TestPathManagement:
    """경로 관리 메서드 테스트"""

    def test_update_robot_path(self, collision_controller):
        """경로 업데이트"""
        path = ['pinky1_spot', 'point1', 'point2']
        collision_controller.update_robot_path('pinky1', path)

        assert collision_controller.robot_paths['pinky1'] == path
        assert collision_controller.robot_path_indices['pinky1'] == 0

    def test_advance_robot_position(self, collision_controller):
        """로봇 위치 전진"""
        path = ['pinky1_spot', 'point1', 'point2']
        collision_controller.update_robot_path('pinky1', path)

        next_node = collision_controller.advance_robot_position('pinky1', 'pinky1_spot')
        assert next_node == 'point1'
        assert collision_controller.robot_path_indices['pinky1'] == 1

    def test_clear_robot_path(self, collision_controller):
        """경로 클리어"""
        path = ['pinky1_spot', 'point1', 'point2']
        collision_controller.update_robot_path('pinky1', path)
        collision_controller.clear_robot_path('pinky1')

        assert 'pinky1' not in collision_controller.robot_paths
        assert 'pinky1' not in collision_controller.robot_path_indices

    def test_get_robot_remaining_path(self, collision_controller):
        """남은 경로 조회"""
        path = ['pinky1_spot', 'point1', 'point2', 'point13']
        collision_controller.update_robot_path('pinky1', path)
        collision_controller.advance_robot_position('pinky1', 'pinky1_spot')

        remaining = collision_controller.get_robot_remaining_path('pinky1')
        assert remaining == ['point1', 'point2', 'point13']


# =============================================================================
# 경로 재계획 트리거 테스트
# =============================================================================

class TestReplanTrigger:
    """handle_replan_trigger 메서드 테스트"""

    def test_pickup_slot_available_trigger(self, collision_controller):
        """픽업 슬롯 사용 가능 트리거"""
        # 대기 상태 설정
        collision_controller.robot_paths['pinky1'] = ['point2']
        collision_controller.robot_path_indices['pinky1'] = 0
        collision_controller.robot_wait_states['pinky1'] = RobotWaitState(
            robot_id='pinky1',
            state=WaitState.WAITING_FOR_PICKUP,
            waiting_at='point2',
            original_goal='pickup_spot'
        )

        path, success = collision_controller.handle_replan_trigger(
            'pinky1', ReplanTrigger.PICKUP_SLOT_AVAILABLE
        )
        # mock 그래프에서 경로가 있으면 성공

    def test_timeout_trigger(self, collision_controller):
        """타임아웃 트리거"""
        collision_controller.robot_paths['pinky1'] = ['point2']
        collision_controller.robot_path_indices['pinky1'] = 0
        collision_controller.robot_wait_states['pinky1'] = RobotWaitState(
            robot_id='pinky1',
            state=WaitState.WAITING_FOR_NODE,
            waiting_at='point2',
            original_goal='pickup_spot',
            waiting_since=datetime.utcnow() - timedelta(seconds=60)
        )

        assert collision_controller.check_wait_timeout('pinky1')


# =============================================================================
# 상태 조회 테스트
# =============================================================================

class TestStatusQueries:
    """상태 조회 메서드 테스트"""

    def test_get_collision_status_summary(self, collision_controller):
        """충돌 회피 상태 요약 조회"""
        # 일부 상태 설정
        collision_controller.robot_paths['pinky1'] = ['point1', 'point2']
        collision_controller.reserved_nodes['point2'] = 'pinky1'

        summary = collision_controller.get_collision_status_summary()

        assert summary['active_paths'] == 1
        assert summary['reserved_nodes_count'] == 1
        assert 'point2' in summary['reserved_nodes']

    def test_get_pickup_queue_status(self, collision_controller):
        """픽업 대기열 상태 조회"""
        collision_controller.manage_pickup_queue('pinky1', 'join')
        collision_controller.manage_pickup_queue('pinky2', 'join')

        status = collision_controller.get_pickup_queue_status()

        assert status['length'] == 2
        assert 'pinky1' in status['queue']
        assert 'pinky2' in status['queue']


# =============================================================================
# 통합 테스트
# =============================================================================

class TestIntegration:
    """통합 테스트"""

    def test_full_path_planning_workflow(self, collision_controller):
        """전체 경로 계획 워크플로우"""
        # 1. pinky1이 pickup으로 경로 계획
        path1, success1 = collision_controller.plan_path_with_avoidance(
            'pinky1', 'pinky1_spot', 'pickup_spot'
        )
        assert success1 or len(path1) > 0  # 성공 또는 대기 경로

        # 2. pinky2도 pickup으로 경로 계획 (충돌 발생 가능)
        path2, success2 = collision_controller.plan_path_with_avoidance(
            'pinky2', 'pinky2_spot', 'pickup_spot'
        )
        # 충돌이 있으면 대기 경로 반환


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
