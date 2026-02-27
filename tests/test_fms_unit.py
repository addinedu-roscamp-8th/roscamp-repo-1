"""
Unit Tests for FMS Components

Tests for:
- TaskManager: Task creation, assignment, completion
- FleetController: Robot state management, task assignment
- RobotState: Robot status tracking

Test coverage:
- Task lifecycle (create -> assign -> start -> complete)
- Fleet robot availability and assignment
- Robot status transitions
- Battery monitoring
- Task lookup by order_id
"""

import pytest
import uuid
from datetime import datetime, timedelta
from geometry_msgs.msg import Pose
from std_msgs.msg import Float32

import sys
import os

# Add FMS module paths
fms_base = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, fms_base)

# Import directly from module files
import importlib.util
task_manager_path = os.path.join(fms_base, 'fms', 'fms', 'task_manager.py')
fleet_controller_path = os.path.join(fms_base, 'fms', 'fms', 'fleet_controller.py')

spec_tm = importlib.util.spec_from_file_location("task_manager", task_manager_path)
task_manager_module = importlib.util.module_from_spec(spec_tm)
spec_tm.loader.exec_module(task_manager_module)

spec_fc = importlib.util.spec_from_file_location("fleet_controller", fleet_controller_path)
fleet_controller_module = importlib.util.module_from_spec(spec_fc)
spec_fc.loader.exec_module(fleet_controller_module)

Task = task_manager_module.Task
TaskManager = task_manager_module.TaskManager
RobotState = fleet_controller_module.RobotState
FleetController = fleet_controller_module.FleetController


class TestTask:
    """Test Task class"""

    def test_task_creation(self):
        """Test creating a new task"""
        order_id = str(uuid.uuid4())
        task = Task(
            order_id=order_id,
            menu_id='M001',
            table_number='T01',
            quantity=1,
            sauce_type='mayo',
            voice_order=False
        )

        assert task.order_id == order_id
        assert task.menu_id == 'M001'
        assert task.table_number == 'T01'
        assert task.quantity == 1
        assert task.sauce_type == 'mayo'
        assert task.voice_order == False
        assert task.status == 'PENDING'
        assert task.assigned_robot is None
        assert task.created_at is not None
        assert task.assigned_at is None
        assert task.completed_at is None

    def test_task_assign_robot(self):
        """Test assigning task to robot"""
        task = Task('ORD001', 'M001', 'T01', 1, 'mayo', False)

        task.assign_robot('pinky1')

        assert task.assigned_robot == 'pinky1'
        assert task.status == 'ASSIGNED'
        assert task.assigned_at is not None

    def test_task_start(self):
        """Test starting a task"""
        task = Task('ORD001', 'M001', 'T01', 1, 'mayo', False)

        task.assign_robot('pinky1')
        task.start()

        assert task.status == 'IN_PROGRESS'

    def test_task_complete(self):
        """Test completing a task"""
        task = Task('ORD001', 'M001', 'T01', 1, 'mayo', False)

        task.assign_robot('pinky1')
        task.start()
        task.complete()

        assert task.status == 'COMPLETED'
        assert task.completed_at is not None

    def test_task_fail(self):
        """Test failing a task"""
        task = Task('ORD001', 'M001', 'T01', 1, 'mayo', False)

        task.assign_robot('pinky1')
        task.fail()

        assert task.status == 'FAILED'

    def test_task_to_dict(self):
        """Test converting task to dictionary"""
        task = Task('ORD001', 'M001', 'T01', 1, 'mayo', False)
        task.assign_robot('pinky1')

        task_dict = task.to_dict()

        assert task_dict['order_id'] == 'ORD001'
        assert task_dict['menu_id'] == 'M001'
        assert task_dict['table_number'] == 'T01'
        assert task_dict['assigned_robot'] == 'pinky1'
        assert task_dict['status'] == 'ASSIGNED'


class TestTaskManager:
    """Test TaskManager class"""

    def test_task_manager_creation(self):
        """Test creating TaskManager"""
        manager = TaskManager()

        assert manager.get_pending_count() == 0
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 0

    def test_create_task(self):
        """Test creating a task"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        task = manager.create_task(
            order_id=order_id,
            menu_id='M001',
            table_number='T01',
            quantity=1,
            sauce_type='mayo',
            voice_order=False
        )

        assert task.order_id == order_id
        assert manager.get_pending_count() == 1
        assert manager.task_lookup[order_id] == task.task_id

    def test_assign_task(self):
        """Test assigning a task to robot"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        task1 = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        task1_id = task1.task_id

        assigned_task = manager.assign_task('pinky1')

        assert assigned_task.task_id == task1_id
        assert assigned_task.assigned_robot == 'pinky1'
        assert assigned_task.status == 'ASSIGNED'
        assert manager.get_pending_count() == 0
        assert manager.get_active_count() == 1

    def test_start_task(self):
        """Test starting a task"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        task = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        task_id = task.task_id

        manager.assign_task('pinky1')
        success = manager.start_task(task_id)

        assert success == True
        task = manager.assigned_tasks[task_id]
        assert task.status == 'IN_PROGRESS'

    def test_complete_task(self):
        """Test completing a task"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        task = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        task_id = task.task_id

        manager.assign_task('pinky1')
        manager.start_task(task_id)
        success = manager.complete_task(task_id)

        assert success == True
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 1
        assert manager.completed_tasks[0].status == 'COMPLETED'

    def test_fail_task(self):
        """Test failing a task"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        task = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        task_id = task.task_id

        manager.assign_task('pinky1')
        success = manager.fail_task(task_id)

        assert success == True
        assert manager.get_pending_count() == 1  # Back in queue
        assert manager.get_active_count() == 0

    def test_get_task_by_order_id_from_assigned(self):
        """Test getting task by order_id from assigned tasks"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        manager.assign_task('pinky1')

        found_task = manager.get_task_by_order_id(order_id)

        assert found_task is not None
        assert found_task.order_id == order_id
        assert found_task.assigned_robot == 'pinky1'

    def test_get_task_by_order_id_from_pending(self):
        """Test getting task by order_id from pending tasks"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)

        found_task = manager.get_task_by_order_id(order_id)

        assert found_task is not None
        assert found_task.order_id == order_id
        assert found_task.status == 'PENDING'

    def test_get_task_by_robot(self):
        """Test getting task assigned to robot"""
        manager = TaskManager()
        order_id = str(uuid.uuid4())

        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        manager.assign_task('pinky1')

        task = manager.get_task_by_robot('pinky1')

        assert task is not None
        assert task.assigned_robot == 'pinky1'

    def test_get_task_by_robot_none(self):
        """Test getting task for robot with no task"""
        manager = TaskManager()

        task = manager.get_task_by_robot('pinky1')

        assert task is None

    def test_multiple_tasks_queue(self):
        """Test multiple tasks in queue"""
        manager = TaskManager()

        orders = [str(uuid.uuid4()) for _ in range(3)]
        for i, order_id in enumerate(orders):
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        assert manager.get_pending_count() == 3

        # Assign all tasks
        task1 = manager.assign_task('pinky1')
        task2 = manager.assign_task('pinky2')
        task3 = manager.assign_task('pinky3')

        assert manager.get_pending_count() == 0
        assert manager.get_active_count() == 3
        assert task1.assigned_robot == 'pinky1'
        assert task2.assigned_robot == 'pinky2'
        assert task3.assigned_robot == 'pinky3'

    def test_get_status_summary(self):
        """Test getting status summary"""
        manager = TaskManager()

        # Create 3 tasks
        for i in range(3):
            order_id = str(uuid.uuid4())
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        # Assign all 3 tasks
        task1 = manager.assign_task('pinky1')
        task2 = manager.assign_task('pinky2')
        task3 = manager.assign_task('pinky3')

        # Start and complete first one
        manager.start_task(task1.task_id)
        manager.complete_task(task1.task_id)

        summary = manager.get_status_summary()

        assert summary['pending'] == 0
        assert summary['assigned'] == 2  # task2 and task3 are still assigned
        assert summary['completed'] == 1


class TestRobotState:
    """Test RobotState class"""

    def test_robot_state_creation(self):
        """Test creating robot state"""
        robot = RobotState('pinky1', 11)

        assert robot.robot_id == 'pinky1'
        assert robot.domain_id == 11  # domain_id is now an integer
        assert robot.status == RobotState.STATUS_IDLE
        assert robot.current_pose is None
        assert robot.battery_voltage == 0.0
        assert robot.battery_present == False
        assert robot.current_task_id is None
        assert robot.target_location is None

    def test_robot_update_pose(self):
        """Test updating robot pose"""
        robot = RobotState('pinky1', 11)
        pose = Pose()
        pose.position.x = 1.0
        pose.position.y = 2.0

        robot.update_pose(pose)

        assert robot.current_pose == pose
        assert robot.last_update is not None

    def test_robot_update_battery(self):
        """Test updating robot battery"""
        robot = RobotState('pinky1', 11)

        robot.update_battery(24.5, True)

        assert robot.battery_voltage == 24.5
        assert robot.battery_present == True

    def test_robot_update_status(self):
        """Test updating robot status"""
        robot = RobotState('pinky1', 11)

        robot.update_status(RobotState.STATUS_MOVING_TO_PICKUP)

        assert robot.status == RobotState.STATUS_MOVING_TO_PICKUP

    def test_robot_assign_task(self):
        """Test assigning task to robot"""
        robot = RobotState('pinky1', 11)
        task_id = str(uuid.uuid4())
        order_id = 'ORD001'

        robot.assign_task(task_id, order_id)

        assert robot.current_task_id == task_id
        assert robot.current_order_id == order_id

    def test_robot_clear_task(self):
        """Test clearing task from robot"""
        robot = RobotState('pinky1', 11)

        robot.assign_task('TASK001', 'ORD001')
        robot.target_location = 'table1'
        robot.clear_task()

        assert robot.current_task_id is None
        assert robot.current_order_id is None
        assert robot.target_location is None

    def test_robot_is_available(self):
        """Test checking if robot is available"""
        robot = RobotState('pinky1', 11)

        assert robot.is_available() == True

        robot.assign_task('TASK001', 'ORD001')

        assert robot.is_available() == False

        robot.clear_task()

        assert robot.is_available() == True

    def test_robot_is_low_battery(self):
        """Test checking low battery"""
        robot = RobotState('pinky1', 11)

        assert robot.is_low_battery() == False

        robot.update_battery(15.0, True)

        assert robot.is_low_battery(threshold=20.0) == True

        robot.update_battery(25.0, True)

        assert robot.is_low_battery(threshold=20.0) == False

    def test_robot_status_transitions(self):
        """Test robot status state transitions"""
        robot = RobotState('pinky1', 11)

        # IDLE -> MOVING_TO_PICKUP
        robot.update_status(RobotState.STATUS_MOVING_TO_PICKUP)
        assert robot.status == RobotState.STATUS_MOVING_TO_PICKUP

        # MOVING_TO_PICKUP -> LOADED
        robot.update_status(RobotState.STATUS_LOADED)
        assert robot.status == RobotState.STATUS_LOADED

        # LOADED -> MOVING_TO_TABLE
        robot.update_status(RobotState.STATUS_MOVING_TO_TABLE)
        assert robot.status == RobotState.STATUS_MOVING_TO_TABLE

        # MOVING_TO_TABLE -> DELIVERING
        robot.update_status(RobotState.STATUS_DELIVERING)
        assert robot.status == RobotState.STATUS_DELIVERING

        # DELIVERING -> RETURNING
        robot.update_status(RobotState.STATUS_RETURNING)
        assert robot.status == RobotState.STATUS_RETURNING

        # RETURNING -> IDLE
        robot.update_status(RobotState.STATUS_IDLE)
        assert robot.status == RobotState.STATUS_IDLE


class TestFleetController:
    """Test FleetController class"""

    def test_fleet_controller_creation(self):
        """Test creating fleet controller"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12},
            {'robot_id': 'pinky3', 'domain_id': 13}
        ]

        fleet = FleetController(robot_configs)

        assert len(fleet.robots) == 3
        assert 'pinky1' in fleet.robots
        assert 'pinky2' in fleet.robots
        assert 'pinky3' in fleet.robots

    def test_get_available_robot(self):
        """Test getting available robot"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12}
        ]

        fleet = FleetController(robot_configs)

        robot = fleet.get_available_robot()

        assert robot is not None
        assert robot.robot_id == 'pinky1'

    def test_get_available_robot_none_when_busy(self):
        """Test getting available robot when all are busy"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)
        pinky1 = fleet.get_robot('pinky1')
        pinky1.assign_task('TASK001', 'ORD001')

        robot = fleet.get_available_robot()

        assert robot is None

    def test_assign_task_to_robot(self):
        """Test assigning task to robot"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        success = fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

        assert success == True
        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_MOVING_TO_PICKUP
        assert robot.current_task_id == 'TASK001'

    def test_robot_reached_pickup(self):
        """Test robot reached pickup spot"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

        fleet.robot_reached_pickup('pinky1')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_LOADED

    def test_robot_start_delivery(self):
        """Test robot starting delivery"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        fleet.robot_start_delivery('pinky1', 'T01')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_MOVING_TO_TABLE
        assert robot.target_location == 'table01'  # T01.lower() -> t01 -> table01

    def test_robot_reached_table(self):
        """Test robot reached table"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        fleet.robot_reached_table('pinky1')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_DELIVERING

    def test_robot_complete_delivery(self):
        """Test robot completing delivery"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        fleet.robot_complete_delivery('pinky1')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_RETURNING
        assert robot.target_location == 'pinky1_spot'

    def test_robot_returned_home(self):
        """Test robot returning home"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

        fleet.robot_returned_home('pinky1')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_IDLE
        assert robot.current_task_id is None

    def test_update_robot_battery(self):
        """Test updating robot battery"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        fleet.update_robot_battery('pinky1', 24.5, True)

        robot = fleet.get_robot('pinky1')
        assert robot.battery_voltage == 24.5
        assert robot.battery_present == True

    def test_robot_error(self):
        """Test robot error handling"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        fleet.robot_error('pinky1', 'Navigation failed')

        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_ERROR

    def test_get_fleet_status_summary(self):
        """Test getting fleet status summary"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12}
        ]

        fleet = FleetController(robot_configs)

        # Assign task to pinky1
        fleet.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

        summary = fleet.get_fleet_status_summary()

        assert summary['total_robots'] == 2
        assert summary['idle_robots'] == 1
        assert summary['busy_robots'] == 1

    def test_calculate_distance(self):
        """Test calculating distance between poses"""
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]

        fleet = FleetController(robot_configs)

        pose1 = Pose()
        pose1.position.x = 0.0
        pose1.position.y = 0.0

        pose2 = Pose()
        pose2.position.x = 3.0
        pose2.position.y = 4.0

        distance = fleet.calculate_distance(pose1, pose2)

        assert abs(distance - 5.0) < 0.01  # 3-4-5 triangle


class TestFMSIntegration:
    """Integration tests for FMS components"""

    def test_task_assignment_flow(self):
        """Test complete task assignment flow"""
        # Setup
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12}
        ]
        fleet = FleetController(robot_configs)

        # Create order
        order_id = str(uuid.uuid4())
        task = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        assert manager.get_pending_count() == 1

        # Get available robot
        robot = fleet.get_available_robot()
        assert robot is not None
        assert robot.robot_id == 'pinky1'

        # Assign task
        assigned_task = manager.assign_task(robot.robot_id)
        fleet.assign_task_to_robot(robot.robot_id, assigned_task.task_id, order_id)

        assert manager.get_active_count() == 1
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_MOVING_TO_PICKUP

    def test_multi_robot_task_queue(self):
        """Test task queue with multiple robots"""
        # Setup
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12},
            {'robot_id': 'pinky3', 'domain_id': 13}
        ]
        fleet = FleetController(robot_configs)

        # Create 3 orders
        for i in range(3):
            order_id = str(uuid.uuid4())
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        # Assign to all robots
        for _ in range(3):
            robot = fleet.get_available_robot()
            task = manager.assign_task(robot.robot_id)
            fleet.assign_task_to_robot(robot.robot_id, task.task_id, task.order_id)

        assert manager.get_pending_count() == 0
        assert manager.get_active_count() == 3
        assert fleet.get_available_robot() is None

    def test_full_delivery_lifecycle(self):
        """Test complete delivery lifecycle"""
        # Setup
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)

        # Step 1: Order arrives
        order_id = str(uuid.uuid4())
        task = manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        task_id = task.task_id

        # Step 2: Assign to robot
        robot = fleet.get_available_robot()
        assigned_task = manager.assign_task(robot.robot_id)
        fleet.assign_task_to_robot(robot.robot_id, assigned_task.task_id, order_id)

        # Step 3: Robot reaches pickup
        fleet.robot_reached_pickup(robot.robot_id)

        # Step 4: Food loaded, start delivery
        manager.start_task(task_id)
        fleet.robot_start_delivery(robot.robot_id, 'T01')

        # Step 5: Robot reaches table
        fleet.robot_reached_table(robot.robot_id)

        # Step 6: Delivery complete, return
        fleet.robot_complete_delivery(robot.robot_id)

        # Step 7: Robot home
        manager.complete_task(task_id)
        fleet.robot_returned_home(robot.robot_id)

        # Verify
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 1
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE
        assert fleet.get_available_robot() is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
