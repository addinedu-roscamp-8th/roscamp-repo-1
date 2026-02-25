"""
Example: How to integrate TaskScheduler into FMS Node

This file demonstrates the recommended patterns for using TaskScheduler
in the FMS Node for multi-robot coordination.
"""

import logging
from typing import Optional
from .task_scheduler import TaskScheduler, TaskState
from .task_manager import Task
from .zone_manager import ZoneManager

logger = logging.getLogger(__name__)


class FMSNodeWithScheduler:
    """
    Example FMS integration using TaskScheduler

    This shows the key methods and workflow for integrating
    the task scheduler into the main FMS node.
    """

    def __init__(self):
        # Initialize zone and task managers
        self.zone_manager = ZoneManager()
        self.task_scheduler = TaskScheduler(self.zone_manager)

    def handle_new_order(self, order_id: str, table_number: str, menu_id: str,
                        quantity: int, sauce_type: str) -> bool:
        """
        Handle new order from GUI

        Flow:
        1. Create task from order
        2. Add to scheduler queue
        3. Try to assign to available robot

        Args:
            order_id: Order UUID
            table_number: Target table
            menu_id: Menu item
            quantity: Item quantity
            sauce_type: Sauce type

        Returns:
            True if order queued successfully
        """
        # Create task from order
        task = Task(
            order_id=order_id,
            menu_id=menu_id,
            table_number=table_number,
            quantity=quantity,
            sauce_type=sauce_type,
            voice_order=False
        )

        # Add to scheduler
        task_id = self.task_scheduler.add_task(task)
        logger.info(f"Order {order_id} queued as task {task_id}")

        return True

    def assign_tasks_to_available_robots(self, available_robots: list) -> dict:
        """
        Assign pending tasks to available robots

        Called periodically (e.g., 2 Hz) to match robots with tasks.

        Args:
            available_robots: List of robot IDs that are IDLE

        Returns:
            Dictionary of assignments: {robot_id: Task}
        """
        assignments = {}

        for robot_id in available_robots:
            task = self.task_scheduler.assign_task_to_robot(robot_id)
            if task:
                assignments[robot_id] = task
                logger.info(f"Assigned task {task.task_id} to robot {robot_id}")

        return assignments

    def robot_ready_for_pickup(self, robot_id: str, task_id: str) -> bool:
        """
        Robot reached pickup_spot and is ready to load

        Flow:
        1. Request pickup slot
        2. If granted: start loading (skip mode auto-loads after 3s)
        3. If waiting: move to waiting zone (point13)

        Args:
            robot_id: Robot ID
            task_id: Task ID

        Returns:
            True if request accepted
        """
        task = self.task_scheduler.assigned_tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return False

        # Request pickup access
        is_granted = self.task_scheduler.request_pickup_access(robot_id, task_id)

        if is_granted:
            # Robot can start loading immediately
            logger.info(f"Task {task_id}: Robot {robot_id} can start loading")
            # FMS will publish goal_arrived message (in skip mode, auto-trigger food_loaded after 3s)
            return True
        else:
            # Robot must wait
            waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
            logger.info(f"Task {task_id}: Robot {robot_id} must wait at {waiting_zone}")
            # Send command to move to waiting zone (point13)
            # Then periodically check if pickup slot becomes available
            return True

    def check_pickup_queue_and_advance(self):
        """
        Periodically check if next robot in queue can enter pickup spot

        Called frequently (10 Hz) to advance queue.

        Should be called:
        - After each robot releases pickup slot
        - Periodically to check timeouts
        - After zone becomes available
        """
        queue_status = self.task_scheduler.get_pickup_queue_status()

        # Check if current holder exceeded timeout
        if self.task_scheduler.pickup_manager.check_slot_timeout():
            logger.warning("Pickup slot timeout detected, forcing release")
            next_robot = self.task_scheduler.pickup_manager.force_release_slot()
            if next_robot:
                logger.info(f"Forcing release, {next_robot} now has pickup access")

        # Log queue status if there are waiting robots
        if queue_status['queue_length'] > 0:
            logger.debug(f"Pickup queue status: {queue_status}")

    def robot_loaded_with_food(self, robot_id: str, task_id: str, table_number: str) -> bool:
        """
        Robot has food loaded and is ready for delivery

        Flow:
        1. Release pickup slot
        2. Notify next robot in queue
        3. Update task state
        4. Send robot to table

        Args:
            robot_id: Robot ID
            task_id: Task ID
            table_number: Target table

        Returns:
            True if successful
        """
        # Update scheduler
        success = self.task_scheduler.robot_loaded(robot_id, task_id)

        if success:
            # After releasing pickup, the next robot in queue will automatically
            # have access. In the next check_pickup_queue_and_advance() call,
            # it will be notified to move to pickup_spot.
            logger.info(f"Task {task_id}: Robot {robot_id} loaded with food, heading to table {table_number}")

            # Check if queue can advance
            self.check_pickup_queue_and_advance()

        return success

    def delivery_complete(self, robot_id: str, task_id: str) -> bool:
        """
        Delivery completed, robot ready to return to parking

        Args:
            robot_id: Robot ID
            task_id: Task ID

        Returns:
            True if successful
        """
        success = self.task_scheduler.robot_delivered(robot_id, task_id)

        if success:
            logger.info(f"Task {task_id}: Robot {robot_id} delivery complete")
            # Robot is now available for next task
            # Next call to assign_tasks_to_available_robots() will assign it

        return success

    def handle_robot_malfunction(self, robot_id: str, error_msg: str):
        """
        Handle robot error or malfunction

        Cleanup:
        1. Release pickup slot if holding
        2. Remove from queue if waiting
        3. Fail current task and return to queue
        4. Next robot in queue gets pickup access

        Args:
            robot_id: Robot ID
            error_msg: Error description
        """
        self.task_scheduler.handle_robot_error(robot_id, error_msg)

        # Check if queue can advance
        self.check_pickup_queue_and_advance()

        # Optionally: notify operators
        logger.error(f"Robot {robot_id} malfunction: {error_msg}. Task requeued.")

    def get_fleet_status(self) -> dict:
        """Get current fleet and scheduler status"""
        return {
            'scheduler_status': self.task_scheduler.get_scheduler_status(),
            'task_summary': self.task_scheduler.get_task_summary(),
            'pickup_queue': self.task_scheduler.get_pickup_queue_status()
        }

    def print_scheduler_status(self):
        """Print scheduler status for debugging"""
        status = self.get_fleet_status()
        logger.info("=== SCHEDULER STATUS ===")
        logger.info(f"Pending tasks: {status['scheduler_status']['pending_tasks']}")
        logger.info(f"Active tasks: {status['scheduler_status']['active_tasks']}")
        logger.info(f"Completed tasks: {status['scheduler_status']['completed_tasks']}")
        logger.info(f"Robots waiting for pickup: {status['scheduler_status']['robots_waiting_for_pickup']}")
        logger.info(f"Task summary: {status['task_summary']}")
        logger.info(f"Pickup queue: {status['pickup_queue']}")


# ============================================================================
# WORKFLOW EXAMPLE: 3 orders arrive simultaneously
# ============================================================================

def workflow_example():
    """
    Example: 3 orders arrive at same time (pinky1, pinky2, pinky3 all IDLE)

    Timeline:
    T0: Orders arrive
    T1: Robots assigned tasks
    T2: pinky1 reaches pickup -> granted access
    T3: pinky2 reaches pickup -> queued (pinky1 holding slot)
    T4: pinky3 reaches pickup -> queued
    T5: pinky1 finishes loading -> releases slot -> pinky2 gets access
    T6: pinky2 finishes loading -> releases slot -> pinky3 gets access
    T7+: All robots delivering to tables
    """

    fms = FMSNodeWithScheduler()

    print("\n=== WORKFLOW: 3 Simultaneous Orders ===\n")

    # T0: 3 orders arrive simultaneously
    print("T0: 3 orders arrive")
    fms.handle_new_order("order1", "table1", "M001", 1, "spicy")
    fms.handle_new_order("order2", "table2", "M002", 1, "mild")
    fms.handle_new_order("order3", "table3", "M001", 2, "spicy")
    print(f"Queue size: {fms.task_scheduler.get_pending_count()}\n")

    # T1: Assign tasks to available robots
    print("T1: Assign tasks to 3 available robots")
    assignments = fms.assign_tasks_to_available_robots(['pinky1', 'pinky2', 'pinky3'])
    print(f"Assignments: {len(assignments)}")
    print(f"Pending: {fms.task_scheduler.get_pending_count()}")
    print(f"Active: {fms.task_scheduler.get_active_count()}\n")

    # T2: pinky1 reaches pickup
    print("T2: pinky1 reaches pickup_spot")
    task1_id = assignments['pinky1'].task_id
    fms.robot_ready_for_pickup('pinky1', task1_id)
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting\n")

    # T3: pinky2 reaches pickup (must wait)
    print("T3: pinky2 reaches pickup_spot")
    task2_id = assignments['pinky2'].task_id
    fms.robot_ready_for_pickup('pinky2', task2_id)
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting")
    print(f"pinky2 waiting zone: {fms.task_scheduler.get_next_waiting_zone('pinky2')}\n")

    # T4: pinky3 reaches pickup (must wait)
    print("T4: pinky3 reaches pickup_spot")
    task3_id = assignments['pinky3'].task_id
    fms.robot_ready_for_pickup('pinky3', task3_id)
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting")
    print(f"pinky3 waiting zone: {fms.task_scheduler.get_next_waiting_zone('pinky3')}\n")

    # T5: pinky1 finishes loading
    print("T5: pinky1 finishes loading")
    fms.robot_loaded_with_food('pinky1', task1_id, 'table1')
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting")
    print(f"Next robot: {fms.task_scheduler.pickup_manager.get_next_in_queue()}\n")

    # T6: pinky2 finishes loading
    print("T6: pinky2 finishes loading")
    fms.robot_loaded_with_food('pinky2', task2_id, 'table2')
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting")
    print(f"Next robot: {fms.task_scheduler.pickup_manager.get_next_in_queue()}\n")

    # T7: pinky3 finishes loading
    print("T7: pinky3 finishes loading")
    fms.robot_loaded_with_food('pinky3', task3_id, 'table3')
    print(f"Pickup queue: {fms.task_scheduler.get_pickup_queue_status()['queue_length']} waiting\n")

    # Final status
    print("=== FINAL STATUS ===")
    fms.print_scheduler_status()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    workflow_example()
