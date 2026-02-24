"""
Multi-Robot Integration Tests

Tests for:
- Multiple robots handling tasks simultaneously
- Namespace isolation (/pinky1 vs /pinky2 vs /pinky3)
- Task queue distribution across fleet
- Robot availability and load balancing
- Concurrent delivery operations

These tests verify the FMS can handle:
1. Multiple simultaneous deliveries
2. Task queueing when all robots are busy
3. Proper isolation of robot contexts
4. Fair distribution of work among robots
"""

import pytest
import uuid
import time
from typing import List, Dict
from geometry_msgs.msg import Pose

import sys
import os

# Add FMS module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

from fms.task_manager import Task, TaskManager
from fms.fleet_controller import RobotState, FleetController


class TestMultiRobotBasics:
    """Test basic multi-robot scenarios"""

    def test_three_robots_initialization(self):
        """Test that all 3 robots are properly initialized"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]

        fleet = FleetController(robot_configs)

        assert len(fleet.robots) == 3
        assert fleet.robots['pinky1'].robot_namespace == '/pinky1'
        assert fleet.robots['pinky2'].robot_namespace == '/pinky2'
        assert fleet.robots['pinky3'].robot_namespace == '/pinky3'

        for robot_id in ['pinky1', 'pinky2', 'pinky3']:
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_IDLE
            assert robot.is_available() == True

    def test_three_robots_in_fleet_status(self):
        """Test fleet status includes all robots"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]

        fleet = FleetController(robot_configs)
        summary = fleet.get_fleet_status_summary()

        assert summary['total_robots'] == 3
        assert summary['idle_robots'] == 3
        assert summary['busy_robots'] == 0
        assert len(summary['robots']) == 3

    def test_robot_namespace_isolation_pinky1(self):
        """Test pinky1 namespace is isolated"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]

        fleet = FleetController(robot_configs)

        pinky1 = fleet.get_robot('pinky1')
        pinky2 = fleet.get_robot('pinky2')

        assert pinky1.robot_namespace == '/pinky1'
        assert pinky2.robot_namespace == '/pinky2'
        assert pinky1.robot_namespace != pinky2.robot_namespace

    def test_robot_namespace_isolation_pinky2(self):
        """Test pinky2 namespace is isolated"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]

        fleet = FleetController(robot_configs)

        pinky2 = fleet.get_robot('pinky2')
        pinky3 = fleet.get_robot('pinky3')

        assert pinky2.robot_namespace == '/pinky2'
        assert pinky3.robot_namespace == '/pinky3'


class TestConcurrentDeliveries:
    """Test concurrent delivery operations"""

    def test_simultaneous_delivery_assignment(self):
        """Test assigning deliveries to all robots simultaneously"""
        # Setup
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Create 3 orders
        order_ids = [str(uuid.uuid4()) for _ in range(3)]
        for i, order_id in enumerate(order_ids):
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        # Assign to each robot
        assignments = []
        for _ in range(3):
            robot = fleet.get_available_robot()
            assert robot is not None
            task = manager.assign_task(robot.robot_id)
            fleet.assign_task_to_robot(robot.robot_id, task.task_id, task.order_id)
            assignments.append({
                'robot_id': robot.robot_id,
                'task_id': task.task_id,
                'order_id': task.order_id,
                'table': task.table_number
            })

        # Verify all robots are assigned
        assert len(assignments) == 3
        assigned_robots = {a['robot_id'] for a in assignments}
        assert assigned_robots == {'pinky1', 'pinky2', 'pinky3'}

        # Verify no robots available
        assert fleet.get_available_robot() is None

    def test_two_robots_busy_one_available(self):
        """Test when 2 robots are busy and 1 is available"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Assign tasks to pinky1 and pinky2
        order1 = str(uuid.uuid4())
        order2 = str(uuid.uuid4())
        manager.create_task(order1, 'M001', 'T01', 1, 'mayo', False)
        manager.create_task(order2, 'M001', 'T02', 1, 'mayo', False)

        task1 = manager.assign_task('pinky1')
        task2 = manager.assign_task('pinky2')
        fleet.assign_task_to_robot('pinky1', task1.task_id, order1)
        fleet.assign_task_to_robot('pinky2', task2.task_id, order2)

        # Check available robot
        available = fleet.get_available_robot()
        assert available is not None
        assert available.robot_id == 'pinky3'

    def test_sequential_delivery_with_queue(self):
        """Test sequential delivery when robot queue exists"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'}
        ]
        fleet = FleetController(robot_configs)

        # Create 3 orders
        for i in range(3):
            order_id = str(uuid.uuid4())
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        assert manager.get_pending_count() == 3

        # Assign first order
        robot = fleet.get_available_robot()
        task1 = manager.assign_task(robot.robot_id)
        fleet.assign_task_to_robot(robot.robot_id, task1.task_id, task1.order_id)

        assert manager.get_pending_count() == 2
        assert manager.get_active_count() == 1

        # Complete first delivery
        fleet.robot_returned_home('pinky1')
        manager.complete_task(task1.task_id)

        assert manager.get_active_count() == 0

        # Assign second order
        robot = fleet.get_available_robot()
        task2 = manager.assign_task(robot.robot_id)
        fleet.assign_task_to_robot(robot.robot_id, task2.task_id, task2.order_id)

        assert manager.get_pending_count() == 1
        assert manager.get_active_count() == 1


class TestLoadBalancing:
    """Test load balancing across robots"""

    def test_round_robin_assignment(self):
        """Test that robots are selected in round-robin fashion"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Create 6 orders
        for i in range(6):
            order_id = str(uuid.uuid4())
            manager.create_task(order_id, 'M001', f'T{(i%8)+1:02d}', 1, 'mayo', False)

        # Assign first 3 orders
        assignments = []
        for _ in range(3):
            robot = fleet.get_available_robot()
            task = manager.assign_task(robot.robot_id)
            fleet.assign_task_to_robot(robot.robot_id, task.task_id, task.order_id)
            assignments.append(robot.robot_id)

        # First 3 should be different robots
        assert len(set(assignments[:3])) == 3

    def test_available_robot_selection(self):
        """Test that first available robot is selected"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Busy pinky1
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

        # Get available
        robot = fleet.get_available_robot()
        assert robot.robot_id == 'pinky2'

        # Busy pinky2
        fleet.assign_task_to_robot('pinky2', 'TASK002', 'ORD002')

        # Get available
        robot = fleet.get_available_robot()
        assert robot.robot_id == 'pinky3'

    def test_battery_aware_selection(self):
        """Test that low battery robots are not selected"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Set pinky1 to low battery
        fleet.update_robot_battery('pinky1', 15.0, True)

        # Get available
        robot = fleet.get_available_robot()
        assert robot.robot_id == 'pinky2'


class TestRobotTaskTracking:
    """Test task tracking for each robot"""

    def test_get_robot_task(self):
        """Test getting task for specific robot"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]
        fleet = FleetController(robot_configs)

        # Create orders
        order1 = str(uuid.uuid4())
        order2 = str(uuid.uuid4())
        manager.create_task(order1, 'M001', 'T01', 1, 'mayo', False)
        manager.create_task(order2, 'M001', 'T02', 1, 'mayo', False)

        # Assign to robots
        task1 = manager.assign_task('pinky1')
        task2 = manager.assign_task('pinky2')

        # Get task by robot
        found_task1 = manager.get_task_by_robot('pinky1')
        found_task2 = manager.get_task_by_robot('pinky2')

        assert found_task1.assigned_robot == 'pinky1'
        assert found_task2.assigned_robot == 'pinky2'
        assert found_task1.task_id != found_task2.task_id

    def test_robot_independent_state(self):
        """Test that robot states are independent"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]
        fleet = FleetController(robot_configs)

        # Set pinky1 to moving
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')
        fleet.robot_reached_pickup('pinky1')

        # Set pinky2 to delivering
        fleet.assign_task_to_robot('pinky2', 'TASK002', 'ORD002')
        fleet.robot_reached_pickup('pinky2')
        fleet.robot_start_delivery('pinky2', 'T02')

        # Check states
        pinky1 = fleet.get_robot('pinky1')
        pinky2 = fleet.get_robot('pinky2')

        assert pinky1.status == RobotState.STATUS_LOADED
        assert pinky2.status == RobotState.STATUS_MOVING_TO_TABLE
        assert pinky1.status != pinky2.status


class TestMultiRobotDeliveryFlow:
    """Test complete delivery flows with multiple robots"""

    def test_three_concurrent_deliveries(self):
        """Test 3 robots making concurrent deliveries"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]
        fleet = FleetController(robot_configs)

        # Create 3 orders
        orders = [str(uuid.uuid4()) for _ in range(3)]
        tasks = []
        for i, order_id in enumerate(orders):
            task = manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)
            tasks.append((order_id, task))

        # Assign to robots
        assignments = []
        for i, (order_id, task) in enumerate(tasks):
            robot_id = ['pinky1', 'pinky2', 'pinky3'][i]
            assigned_task = manager.assign_task(robot_id)
            fleet.assign_task_to_robot(robot_id, assigned_task.task_id, order_id)
            assignments.append((robot_id, assigned_task.task_id, order_id))

        # All robots moving to pickup
        for robot_id, task_id, order_id in assignments:
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_MOVING_TO_PICKUP

        # All robots reach pickup
        for robot_id, task_id, order_id in assignments:
            fleet.robot_reached_pickup(robot_id)
            manager.start_task(task_id)
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_LOADED

        # All robots start delivery
        for robot_id, task_id, order_id in assignments:
            fleet.robot_start_delivery(robot_id, f'T{["pinky1", "pinky2", "pinky3"].index(robot_id)+1:02d}')
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_MOVING_TO_TABLE

        # All robots reach tables
        for robot_id, task_id, order_id in assignments:
            fleet.robot_reached_table(robot_id)
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_DELIVERING

        # Complete deliveries
        for robot_id, task_id, order_id in assignments:
            fleet.robot_complete_delivery(robot_id)
            manager.complete_task(task_id)
            fleet.robot_returned_home(robot_id)
            robot = fleet.get_robot(robot_id)
            assert robot.status == RobotState.STATUS_IDLE

        # Verify all completed
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 3
        assert fleet.get_available_robot() is not None

    def test_staggered_delivery_completion(self):
        """Test deliveries completing at different times"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]
        fleet = FleetController(robot_configs)

        # Create 2 orders
        order1 = str(uuid.uuid4())
        order2 = str(uuid.uuid4())
        manager.create_task(order1, 'M001', 'T01', 1, 'mayo', False)
        manager.create_task(order2, 'M001', 'T02', 1, 'mayo', False)

        # Assign
        task1 = manager.assign_task('pinky1')
        task2 = manager.assign_task('pinky2')
        fleet.assign_task_to_robot('pinky1', task1.task_id, order1)
        fleet.assign_task_to_robot('pinky2', task2.task_id, order2)

        # Pinky1 completes first
        fleet.robot_reached_pickup('pinky1')
        manager.start_task(task1.task_id)
        fleet.robot_start_delivery('pinky1', 'T01')
        fleet.robot_reached_table('pinky1')
        fleet.robot_complete_delivery('pinky1')
        manager.complete_task(task1.task_id)
        fleet.robot_returned_home('pinky1')

        # Pinky2 still delivering
        fleet.robot_reached_pickup('pinky2')
        manager.start_task(task2.task_id)
        fleet.robot_start_delivery('pinky2', 'T02')
        fleet.robot_reached_table('pinky2')

        # Verify states
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE
        assert fleet.get_robot('pinky2').status == RobotState.STATUS_DELIVERING
        assert manager.get_active_count() == 1
        assert len(manager.completed_tasks) == 1


class TestNamespaceIsolation:
    """Test namespace isolation for multi-robot scenarios"""

    def test_namespace_format(self):
        """Test that namespaces follow correct format"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]

        fleet = FleetController(robot_configs)

        for robot_id in ['pinky1', 'pinky2', 'pinky3']:
            robot = fleet.get_robot(robot_id)
            assert robot.robot_namespace.startswith('/')
            assert robot.robot_id in robot.robot_namespace

    def test_no_namespace_cross_talk(self):
        """Test that robot namespaces don't interfere"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]

        fleet = FleetController(robot_configs)

        # Modify pinky1
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')
        pose1 = Pose()
        pose1.position.x = 1.0
        fleet.update_robot_pose('pinky1', pose1)

        # Check pinky2 is unaffected
        pinky2 = fleet.get_robot('pinky2')
        assert pinky2.status == RobotState.STATUS_IDLE
        assert pinky2.current_task_id is None
        assert pinky2.current_pose is None


class TestErrorHandling:
    """Test error handling in multi-robot scenarios"""

    def test_robot_error_does_not_affect_others(self):
        """Test that one robot error doesn't affect others"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'}
        ]

        fleet = FleetController(robot_configs)

        # Pinky1 error
        fleet.robot_error('pinky1', 'Navigation failed')

        # Pinky2 should be fine
        pinky1 = fleet.get_robot('pinky1')
        pinky2 = fleet.get_robot('pinky2')

        assert pinky1.status == RobotState.STATUS_ERROR
        assert pinky2.status == RobotState.STATUS_IDLE

    def test_recovery_after_error(self):
        """Test robot can recover after error"""
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'}
        ]

        fleet = FleetController(robot_configs)

        # Error
        fleet.robot_error('pinky1', 'Navigation failed')
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_ERROR

        # Recovery (manual reset)
        fleet.get_robot('pinky1').update_status(RobotState.STATUS_IDLE)
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE

        # Should be available again
        assert fleet.get_available_robot() is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
