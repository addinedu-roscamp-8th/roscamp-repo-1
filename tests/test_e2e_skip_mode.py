"""
End-to-End Tests with Skip Mode

Tests the complete FMS delivery flow with skip_robot_arm mode enabled:

1. GUI order → FMS (order_request published)
2. FMS receives order, creates task
3. FMS assigns task to available robot
4. Robot navigates to point13 (pickup_spot)
5. Robot reaches point13, sends goal_arrived signal
6. [SKIP] Precision parking point13→pickup_spot (simulated)
7. [SKIP] Robot arm food loading (simulated after 3 seconds)
8. Robot receives food_loaded signal
9. Robot navigates to customer table
10. Robot reaches table, waiting for customer
11. Customer clicks delivery complete
12. Robot returns to parking spot
13. Robot becomes IDLE

Test scenarios:
- Single robot E2E flow
- Multiple concurrent E2E flows
- Skip mode timing validation
- Message sequence validation
- State transition validation
"""

import pytest
import uuid
import time
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from geometry_msgs.msg import Pose

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


class SkipModeSimulator:
    """
    Simulates the FMS behavior with skip_robot_arm mode enabled.

    In skip mode:
    - Precision parking is skipped (automatic)
    - Robot arm loading is skipped (automatic after 3 seconds)
    """

    def __init__(self, manager: TaskManager, fleet: FleetController):
        self.manager = manager
        self.fleet = fleet
        self.skip_mode = True
        self.event_log = []

    def log_event(self, event_type: str, details: Dict = None):
        """Log an event for verification"""
        event = {
            'timestamp': datetime.utcnow(),
            'type': event_type,
            'details': details or {}
        }
        self.event_log.append(event)

    def process_pending_tasks(self) -> bool:
        """Process pending tasks (simulates FMS task assignment loop)"""
        if self.manager.get_pending_count() == 0:
            return False

        robot = self.fleet.get_available_robot()
        if not robot:
            return False

        task = self.manager.assign_task(robot.robot_id)
        if task:
            self.fleet.assign_task_to_robot(
                robot.robot_id,
                task.task_id,
                task.order_id
            )
            self.log_event('task_assigned', {
                'robot_id': robot.robot_id,
                'task_id': task.task_id,
                'order_id': task.order_id,
                'table': task.table_number
            })
            return True
        return False

    def simulate_robot_navigation(self, robot_id: str, target_location: str):
        """
        Simulate robot reaching target location

        This is called when the FMS detects robot reached destination via pose callback.
        """
        robot = self.fleet.get_robot(robot_id)
        if not robot:
            return

        if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
            # Robot reached pickup spot
            self.fleet.robot_reached_pickup(robot_id)
            self.log_event('robot_reached_pickup', {
                'robot_id': robot_id,
                'status': robot.status
            })

            # In skip mode, auto-simulate food loading after 3 seconds
            if self.skip_mode:
                task = self.manager.get_task_by_robot(robot_id)
                if task:
                    # Simulate: precision_parked message (immediate)
                    self.log_event('precision_parked_simulated', {
                        'robot_id': robot_id
                    })

                    # Simulate: food_loaded message (after 3 seconds)
                    # In real FMS, this would be a timer. For testing, we'll do it immediately
                    # but log the 3-second delay intention.
                    self.log_event('food_loaded_simulated', {
                        'robot_id': robot_id,
                        'delay_seconds': 3
                    })

                    # Trigger food loaded handling
                    self.handle_food_loaded(robot_id, task.order_id)

        elif robot.status == RobotState.STATUS_MOVING_TO_TABLE:
            # Robot reached table
            self.fleet.robot_reached_table(robot_id)
            self.log_event('robot_reached_table', {
                'robot_id': robot_id,
                'status': robot.status
            })

        elif robot.status == RobotState.STATUS_RETURNING:
            # Robot returned to parking
            self.fleet.robot_returned_home(robot_id)
            self.log_event('robot_returned_home', {
                'robot_id': robot_id,
                'status': robot.status
            })

    def handle_food_loaded(self, robot_id: str, order_id: str):
        """Handle food_loaded message (from skip mode)"""
        task = self.manager.get_task_by_order_id(order_id)
        if task and task.assigned_robot == robot_id:
            self.manager.start_task(task.task_id)
            self.fleet.robot_start_delivery(robot_id, task.table_number)
            self.log_event('food_loaded_handled', {
                'robot_id': robot_id,
                'order_id': order_id,
                'task_id': task.task_id,
                'table': task.table_number
            })

    def handle_delivery_complete(self, order_id: str):
        """Handle delivery_complete message (from GUI)"""
        task = self.manager.get_task_by_order_id(order_id)
        if task and task.assigned_robot:
            robot_id = task.assigned_robot
            self.fleet.robot_complete_delivery(robot_id)
            self.manager.complete_task(task.task_id)
            self.log_event('delivery_complete', {
                'robot_id': robot_id,
                'order_id': order_id,
                'task_id': task.task_id
            })

    def get_event_log(self) -> List[Dict]:
        """Get all logged events"""
        return self.event_log

    def verify_event_sequence(self, expected_sequence: List[str]) -> bool:
        """Verify events occurred in expected sequence"""
        event_types = [e['type'] for e in self.event_log]
        return event_types == expected_sequence


class TestSingleRobotE2E:
    """Test E2E flow with single robot"""

    def test_complete_delivery_flow(self):
        """Test complete single-robot delivery flow"""
        # Setup
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        # Step 1: Order arrives
        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.log_event('order_received', {'order_id': order_id})

        # Step 2: Process pending tasks (FMS assignment)
        simulator.process_pending_tasks()

        # Step 3: Robot navigates to pickup
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')

        # Step 4: Verify food loaded was simulated
        task = manager.get_task_by_order_id(order_id)
        assert task.status == 'IN_PROGRESS'

        # Step 5: Robot navigates to table
        simulator.simulate_robot_navigation('pinky1', 'table1')

        # Step 6: Customer delivery complete
        simulator.handle_delivery_complete(order_id)

        # Step 7: Robot returns to parking
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        # Verify final state
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 1
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE

        # Verify event sequence
        expected = [
            'order_received',
            'task_assigned',
            'robot_reached_pickup',
            'precision_parked_simulated',
            'food_loaded_simulated',
            'food_loaded_handled',
            'robot_reached_table',
            'delivery_complete',
            'robot_returned_home'
        ]
        assert simulator.verify_event_sequence(expected)

    def test_skip_mode_timing(self):
        """Test that skip mode has proper timing simulation"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        # Create order
        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)

        # Assign
        simulator.process_pending_tasks()

        # Simulate pickup arrival
        start_time = datetime.utcnow()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')

        # Check that food_loaded event logged a 3-second delay
        food_loaded_events = [e for e in simulator.get_event_log()
                             if e['type'] == 'food_loaded_simulated']
        assert len(food_loaded_events) > 0
        assert food_loaded_events[0]['details']['delay_seconds'] == 3

    def test_task_completion_tracking(self):
        """Test that task completion is properly tracked"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)

        # Full flow
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')
        simulator.handle_delivery_complete(order_id)
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        # Verify task is in completed_tasks
        completed_task = manager.completed_tasks[0]
        assert completed_task.order_id == order_id
        assert completed_task.status == 'COMPLETED'
        assert completed_task.completed_at is not None


class TestMultipleRobotsE2E:
    """Test E2E flow with multiple robots"""

    def test_two_concurrent_deliveries(self):
        """Test 2 concurrent deliveries with skip mode"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        # Create 2 orders
        order1 = str(uuid.uuid4())
        order2 = str(uuid.uuid4())
        manager.create_task(order1, 'M001', 'T01', 1, 'mayo', False)
        manager.create_task(order2, 'M001', 'T02', 1, 'mayo', False)
        simulator.log_event('orders_received', {
            'order1': order1,
            'order2': order2
        })

        # Assign both
        simulator.process_pending_tasks()
        simulator.process_pending_tasks()

        assert manager.get_active_count() == 2

        # Both robots navigate to pickup
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky2', 'pickup_spot')

        # Verify both got food_loaded
        task1 = manager.get_task_by_order_id(order1)
        task2 = manager.get_task_by_order_id(order2)
        assert task1.status == 'IN_PROGRESS'
        assert task2.status == 'IN_PROGRESS'

        # Both navigate to tables
        simulator.simulate_robot_navigation('pinky1', 'table1')
        simulator.simulate_robot_navigation('pinky2', 'table2')

        # Complete both deliveries
        simulator.handle_delivery_complete(order1)
        simulator.handle_delivery_complete(order2)

        # Both return home
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')
        simulator.simulate_robot_navigation('pinky2', 'pinky2_spot')

        # Verify state
        assert manager.get_active_count() == 0
        assert len(manager.completed_tasks) == 2
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE
        assert fleet.get_robot('pinky2').status == RobotState.STATUS_IDLE

    def test_three_concurrent_deliveries(self):
        """Test 3 concurrent deliveries with skip mode"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11},
            {'robot_id': 'pinky2', 'domain_id': 12},
            {'robot_id': 'pinky3', 'domain_id': 13}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        # Create 3 orders
        orders = [str(uuid.uuid4()) for _ in range(3)]
        tables = ['T01', 'T02', 'T03']
        for order_id, table in zip(orders, tables):
            manager.create_task(order_id, 'M001', table, 1, 'mayo', False)

        # Assign all
        for _ in range(3):
            simulator.process_pending_tasks()

        # All navigate to pickup
        for robot_id in ['pinky1', 'pinky2', 'pinky3']:
            simulator.simulate_robot_navigation(robot_id, 'pickup_spot')

        # All navigate to tables
        for robot_id, table in zip(['pinky1', 'pinky2', 'pinky3'], tables):
            simulator.simulate_robot_navigation(robot_id, table.lower())

        # Complete all
        for order_id in orders:
            simulator.handle_delivery_complete(order_id)

        # Return home
        for robot_id in ['pinky1', 'pinky2', 'pinky3']:
            simulator.simulate_robot_navigation(robot_id, f'{robot_id}_spot')

        # Verify
        assert len(manager.completed_tasks) == 3
        for robot_id in ['pinky1', 'pinky2', 'pinky3']:
            assert fleet.get_robot(robot_id).status == RobotState.STATUS_IDLE


class TestSkipModeEdgeCases:
    """Test edge cases in skip mode"""

    def test_skip_mode_with_queue(self):
        """Test skip mode with queued orders"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        # Create 3 orders
        orders = [str(uuid.uuid4()) for _ in range(3)]
        for i, order_id in enumerate(orders):
            manager.create_task(order_id, 'M001', f'T{i+1:02d}', 1, 'mayo', False)

        # Assign first
        simulator.process_pending_tasks()
        assert manager.get_pending_count() == 2

        # Complete first delivery
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')
        simulator.handle_delivery_complete(orders[0])
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        # Assign second
        simulator.process_pending_tasks()
        assert manager.get_pending_count() == 1

        # Complete second
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table2')
        simulator.handle_delivery_complete(orders[1])
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        # Assign third
        simulator.process_pending_tasks()
        assert manager.get_pending_count() == 0

        # Complete third
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table3')
        simulator.handle_delivery_complete(orders[2])
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        # All should be completed
        assert len(manager.completed_tasks) == 3
        assert manager.get_active_count() == 0

    def test_order_complete_without_reaching_table(self):
        """Test delivery complete while robot is at table"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)

        # Assign and navigate
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')

        # Complete immediately
        simulator.handle_delivery_complete(order_id)

        # Robot should be returning
        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_RETURNING

    def test_skip_mode_disabled(self):
        """Test behavior when skip mode is disabled"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)
        simulator.skip_mode = False

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)

        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')

        # Without skip mode, food_loaded should not be called automatically
        # Robot stays in LOADED state
        robot = fleet.get_robot('pinky1')
        assert robot.status == RobotState.STATUS_LOADED

        task = manager.get_task_by_order_id(order_id)
        # Task should still be in ASSIGNED state (not started)
        assert task.status == 'ASSIGNED'


class TestStateTransitions:
    """Test all state transitions in skip mode"""

    def test_idle_to_moving_to_pickup(self):
        """Test IDLE -> MOVING_TO_PICKUP transition"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()

        assert fleet.get_robot('pinky1').status == RobotState.STATUS_MOVING_TO_PICKUP

    def test_moving_to_pickup_to_loaded(self):
        """Test MOVING_TO_PICKUP -> LOADED transition"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        # Create simulator without skip mode to test state transitions
        simulator = SkipModeSimulator(manager, fleet)
        simulator.skip_mode = False  # Disable skip mode for this test

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()

        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')

        # Without skip mode, robot stays in LOADED state
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_LOADED

    def test_loaded_to_moving_to_table(self):
        """Test LOADED -> MOVING_TO_TABLE transition (with skip mode)"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)
        simulator.skip_mode = True  # Enable skip mode for this test

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')

        # With skip mode enabled, after food_loaded is simulated, robot moves to table
        assert fleet.get_robot('pinky1').status == RobotState.STATUS_MOVING_TO_TABLE

    def test_moving_to_table_to_delivering(self):
        """Test MOVING_TO_TABLE -> DELIVERING transition"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')

        assert fleet.get_robot('pinky1').status == RobotState.STATUS_DELIVERING

    def test_delivering_to_returning(self):
        """Test DELIVERING -> RETURNING transition"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')
        simulator.handle_delivery_complete(order_id)

        assert fleet.get_robot('pinky1').status == RobotState.STATUS_RETURNING

    def test_returning_to_idle(self):
        """Test RETURNING -> IDLE transition"""
        manager = TaskManager()
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11}
        ]
        fleet = FleetController(robot_configs)
        simulator = SkipModeSimulator(manager, fleet)

        order_id = str(uuid.uuid4())
        manager.create_task(order_id, 'M001', 'T01', 1, 'mayo', False)
        simulator.process_pending_tasks()
        simulator.simulate_robot_navigation('pinky1', 'pickup_spot')
        simulator.simulate_robot_navigation('pinky1', 'table1')
        simulator.handle_delivery_complete(order_id)
        simulator.simulate_robot_navigation('pinky1', 'pinky1_spot')

        assert fleet.get_robot('pinky1').status == RobotState.STATUS_IDLE


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
