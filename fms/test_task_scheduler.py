#!/usr/bin/env python3
"""
Standalone test script for TaskScheduler

Tests multi-robot task scheduling without ROS 2 dependencies.
"""

import sys
import logging
from pathlib import Path

# Add fms to path
fms_path = Path(__file__).parent / 'fms'
sys.path.insert(0, str(fms_path))

# Import directly to avoid __init__.py dependencies
import importlib.util

# Load task_scheduler
spec = importlib.util.spec_from_file_location("task_scheduler", fms_path / "task_scheduler.py")
task_scheduler_module = importlib.util.module_from_spec(spec)

# Load task_manager
spec_tm = importlib.util.spec_from_file_location("task_manager", fms_path / "task_manager.py")
task_manager_module = importlib.util.module_from_spec(spec_tm)

# Load zone_manager
spec_zm = importlib.util.spec_from_file_location("zone_manager", fms_path / "zone_manager.py")
zone_manager_module = importlib.util.module_from_spec(spec_zm)

# Execute modules
spec_tm.loader.exec_module(task_manager_module)
spec_zm.loader.exec_module(zone_manager_module)
spec.loader.exec_module(task_scheduler_module)

# Extract classes
TaskScheduler = task_scheduler_module.TaskScheduler
TaskState = task_scheduler_module.TaskState
PickupSlotManager = task_scheduler_module.PickupSlotManager
Task = task_manager_module.Task
ZoneManager = zone_manager_module.ZoneManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_operations():
    """Test basic scheduler operations"""
    print("\n" + "="*70)
    print("TEST 1: Basic Operations")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Create tasks
    task1 = Task('order1', 'M001', 'table1', 1, 'spicy', False)
    task2 = Task('order2', 'M002', 'table2', 1, 'mild', False)
    task3 = Task('order3', 'M001', 'table3', 2, 'spicy', False)

    # Add tasks
    print("\n1. Adding 3 tasks to queue...")
    id1 = scheduler.add_task(task1)
    id2 = scheduler.add_task(task2)
    id3 = scheduler.add_task(task3)
    print(f"   Pending: {scheduler.get_pending_count()}")
    print(f"   Active: {scheduler.get_active_count()}")

    # Assign tasks
    print("\n2. Assigning tasks to robots...")
    t1 = scheduler.assign_task_to_robot('pinky1')
    t2 = scheduler.assign_task_to_robot('pinky2')
    t3 = scheduler.assign_task_to_robot('pinky3')
    print(f"   Pending: {scheduler.get_pending_count()}")
    print(f"   Active: {scheduler.get_active_count()}")
    print(f"   Task 1 → pinky1: {t1.task_id[:8]}...")
    print(f"   Task 2 → pinky2: {t2.task_id[:8]}...")
    print(f"   Task 3 → pinky3: {t3.task_id[:8]}...")

    # Get task states
    print("\n3. Task states after assignment:")
    print(f"   Task 1 state: {scheduler.get_task_state(id1).value}")
    print(f"   Task 2 state: {scheduler.get_task_state(id2).value}")
    print(f"   Task 3 state: {scheduler.get_task_state(id3).value}")

    return scheduler, (id1, id2, id3)


def test_pickup_queue_single_robot():
    """Test pickup queue with single robot"""
    print("\n" + "="*70)
    print("TEST 2: Pickup Queue - Single Robot")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Create and assign task
    task = Task('order1', 'M001', 'table1', 1, 'spicy', False)
    task_id = scheduler.add_task(task)
    scheduler.assign_task_to_robot('pinky1')

    print("\n1. Robot pinky1 requests pickup access...")
    is_granted = scheduler.request_pickup_access('pinky1', task_id)
    print(f"   Access granted: {is_granted}")
    print(f"   Task state: {scheduler.get_task_state(task_id).value}")
    print(f"   Queue status: {scheduler.get_pickup_queue_status()}")

    print("\n2. Robot pinky1 finishes loading...")
    scheduler.robot_loaded('pinky1', task_id)
    print(f"   Task state: {scheduler.get_task_state(task_id).value}")
    print(f"   Pickup queue: {scheduler.get_pickup_queue_status()}")

    print("\n3. Robot pinky1 completes delivery...")
    scheduler.robot_delivered('pinky1', task_id)
    print(f"   Task state: {scheduler.get_task_state(task_id).value}")
    print(f"   Completed tasks: {len(scheduler.completed_tasks)}")


def test_pickup_queue_multiple_robots():
    """Test pickup queue with 3 robots waiting"""
    print("\n" + "="*70)
    print("TEST 3: Pickup Queue - Multiple Robots (3 simultaneous orders)")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Create and assign 3 tasks
    print("\n[T0] Creating 3 orders and assigning to robots...")
    tasks = []
    task_ids = []
    for i, robot_id in enumerate(['pinky1', 'pinky2', 'pinky3'], 1):
        task = Task(f'order{i}', f'M{i:03d}', f'table{i}', 1, 'spicy', False)
        task_id = scheduler.add_task(task)
        scheduler.assign_task_to_robot(robot_id)
        tasks.append((robot_id, task))
        task_ids.append(task_id)
        print(f"   {robot_id} ← order{i}")

    # Robot 1 reaches pickup
    print("\n[T1] pinky1 reaches pickup_spot...")
    granted1 = scheduler.request_pickup_access('pinky1', task_ids[0])
    print(f"   pinky1 access granted: {granted1}")
    print(f"   Queue: {scheduler.get_pickup_queue_status()['waiting_robots']}")

    # Robot 2 reaches pickup
    print("\n[T2] pinky2 reaches pickup_spot...")
    granted2 = scheduler.request_pickup_access('pinky2', task_ids[1])
    print(f"   pinky2 access granted: {granted2}")
    print(f"   pinky2 waiting zone: {scheduler.get_next_waiting_zone('pinky2')}")
    queue = scheduler.get_pickup_queue_status()
    print(f"   Queue: {queue['waiting_robots']}")
    print(f"   Positions: {queue['queue_positions']}")

    # Robot 3 reaches pickup
    print("\n[T3] pinky3 reaches pickup_spot...")
    granted3 = scheduler.request_pickup_access('pinky3', task_ids[2])
    print(f"   pinky3 access granted: {granted3}")
    print(f"   pinky3 waiting zone: {scheduler.get_next_waiting_zone('pinky3')}")
    queue = scheduler.get_pickup_queue_status()
    print(f"   Queue: {queue['waiting_robots']}")
    print(f"   Positions: {queue['queue_positions']}")

    # Robot 1 finishes loading
    print("\n[T4] pinky1 finishes loading, releases slot...")
    scheduler.robot_loaded('pinky1', task_ids[0])
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")
    print(f"   Next in queue: {scheduler.pickup_manager.get_next_in_queue()}")
    print(f"   Queue: {queue['waiting_robots']}")

    # Robot 2 finishes loading
    print("\n[T5] pinky2 finishes loading, releases slot...")
    scheduler.robot_loaded('pinky2', task_ids[1])
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")
    print(f"   Next in queue: {scheduler.pickup_manager.get_next_in_queue()}")
    print(f"   Queue: {queue['waiting_robots']}")

    # Robot 3 finishes loading
    print("\n[T6] pinky3 finishes loading, releases slot...")
    scheduler.robot_loaded('pinky3', task_ids[2])
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")
    print(f"   Queue: {queue['waiting_robots']}")

    # Summary
    print("\n=== SUMMARY ===")
    summary = scheduler.get_task_summary()
    for state, count in summary.items():
        if count > 0:
            print(f"   {state}: {count}")


def test_error_handling():
    """Test error handling and recovery"""
    print("\n" + "="*70)
    print("TEST 4: Error Handling")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Create 3 tasks
    print("\n1. Creating 3 tasks...")
    task_ids = []
    for i, robot_id in enumerate(['pinky1', 'pinky2', 'pinky3'], 1):
        task = Task(f'order{i}', f'M{i:03d}', f'table{i}', 1, 'spicy', False)
        task_id = scheduler.add_task(task)
        scheduler.assign_task_to_robot(robot_id)
        task_ids.append(task_id)

    # pinky1 gets pickup access
    print("\n2. pinky1 gets pickup access...")
    scheduler.request_pickup_access('pinky1', task_ids[0])
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")

    # pinky2 and pinky3 queue up
    print("\n3. pinky2 and pinky3 queue up...")
    scheduler.request_pickup_access('pinky2', task_ids[1])
    scheduler.request_pickup_access('pinky3', task_ids[2])
    queue = scheduler.get_pickup_queue_status()
    print(f"   Queue: {queue['waiting_robots']}")

    # pinky1 encounters error
    print("\n4. pinky1 encounters error (forcing release)...")
    scheduler.handle_robot_error('pinky1', "Navigation failed")
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")
    print(f"   Queue: {queue['waiting_robots']}")
    print(f"   pinky1 task state: {scheduler.get_task_state(task_ids[0]).value}")

    print("\n5. Task summary after error:")
    summary = scheduler.get_task_summary()
    for state, count in summary.items():
        if count > 0:
            print(f"   {state}: {count}")

    print("\n6. Task was requeued for retry:")
    print(f"   Pending tasks: {scheduler.get_pending_count()}")


def test_timeout():
    """Test pickup slot timeout"""
    print("\n" + "="*70)
    print("TEST 5: Pickup Slot Timeout")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Set short timeout for testing
    scheduler.pickup_manager.holding_timeout = 0.5

    # Create task
    print("\n1. Creating task and assigning to pinky1...")
    task = Task('order1', 'M001', 'table1', 1, 'spicy', False)
    task_id = scheduler.add_task(task)
    scheduler.assign_task_to_robot('pinky1')

    # Request pickup
    print("\n2. pinky1 requests and gets pickup access...")
    scheduler.request_pickup_access('pinky1', task_id)
    print(f"   Current holder: {scheduler.pickup_manager.current_holder}")
    print(f"   Timeout: {scheduler.pickup_manager.holding_timeout}s")

    # Check timeout immediately
    import time
    print("\n3. Check timeout immediately (should be False)...")
    has_timeout = scheduler.pickup_manager.check_slot_timeout()
    print(f"   Has timeout: {has_timeout}")

    # Wait and check again
    print("\n4. Wait 1 second and check timeout (should be True)...")
    time.sleep(1.0)
    has_timeout = scheduler.pickup_manager.check_slot_timeout()
    print(f"   Has timeout: {has_timeout}")

    # Force release
    print("\n5. Force release due to timeout...")
    next_robot = scheduler.pickup_manager.force_release_slot()
    print(f"   Current holder: {scheduler.pickup_manager.current_holder}")
    print(f"   Next robot: {next_robot}")


def test_status_reporting():
    """Test status reporting and monitoring"""
    print("\n" + "="*70)
    print("TEST 6: Status Reporting")
    print("="*70)

    zone_mgr = ZoneManager()
    scheduler = TaskScheduler(zone_mgr)

    # Create mixed state tasks
    print("\n1. Creating tasks in various states...")
    task_ids = []

    # Pending
    for i in range(2):
        task = Task(f'pending{i+1}', 'M001', 'table1', 1, 'spicy', False)
        task_id = scheduler.add_task(task)
        task_ids.append(task_id)

    # Assigned
    for i in range(2):
        task = Task(f'assigned{i+1}', 'M002', 'table2', 1, 'mild', False)
        task_id = scheduler.add_task(task)
        scheduler.assign_task_to_robot(f'pinky{i+1}')
        task_ids.append(task_id)

    # At pickup
    task = Task('at_pickup', 'M003', 'table3', 1, 'spicy', False)
    task_id = scheduler.add_task(task)
    scheduler.assign_task_to_robot('pinky3')
    scheduler.request_pickup_access('pinky3', task_id)
    task_ids.append(task_id)

    print(f"   Created {len(task_ids)} tasks in various states")

    # Get summary
    print("\n2. Task summary:")
    summary = scheduler.get_task_summary()
    for state, count in summary.items():
        if count > 0:
            print(f"   {state}: {count}")

    # Get full scheduler status
    print("\n3. Full scheduler status:")
    status = scheduler.get_scheduler_status()
    print(f"   Pending: {status['pending_tasks']}")
    print(f"   Active: {status['active_tasks']}")
    print(f"   Completed: {status['completed_tasks']}")
    print(f"   Waiting for pickup: {status['robots_waiting_for_pickup']}")

    # Get queue status
    print("\n4. Pickup queue status:")
    queue = scheduler.get_pickup_queue_status()
    print(f"   Current holder: {queue['current_holder']}")
    print(f"   Queue length: {queue['queue_length']}")
    print(f"   Waiting robots: {queue['waiting_robots']}")

    # Get robot task mapping
    print("\n5. Robot task mapping:")
    for robot_id, task_info in status['robot_task_mapping'].items():
        print(f"   {robot_id}:")
        print(f"      Task: {task_info['current_task'][:8]}...")
        print(f"      State: {task_info['state']}")


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("TASK SCHEDULER COMPREHENSIVE TESTS")
    print("="*70)

    try:
        test_basic_operations()
        test_pickup_queue_single_robot()
        test_pickup_queue_multiple_robots()
        test_error_handling()
        test_timeout()
        test_status_reporting()

        print("\n" + "="*70)
        print("ALL TESTS PASSED")
        print("="*70 + "\n")
        return 0

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
