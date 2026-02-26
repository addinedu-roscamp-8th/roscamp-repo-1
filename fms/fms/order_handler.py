"""
Order Handler - Application Layer
Handles order processing workflow from GUI to robot arm and navigation
Clean Architecture: Use Case implementation

Supports order queueing when all robots are busy.
"""

import logging
from collections import deque
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from geometry_msgs.msg import Pose

logger = logging.getLogger(__name__)


class OrderWorkflow:
    """
    Domain Entity: Order workflow state machine

    Flow:
    1. RECEIVED -> 주문 접수
    2. COOKING -> 로봇팔 조리 중
    3. LOADING -> pinky1 이동 중 (point13)
    4. LOADED -> 음식 적재 완료
    5. DELIVERING -> 테이블로 이동 중
    6. ARRIVED -> 테이블 도착
    7. COMPLETED -> 수령 완료, 복귀
    """

    # Workflow states
    STATE_QUEUED = "QUEUED"       # 대기 큐에 추가됨 (가용 로봇 없음)
    STATE_RECEIVED = "RECEIVED"
    STATE_COOKING = "COOKING"
    STATE_LOADING = "LOADING"
    STATE_LOADED = "LOADED"
    STATE_DELIVERING = "DELIVERING"
    STATE_ARRIVED = "ARRIVED"
    STATE_COMPLETED = "COMPLETED"
    STATE_FAILED = "FAILED"

    def __init__(self, order_id: str, table_number: int, order_data: Dict[str, Any]):
        self.order_id = order_id
        self.table_number = table_number
        self.order_data = order_data
        self.robot_id = None
        self.state = self.STATE_RECEIVED
        self.created_at = datetime.utcnow()
        self.state_timestamps = {self.STATE_RECEIVED: self.created_at}

    def transition_to(self, new_state: str):
        """Transition to new state"""
        logger.info(f"Order {self.order_id} state: {self.state} -> {new_state}")
        self.state = new_state
        self.state_timestamps[new_state] = datetime.utcnow()

    def assign_robot(self, robot_id: str):
        """Assign robot to this order"""
        self.robot_id = robot_id
        logger.info(f"Order {self.order_id} assigned to robot {robot_id}")


class OrderHandler:
    """
    Application Layer: Order processing use case handler

    Orchestrates:
    - Order reception from GUI (TCP)
    - Robot arm cooking command (ROS2)
    - pinky1 navigation to point13 (ROS2)
    - Table delivery coordination
    - Delivery notification to GUI (TCP)
    """

    def __init__(self):
        self.active_orders: Dict[str, OrderWorkflow] = {}
        self.order_counter = 0

        # Pending order queue (FIFO) - for orders waiting for available robot
        self.pending_order_queue: deque = deque()

        # Callbacks to infrastructure layer
        self.send_cooking_command_callback: Optional[Callable] = None
        self.navigate_robot_callback: Optional[Callable] = None
        self.navigate_robot_home_callback: Optional[Callable] = None  # 로봇 home 복귀
        self.send_gui_notification_callback: Optional[Callable] = None
        self.fleet_controller_callback: Optional[Callable] = None

        # Robot availability callbacks
        self.get_available_robot_callback: Optional[Callable[[], Optional[str]]] = None
        self.assign_robot_callback: Optional[Callable[[str, str], bool]] = None

        logger.info("OrderHandler initialized")

    def register_callbacks(
        self,
        send_cooking_command: Callable,
        navigate_robot: Callable,
        send_gui_notification: Callable,
        fleet_controller: Callable
    ):
        """Register infrastructure callbacks"""
        self.send_cooking_command_callback = send_cooking_command
        self.navigate_robot_callback = navigate_robot
        self.send_gui_notification_callback = send_gui_notification
        self.fleet_controller_callback = fleet_controller
        logger.info("OrderHandler callbacks registered")

    def set_get_available_robot_callback(self, callback: Callable[[], Optional[str]]):
        """
        Set callback for checking available robot

        Args:
            callback: Function that returns available robot_id or None if none available
        """
        self.get_available_robot_callback = callback
        logger.info("Get available robot callback registered")

    def set_assign_robot_callback(self, callback: Callable[[str, str], bool]):
        """
        Set callback for assigning robot to order

        Args:
            callback: Function(robot_id, order_id) -> bool that assigns robot and returns success
        """
        self.assign_robot_callback = callback
        logger.info("Assign robot callback registered")

    def set_navigate_robot_home_callback(self, callback: Callable[[str], None]):
        """
        Set callback for navigating robot to home position

        Args:
            callback: Function(robot_id) that navigates robot to home
        """
        self.navigate_robot_home_callback = callback
        logger.info("Navigate robot home callback registered")

    def set_navigate_robot_callback(self, callback: Callable[[str, str], None]):
        """
        Set callback for navigating robot to location

        Args:
            callback: Function(robot_id, location) that navigates robot to location
        """
        self.navigate_robot_callback = callback
        logger.info("Navigate robot callback registered (via setter)")

    def set_send_cooking_command_callback(self, callback: Callable[[str, Dict], None]):
        """
        Set callback for sending cooking command

        Args:
            callback: Function(order_id, order_data) that sends cooking command
        """
        self.send_cooking_command_callback = callback
        logger.info("Send cooking command callback registered (via setter)")

    def handle_new_order(self, order_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle new order from GUI

        Args:
            order_message: {
                'table_number': 1,
                'order': {...}
            }

        Returns:
            Response dictionary with order_id and status
        """
        table_number = order_message.get('table_number')
        order_data = order_message.get('order', {})

        if not table_number or not order_data:
            raise ValueError("Invalid order message: missing table_number or order")

        # Generate order ID
        self.order_counter += 1
        order_id = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self.order_counter:04d}"

        # Create workflow
        workflow = OrderWorkflow(order_id, table_number, order_data)
        self.active_orders[order_id] = workflow

        logger.info(f"New order received: {order_id} for table {table_number}")

        # Check for available robot
        available_robot_id = None
        if self.get_available_robot_callback:
            available_robot_id = self.get_available_robot_callback()
            logger.info(f"Available robot check result: {available_robot_id}")

        # If no available robot, queue the order
        if available_robot_id is None:
            logger.info(f"No available robot, queuing order {order_id}")
            self.queue_order(workflow)
            return {
                'success': True,
                'order_id': order_id,
                'status': OrderWorkflow.STATE_QUEUED,
                'queue_position': len(self.pending_order_queue),
                'message': f'Order {order_id} queued (no available robot)'
            }

        # Execute order workflow with available robot
        try:
            # Assign robot if callback available
            if self.assign_robot_callback:
                self.assign_robot_callback(available_robot_id, order_id)

            self._execute_order_workflow(workflow, available_robot_id)

            return {
                'success': True,
                'order_id': order_id,
                'robot_id': available_robot_id,
                'status': workflow.state,
                'message': f'Order {order_id} accepted'
            }
        except Exception as e:
            logger.error(f"Failed to execute order workflow: {e}")
            workflow.transition_to(OrderWorkflow.STATE_FAILED)
            return {
                'success': False,
                'order_id': order_id,
                'message': str(e)
            }

    def _execute_order_workflow(self, workflow: OrderWorkflow, robot_id: Optional[str] = None):
        """
        Execute order workflow: cooking + navigation in parallel

        전체 워크플로우:
        1. [주문 접수] GUI에서 TCP로 주문 수신
        2. [조리 명령] 로봇팔에 /cooking/command 발행
        3. [로봇 배정] 가용 로봇 배정 (pinky1, pinky2, pinky3 중)
        4. [point13 이동] 배정 로봇을 point13으로 Nav2 이동
        5. [Skip 대기] Skip 단계 후 3초 대기 (로봇팔 없이 테스트용)
        6. [테이블 이동] table로 이동
        7. [도착 알림] table 도착 시 GUI에 delivery_notification 푸시
        8. [수령 확인] GUI에서 수령 확인 시 로봇 home으로 복귀

        Args:
            workflow: Order workflow to execute
            robot_id: Optional robot ID to assign (defaults to pinky1 for backward compatibility)
        """
        logger.info(f"=" * 60)
        logger.info(f"[WORKFLOW START] Order {workflow.order_id} for table {workflow.table_number}")
        logger.info(f"=" * 60)

        # Step 1: Send cooking command to robot arm (/cooking/command)
        if self.send_cooking_command_callback:
            cooking_command = {
                'order_id': workflow.order_id,
                'operation': 'START',
                'menu_items': workflow.order_data.get('items', []),
                'table_number': workflow.table_number
            }
            self.send_cooking_command_callback(cooking_command)
            workflow.transition_to(OrderWorkflow.STATE_COOKING)
            logger.info(f"[STEP 1] Cooking command sent to robot arm: /cooking/command")
        else:
            raise RuntimeError("Cooking command callback not registered")

        # Step 2: Assign robot to order (use provided robot_id or default to pinky1)
        assigned_robot_id = robot_id if robot_id else "pinky1"
        workflow.assign_robot(assigned_robot_id)
        logger.info(f"[STEP 2] Robot assigned: {assigned_robot_id}")

        # Step 3: Navigate robot to point13 (pickup waiting point)
        if self.navigate_robot_callback:
            self.navigate_robot_callback(assigned_robot_id, 'point13')
            workflow.transition_to(OrderWorkflow.STATE_LOADING)
            logger.info(f"[STEP 3] Navigation started: {assigned_robot_id} -> point13")
        else:
            raise RuntimeError("Navigate robot callback not registered")

    def handle_robot_arrived_point13(self, robot_id: str, order_id: str):
        """
        Handle robot arrival at point13
        Skip precision control and pickup_spot (as per requirements)
        Wait for cooking completion

        Args:
            robot_id: Robot ID (pinky1)
            order_id: Order ID
        """
        workflow = self.active_orders.get(order_id)
        if not workflow:
            logger.warning(f"Order {order_id} not found for robot arrival")
            return

        logger.info(f"Robot {robot_id} arrived at point13, waiting for cooking completion")
        # State remains LOADING until food is loaded

    def handle_cooking_complete(self, order_id: str):
        """
        Handle cooking completion from robot arm

        Args:
            order_id: Order ID
        """
        workflow = self.active_orders.get(order_id)
        if not workflow:
            logger.warning(f"Order {order_id} not found for cooking completion")
            return

        logger.info(f"Cooking completed for order {order_id}")

        # Check if robot is at point13
        if workflow.state == OrderWorkflow.STATE_LOADING:
            # Food is ready, robot is at point13
            # Skip precision control as per requirements (3초 딜레이 후 자동 이동)
            self._trigger_food_loading(workflow)

    def _trigger_food_loading(self, workflow: OrderWorkflow):
        """
        Trigger food loading (skip precision control as per requirements)
        After 3 seconds, automatically proceed to table delivery

        Skip 단계 후 3초 대기 -> table로 이동

        Args:
            workflow: Order workflow
        """
        workflow.transition_to(OrderWorkflow.STATE_LOADED)
        logger.info(f"Food loaded for order {workflow.order_id}")
        logger.info(f"[SKIP MODE] Waiting 3 seconds before proceeding to table...")

        # Navigate to table after 3 seconds (skip mode behavior)
        import threading

        def delayed_table_navigation():
            import time
            time.sleep(3.0)  # Skip 단계 후 3초 대기
            logger.info(f"[SKIP MODE] 3 seconds elapsed, navigating to table{workflow.table_number}")
            self._navigate_to_table(workflow)

        # Start delayed navigation in separate thread
        timer_thread = threading.Thread(target=delayed_table_navigation, daemon=True)
        timer_thread.start()

    def _navigate_to_table(self, workflow: OrderWorkflow):
        """
        Navigate robot to table

        Args:
            workflow: Order workflow
        """
        table_name = f"table{workflow.table_number}"

        if self.navigate_robot_callback:
            self.navigate_robot_callback(workflow.robot_id, table_name)
            workflow.transition_to(OrderWorkflow.STATE_DELIVERING)
            logger.info(f"[STEP 5] Navigation started: {workflow.robot_id} -> {table_name}")
        else:
            logger.error("Navigate robot callback not registered")

    def handle_robot_arrived_table(self, robot_id: str, order_id: str):
        """
        Handle robot arrival at table
        table 도착 시 GUI에 delivery_notification 푸시

        Args:
            robot_id: Robot ID
            order_id: Order ID
        """
        workflow = self.active_orders.get(order_id)
        if not workflow:
            logger.warning(f"Order {order_id} not found for table arrival")
            return

        workflow.transition_to(OrderWorkflow.STATE_ARRIVED)
        logger.info(f"[STEP 6] Robot {robot_id} arrived at table{workflow.table_number}")

        # Send push notification to GUI (delivery_notification)
        if self.send_gui_notification_callback:
            notification = {
                'type': 'delivery_notification',
                'data': {
                    'order_id': order_id,
                    'table_number': workflow.table_number,
                    'robot_id': robot_id,
                    'status': 'arrived',
                    'message': f'주문이 테이블 {workflow.table_number}에 도착했습니다.'
                }
            }
            self.send_gui_notification_callback(notification)
            logger.info(f"[STEP 6] Sent delivery_notification to GUI: order={order_id}, table={workflow.table_number}")
        else:
            logger.error("GUI notification callback not registered")

    def handle_delivery_confirmation(self, order_id: str, table_number: int):
        """
        Handle delivery confirmation from GUI (customer received order)
        수령 확인 시:
        - 대기 주문이 있으면 바로 다음 주문 처리 (home 복귀 없이)
        - 대기 주문이 없으면 home으로 복귀

        Args:
            order_id: Order ID
            table_number: Table number
        """
        workflow = self.active_orders.get(order_id)

        # Fallback: If order_id not found, try to find by table_number
        # This handles cases where GUI uses a different order_id format
        if not workflow:
            logger.warning(f"Order {order_id} not found, trying to find by table {table_number}")
            for oid, wf in self.active_orders.items():
                # Convert table_number to int for comparison
                try:
                    tbl = int(table_number) if isinstance(table_number, str) else table_number
                except (ValueError, TypeError):
                    tbl = None

                if wf.table_number == tbl and wf.state == OrderWorkflow.STATE_ARRIVED:
                    workflow = wf
                    logger.info(f"Found matching order {oid} by table_number {table_number}")
                    break

        if not workflow:
            logger.warning(f"Order {order_id} not found for delivery confirmation")
            return

        # 현재 주문 완료 처리
        workflow.transition_to(OrderWorkflow.STATE_COMPLETED)
        logger.info(f"[STEP 7] Delivery confirmed for order {workflow.order_id}")

        # 로봇 해제
        robot_id = workflow.robot_id

        # Update fleet controller to mark robot as completing delivery
        if self.fleet_controller_callback:
            self.fleet_controller_callback(robot_id, 'complete_delivery')

        logger.info(f"=" * 60)
        logger.info(f"[WORKFLOW COMPLETE] Order {workflow.order_id} delivered successfully")
        logger.info(f"=" * 60)

        # 대기 주문 확인 및 자동 디스패치
        if self.pending_order_queue:
            next_workflow = self.pending_order_queue.popleft()
            if next_workflow:
                logger.info(f"[AUTO-DISPATCH] Found pending order {next_workflow.order_id}, dispatching to {robot_id}")
                # Update remaining queue positions and notify GUI
                self._notify_queue_position_updates()
                # 바로 다음 주문 처리 (home 복귀 없이)
                self._dispatch_order_to_robot(next_workflow, robot_id)
                return

        # 대기 주문 없으면 home 복귀
        logger.info(f"[NO PENDING ORDERS] Robot {robot_id} returning to home")
        if self.navigate_robot_home_callback:
            self.navigate_robot_home_callback(robot_id)
            logger.info(f"[STEP 8] Robot {robot_id} returning to home via home callback")
        elif self.navigate_robot_callback:
            # Fallback: use navigate_robot_callback with home location
            home_location = f"{robot_id}_spot"
            self.navigate_robot_callback(robot_id, home_location)
            logger.info(f"[STEP 8] Robot {robot_id} returning to home: {home_location}")
        else:
            logger.error("Navigate robot callback not registered")

    def _dispatch_order_to_robot(self, workflow: OrderWorkflow, robot_id: str):
        """
        Dispatch order to a specific robot (auto-dispatch after delivery completion)

        Args:
            workflow: OrderWorkflow to dispatch
            robot_id: Robot ID to assign
        """
        logger.info(f"=" * 60)
        logger.info(f"[AUTO-DISPATCH START] Order {workflow.order_id} for table {workflow.table_number}")
        logger.info(f"=" * 60)

        # Assign robot to order
        workflow.assign_robot(robot_id)

        # Assign robot through callback if available
        if self.assign_robot_callback:
            self.assign_robot_callback(robot_id, workflow.order_id)

        # Transition to COOKING state
        workflow.transition_to(OrderWorkflow.STATE_COOKING)

        # Send cooking command to robot arm
        if self.send_cooking_command_callback:
            cooking_command = {
                'order_id': workflow.order_id,
                'operation': 'START',
                'menu_items': workflow.order_data.get('items', []),
                'table_number': workflow.table_number
            }
            self.send_cooking_command_callback(cooking_command)
            logger.info(f"[AUTO-DISPATCH STEP 1] Cooking command sent for order {workflow.order_id}")
        else:
            logger.error("Cooking command callback not registered")

        # Navigate robot to pickup point (point13)
        if self.navigate_robot_callback:
            self.navigate_robot_callback(robot_id, 'point13')
            workflow.transition_to(OrderWorkflow.STATE_LOADING)
            logger.info(f"[AUTO-DISPATCH STEP 2] Robot {robot_id} navigating to point13")
        else:
            logger.error("Navigate robot callback not registered")

        # Notify GUI that queued order is now processing
        if self.send_gui_notification_callback:
            notification = {
                'type': 'order_processing',
                'data': {
                    'order_id': workflow.order_id,
                    'table_number': workflow.table_number,
                    'robot_id': robot_id,
                    'status': workflow.state,
                    'message': f'대기 중이던 주문이 처리를 시작합니다. 로봇: {robot_id}'
                }
            }
            self.send_gui_notification_callback(notification)

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status

        Args:
            order_id: Order ID

        Returns:
            Order status dictionary
        """
        workflow = self.active_orders.get(order_id)
        if not workflow:
            return None

        return {
            'order_id': workflow.order_id,
            'table_number': workflow.table_number,
            'robot_id': workflow.robot_id,
            'state': workflow.state,
            'created_at': workflow.created_at.isoformat(),
            'state_timestamps': {
                k: v.isoformat() for k, v in workflow.state_timestamps.items()
            }
        }

    def get_all_active_orders(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active orders

        Returns:
            Dictionary of order statuses
        """
        return {
            order_id: self.get_order_status(order_id)
            for order_id in self.active_orders.keys()
        }

    # =========================================================================
    # Queue Management Methods
    # =========================================================================

    def queue_order(self, workflow: OrderWorkflow) -> bool:
        """
        Add order to pending queue when no robot is available

        Args:
            workflow: OrderWorkflow to queue

        Returns:
            True if successfully queued
        """
        workflow.transition_to(OrderWorkflow.STATE_QUEUED)
        self.pending_order_queue.append(workflow)

        queue_position = len(self.pending_order_queue)
        logger.info(f"Order {workflow.order_id} queued at position {queue_position}")

        # Send notification to GUI about queued order
        if self.send_gui_notification_callback:
            notification = {
                'type': 'order_queued',
                'data': {
                    'order_id': workflow.order_id,
                    'table_number': workflow.table_number,
                    'queue_position': queue_position,
                    'status': OrderWorkflow.STATE_QUEUED,
                    'message': f'주문이 대기열에 추가되었습니다. 현재 {queue_position}번째 대기 중입니다.'
                }
            }
            self.send_gui_notification_callback(notification)
            logger.info(f"Sent order_queued notification to GUI: order={workflow.order_id}")

        return True

    def get_next_queued_order(self) -> Optional[OrderWorkflow]:
        """
        Get next order from pending queue (FIFO)

        Returns:
            Next OrderWorkflow or None if queue is empty
        """
        if not self.pending_order_queue:
            return None

        return self.pending_order_queue[0]

    def process_queued_order(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """
        Process next queued order when a robot becomes available

        Called when a robot completes delivery and returns to home.
        Takes the next order from the queue and assigns it to the available robot.

        Args:
            robot_id: Available robot ID (e.g., 'pinky1', 'pinky2', 'pinky3')

        Returns:
            Dictionary with processing result or None if no queued orders
        """
        if not self.pending_order_queue:
            logger.info(f"No queued orders to process for robot {robot_id}")
            return None

        # Pop next order from queue (FIFO)
        workflow = self.pending_order_queue.popleft()
        logger.info(f"Processing queued order {workflow.order_id} with robot {robot_id}")

        # Update remaining queue positions and notify GUI
        self._notify_queue_position_updates()

        try:
            # Assign robot through callback if available
            if self.assign_robot_callback:
                self.assign_robot_callback(robot_id, workflow.order_id)

            # Execute the order workflow with the available robot
            self._execute_order_workflow(workflow, robot_id)

            # Notify GUI that queued order is now processing
            if self.send_gui_notification_callback:
                notification = {
                    'type': 'order_processing',
                    'data': {
                        'order_id': workflow.order_id,
                        'table_number': workflow.table_number,
                        'robot_id': robot_id,
                        'status': workflow.state,
                        'message': f'대기 중이던 주문이 처리를 시작합니다. 로봇: {robot_id}'
                    }
                }
                self.send_gui_notification_callback(notification)

            return {
                'success': True,
                'order_id': workflow.order_id,
                'robot_id': robot_id,
                'status': workflow.state,
                'message': f'Queued order {workflow.order_id} now processing'
            }

        except Exception as e:
            logger.error(f"Failed to process queued order {workflow.order_id}: {e}")
            workflow.transition_to(OrderWorkflow.STATE_FAILED)
            return {
                'success': False,
                'order_id': workflow.order_id,
                'message': str(e)
            }

    def _notify_queue_position_updates(self):
        """
        Notify GUI about updated queue positions after an order is dequeued
        """
        if not self.send_gui_notification_callback:
            return

        for position, workflow in enumerate(self.pending_order_queue, start=1):
            notification = {
                'type': 'queue_position_updated',
                'data': {
                    'order_id': workflow.order_id,
                    'table_number': workflow.table_number,
                    'queue_position': position,
                    'message': f'대기 순서가 {position}번으로 변경되었습니다.'
                }
            }
            self.send_gui_notification_callback(notification)

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status for GUI display

        Returns:
            Dictionary containing queue information:
            - queue_length: Number of orders in queue
            - orders: List of queued orders with their positions
        """
        queued_orders = []
        for position, workflow in enumerate(self.pending_order_queue, start=1):
            queued_orders.append({
                'order_id': workflow.order_id,
                'table_number': workflow.table_number,
                'queue_position': position,
                'created_at': workflow.created_at.isoformat(),
                'state': workflow.state,
                'items': workflow.order_data.get('items', [])
            })

        return {
            'queue_length': len(self.pending_order_queue),
            'orders': queued_orders
        }

    def get_queued_order_count(self) -> int:
        """
        Get number of orders currently in queue

        Returns:
            Number of queued orders
        """
        return len(self.pending_order_queue)

    def remove_queued_order(self, order_id: str) -> bool:
        """
        Remove a specific order from the queue (e.g., for cancellation)

        Args:
            order_id: Order ID to remove

        Returns:
            True if order was found and removed, False otherwise
        """
        for i, workflow in enumerate(self.pending_order_queue):
            if workflow.order_id == order_id:
                del self.pending_order_queue[i]
                logger.info(f"Order {order_id} removed from queue")

                # Update queue positions
                self._notify_queue_position_updates()

                # Remove from active orders
                if order_id in self.active_orders:
                    del self.active_orders[order_id]

                return True

        return False
