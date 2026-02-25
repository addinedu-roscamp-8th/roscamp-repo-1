"""
Fleet Management System (FMS) Node
Integrates TaskManager, FleetController, and ZoneManager
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped, Pose, PoseWithCovarianceStamped
from fleet_interfaces.msg import (
    OrderRequest,
    RobotStatus,
    FleetStatus,
    DeliveryComplete,
    PickupArrival,
    PrecisionParked,
    CookingOrder,
    LoadingComplete,
    TableArrival,
    ErrorAlert,
    OperatorCommand as OperatorCommandMsg
)
from std_msgs.msg import Float32, Bool
from builtin_interfaces.msg import Time
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional

from .task_manager import TaskManager, Task
from .fleet_controller import FleetController, RobotState
from .zone_manager import ZoneManager
from .task_scheduler import TaskScheduler, PickupSlotManager
from .error_detector import ErrorDetector, ErrorType, RobotError
from .error_recovery import ErrorRecoveryHandler, OperatorCommand, OperatorAction

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class FMSNode(Node):
    """
    Fleet Management System Node

    Architecture:
    - TaskManager: Order queue and task assignment
    - FleetController: Robot fleet status and control
    - ZoneManager: Collision avoidance and zone coordination

    Communication:
    - Subscribes to: /fms/order_request, /fms/delivery_complete
    - Publishes to: /fms/fleet_status
    - Controls robots via: /navigate_to_pose action (per DOMAIN_ID)
    - Monitors robots via: /pose, /battery/* topics (per DOMAIN_ID)

    NOTE: Each robot runs on separate ROS_DOMAIN_ID (11, 12, 13)
    FMS communicates via TCP or domain bridge for cross-domain messaging
    """

    def __init__(self):
        super().__init__('fms_node')

        logger.info("Initializing Fleet Management System...")

        # 로봇팔 스킵 모드 (로봇팔 연결 전 테스트용)
        self.declare_parameter('skip_robot_arm', True)
        self.skip_robot_arm = self.get_parameter('skip_robot_arm').value
        if self.skip_robot_arm:
            logger.info("*** SKIP ROBOT ARM MODE ENABLED ***")
            logger.info("로봇이 pickup_spot 도착 후 3초 뒤 자동으로 테이블로 이동합니다.")

        # Initial Pose 자동 설정 모드
        self.declare_parameter('auto_set_initial_pose', True)
        self.auto_set_initial_pose = self.get_parameter('auto_set_initial_pose').value

        # Robot configurations with ROS_DOMAIN_ID (not namespace)
        # Each robot runs on separate DOMAIN_ID in closed network
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11, 'ip': '192.168.1.7'},
            {'robot_id': 'pinky2', 'domain_id': 12, 'ip': '192.168.1.6', 'enabled': False},  # 테스트 제외
            {'robot_id': 'pinky3', 'domain_id': 13, 'ip': '192.168.1.11'}
        ]

        # Initialize core components
        self.task_manager = TaskManager()
        self.fleet_controller = FleetController(robot_configs)
        self.zone_manager = ZoneManager()
        self.task_scheduler = TaskScheduler(self.zone_manager)
        self.error_detector = ErrorDetector()
        self.error_recovery_handler = ErrorRecoveryHandler()

        # Robot domain configurations
        self.robot_domains = {}
        for config in robot_configs:
            if config.get('enabled', True) is False:
                continue
            robot_id = config['robot_id']
            domain_id = config.get('domain_id', 0)
            self.robot_domains[robot_id] = {
                'domain_id': domain_id,
                'ip': config.get('ip', ''),
            }
            logger.info(f"Registered robot {robot_id} on DOMAIN_ID={domain_id}")

        # NOTE: Navigation and monitoring requires matching DOMAIN_ID
        # For cross-domain communication, use TCP or domain bridge
        # Action clients are created for current domain only
        self.nav_clients = {}
        current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))
        logger.info(f"FMS running on DOMAIN_ID={current_domain}")

        # Create action client for robots on same domain
        for robot_id, domain_info in self.robot_domains.items():
            if domain_info['domain_id'] == current_domain:
                action_name = '/navigate_to_pose'  # No namespace prefix
                self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
                logger.info(f"Created navigation client for {robot_id}: {action_name} (DOMAIN_ID={current_domain})")
            else:
                logger.warning(f"Robot {robot_id} on different DOMAIN_ID={domain_info['domain_id']}, needs TCP/bridge")

        # Initial pose publishers (for same domain only)
        self.initialpose_pubs = {}
        for robot_id, domain_info in self.robot_domains.items():
            if domain_info['domain_id'] == current_domain:
                topic_name = '/initialpose'  # No namespace prefix
                self.initialpose_pubs[robot_id] = self.create_publisher(
                    PoseWithCovarianceStamped,
                    topic_name,
                    10
                )
                logger.info(f"Created initial pose publisher for {robot_id}: {topic_name}")

        # Publishers
        self.fleet_status_pub = self.create_publisher(
            FleetStatus,
            '/fms/fleet_status',
            10
        )

        self.pickup_arrival_pub = self.create_publisher(
            PickupArrival,
            '/fms/pickup_arrival',
            10
        )

        self.table_arrival_pub = self.create_publisher(
            TableArrival,
            '/fms/table_arrival',
            10
        )

        # CookingOrder publisher - send order to robot arm coordinator
        self.cooking_order_pub = self.create_publisher(
            CookingOrder,
            '/cooking/order',
            10
        )

        # Error alert publisher - notify operators about robot errors
        self.error_alert_pub = self.create_publisher(
            ErrorAlert,
            '/fms/error_alert',
            10
        )

        # Subscribers
        self.order_request_sub = self.create_subscription(
            OrderRequest,
            '/fms/order_request',
            self.order_request_callback,
            10
        )

        self.delivery_complete_sub = self.create_subscription(
            DeliveryComplete,
            '/fms/delivery_complete',
            self.delivery_complete_callback,
            10
        )

        self.precision_parked_sub = self.create_subscription(
            PrecisionParked,
            '/fms/precision_parked',
            self.precision_parked_callback,
            10
        )

        # LoadingComplete subscriber - receive food loaded notification from robot arm
        self.loading_complete_sub = self.create_subscription(
            LoadingComplete,
            '/cooking/loading_complete',
            self.loading_complete_callback,
            10
        )

        # Operator command subscriber - receive recovery commands from Admin GUI
        self.operator_command_sub = self.create_subscription(
            OperatorCommandMsg,
            '/fms/operator_command',
            self.operator_command_callback,
            10
        )

        # Robot monitoring subscribers
        self._setup_robot_monitoring(robot_configs)

        # Fleet status publisher timer (publish every 1 second)
        self.status_timer = self.create_timer(1.0, self.publish_fleet_status)

        # Task assignment timer (check for pending tasks every 0.5 seconds)
        self.assignment_timer = self.create_timer(0.5, self.process_pending_tasks)

        # Pickup queue processing timer (10Hz)
        self.pickup_queue_timer = self.create_timer(0.1, self._process_pickup_queue)

        # Reservation cleanup timer (1Hz)
        self.cleanup_timer = self.create_timer(1.0, self._cleanup_expired_reservations)

        # Error monitoring timer (2Hz)
        self.error_monitor_timer = self.create_timer(0.5, self._monitor_errors)

        # Error recovery timer (1Hz)
        self.error_recovery_timer = self.create_timer(1.0, self._process_recovery_actions)

        # Register recovery action callbacks
        self._register_recovery_callbacks()

        # TODO: Load map positions from config file
        self.map_positions = self._load_map_positions()

        # Load initial poses for AMCL localization
        self.initial_poses = self._load_initial_poses()

        # Set initial poses for all robots if enabled
        if self.auto_set_initial_pose:
            logger.info("Auto-setting initial poses for all robots...")
            self.create_timer(1.0, self._set_all_initial_poses_once)

        logger.info("Fleet Management System initialized successfully")

    def _setup_robot_monitoring(self, robot_configs: List[Dict]):
        """
        Setup subscribers for monitoring robot status

        NOTE: Only monitors robots on the same DOMAIN_ID as FMS.
        Cross-domain monitoring requires TCP or domain bridge.

        Args:
            robot_configs: List of robot configurations
        """
        current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))

        for config in robot_configs:
            if config.get('enabled', True) is False:
                continue
            robot_id = config['robot_id']
            domain_id = config.get('domain_id', 0)

            # Only subscribe to robots on same domain
            if domain_id != current_domain:
                logger.warning(f"Robot {robot_id} on DOMAIN_ID={domain_id}, skipping ROS monitoring")
                continue

            # Subscribe to pose (no namespace prefix)
            self.create_subscription(
                Pose,
                '/pose',
                lambda msg, rid=robot_id: self.robot_pose_callback(rid, msg),
                10
            )

            # Subscribe to battery voltage
            self.create_subscription(
                Float32,
                '/battery/voltage',
                lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
                10
            )

            # Subscribe to battery present
            self.create_subscription(
                Bool,
                '/battery/present',
                lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
                10
            )

            logger.info(f"Setup monitoring for robot {robot_id} (DOMAIN_ID={domain_id})")

    def _load_map_positions(self) -> Dict[str, Pose]:
        """
        Load map positions from config file

        Returns:
            Dictionary mapping location names to Pose objects
        """
        import yaml
        import os

        # Load from fms_config.yaml
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'fms_config.yaml'
        )

        positions = {}
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Load all positions from config
            for position_name, position_data in config.get('positions', {}).items():
                x = position_data.get('x', 0.0)
                y = position_data.get('y', 0.0)
                theta = position_data.get('theta', 0.0)
                positions[position_name] = self._create_pose(x, y, theta)

            logger.info(f"Loaded {len(positions)} positions from config")

        except Exception as e:
            logger.error(f"Failed to load positions from config: {e}")
            logger.warning("Using fallback placeholder positions")
            # Fallback to placeholder positions
            positions = {
                'pickup_spot': self._create_pose(0.47, 0.63, 3.14159),
                'table1': self._create_pose(1.785, 0.35, 0.0),
                'table2': self._create_pose(1.415, 0.35, 0.0),
                'table3': self._create_pose(1.785, 0.65, 0.0),
                'table4': self._create_pose(1.415, 0.65, 0.0),
                'table5': self._create_pose(1.235, 0.35, 0.0),
                'table6': self._create_pose(0.865, 0.35, 0.0),
                'table7': self._create_pose(1.235, 0.65, 0.0),
                'table8': self._create_pose(0.865, 0.65, 0.0),
                'pinky1_spot': self._create_pose(0.585, 0.085, 0.0),
                'pinky2_spot': self._create_pose(0.585, 0.255, 0.0),
                'pinky3_spot': self._create_pose(0.585, 0.915, 0.0),
            }

        return positions

    def _create_pose(self, x: float, y: float, theta: float) -> Pose:
        """
        Create Pose message

        Args:
            x: X position
            y: Y position
            theta: Yaw angle

        Returns:
            Pose message
        """
        pose = Pose()
        pose.position.x = x
        pose.position.y = y
        pose.position.z = 0.0

        # Convert theta to quaternion
        import math
        pose.orientation.z = math.sin(theta / 2.0)
        pose.orientation.w = math.cos(theta / 2.0)

        return pose

    # ========================================
    def _load_initial_poses(self) -> Dict[str, Pose]:
        """
        Load initial poses for robot AMCL localization from config

        Returns:
            Dictionary mapping robot_id to initial Pose
        """
        import yaml
        import os

        # Default fallback poses (parking spots)
        default_poses = {
            'pinky1': self._create_pose(0.585, 0.085, 0.0),
            'pinky2': self._create_pose(0.585, 0.255, 0.0),
            'pinky3': self._create_pose(0.585, 0.915, 0.0),
        }

        try:
            # Try to load from fms_config.yaml
            config_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                'config',
                'fms_config.yaml'
            )
            config_path = os.path.abspath(config_path)

            if not os.path.exists(config_path):
                logger.warning(f"Config file not found: {config_path}, using defaults")
                return default_poses

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            initial_poses_config = config.get('initial_poses', {})
            if not initial_poses_config:
                logger.warning("No initial_poses section in config, using defaults")
                return default_poses

            # Convert config to Pose objects
            initial_poses = {}
            for robot_id, pose_data in initial_poses_config.items():
                x = pose_data.get('x', 0.0)
                y = pose_data.get('y', 0.0)
                theta = pose_data.get('theta', 0.0)
                initial_poses[robot_id] = self._create_pose(x, y, theta)
                logger.info(f"Loaded initial pose for {robot_id}: x={x}, y={y}, theta={theta}")

            return initial_poses

        except Exception as e:
            logger.error(f"Failed to load initial poses from config: {e}")
            logger.info("Using default initial poses")
            return default_poses

    def set_initial_pose(self, robot_id: str, pose: Pose):
        """
        Set initial pose for a robot's AMCL localization

        Publishes to /initialpose topic (same DOMAIN_ID only)

        Args:
            robot_id: Robot ID (e.g., 'pinky1')
            pose: Initial pose (x, y, theta as quaternion)
        """
        publisher = self.initialpose_pubs.get(robot_id)
        if not publisher:
            logger.error(f"Initial pose publisher not found for robot {robot_id}")
            return

        # Create PoseWithCovarianceStamped message
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose = pose

        # Set covariance matrix (uncertainty in initial pose)
        # Default AMCL covariance: diagonal elements for x, y, theta
        msg.pose.covariance = [
            0.25, 0.0, 0.0, 0.0, 0.0, 0.0,  # x variance
            0.0, 0.25, 0.0, 0.0, 0.0, 0.0,  # y variance
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,   # z (unused)
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,   # roll (unused)
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,   # pitch (unused)
            0.0, 0.0, 0.0, 0.0, 0.0, 0.06853892326654787  # theta variance
        ]

        # Publish initial pose
        publisher.publish(msg)
        logger.info(f"Set initial pose for {robot_id}: x={pose.position.x:.3f}, y={pose.position.y:.3f}")

    def _set_all_initial_poses_once(self):
        """
        Set initial poses for all robots once (one-time timer callback)

        This is called once after FMS starts to initialize AMCL localization
        """
        # Prevent repeated execution
        if hasattr(self, '_initial_poses_set'):
            return

        for robot_id, pose in self.initial_poses.items():
            self.set_initial_pose(robot_id, pose)

        logger.info("Initial poses set for all robots")
        self._initial_poses_set = True

    # Callbacks
    # ========================================

    def order_request_callback(self, msg: OrderRequest):
        """
        Handle order request from Main Server

        Args:
            msg: OrderRequest message
        """
        logger.info(f"Received order request: order_id={msg.order_id}, table={msg.table_number}")

        # Create task in task_manager (legacy)
        task = self.task_manager.create_task(
            order_id=msg.order_id,
            menu_id=msg.menu_id,
            table_number=msg.table_number,
            quantity=msg.quantity,
            sauce_type=msg.sauce_type,
            voice_order=msg.voice_order
        )

        logger.info(f"Created task {task.task_id} for order {msg.order_id}")

        # Also add to task_scheduler for advanced scheduling
        self.task_scheduler.add_task(task)
        logger.debug(f"Added task {task.task_id} to scheduler queue")

    def delivery_complete_callback(self, msg: DeliveryComplete):
        """
        Handle delivery complete signal from Main Server

        SC-186/324: 복귀 명령 로직
        Flow:
        1. 작업 완료 표시
        2. 로봇 상태를 RETURNING으로 변경
        3. 존 해제 처리 (테이블 zone)
        4. 로봇을 주차 위치로 이동 명령

        Args:
            msg: DeliveryComplete message
        """
        logger.info(f"Received delivery complete: order_id={msg.order_id}, table={msg.table_number}")

        # Find task by order ID
        task = self.task_manager.get_task_by_order_id(msg.order_id)
        if task and task.assigned_robot:
            robot_id = task.assigned_robot

            # Complete task in task_manager
            self.task_manager.complete_task(task.task_id)

            # Complete task in scheduler
            self.task_scheduler.robot_delivered(robot_id, task.task_id)

            # SC-186: Update robot status - start returning home (RETURNING state)
            self.fleet_controller.robot_complete_delivery(robot_id)
            logger.info(f"Robot {robot_id} status changed to RETURNING")

            # Release table zone (if zone was reserved for delivery)
            # Note: Zones might not be explicitly reserved for tables, but we clean up anyway
            logger.info(f"Releasing delivery zone for robot {robot_id}")

            # Send robot back to parking spot
            self._send_robot_to_parking(robot_id)
            logger.info(f"Robot {robot_id} returning to parking spot after delivery")

    def precision_parked_callback(self, msg: PrecisionParked):
        """
        Handle precision parking complete from Precision Control Team

        After robot is precisely parked, send CookingOrder to robot arm coordinator.

        Args:
            msg: PrecisionParked message
        """
        logger.info(f"Received precision_parked: robot={msg.robot_id}, order={msg.order_id}, success={msg.success}")

        if not msg.success:
            logger.error(f"Precision parking failed for {msg.robot_id}: {msg.message}")
            # TODO: Handle parking failure - retry or abort task
            return

        # Robot is now precisely positioned for robot arm loading
        logger.info(f"Robot {msg.robot_id} is precisely parked, sending CookingOrder to robot arm...")

        # Find task to get order details
        task = self.task_manager.get_task_by_order_id(msg.order_id)
        if task:
            # Send CookingOrder to robot arm coordinator
            self._send_cooking_order(msg.order_id, task.menu_id, task.quantity,
                                     task.sauce_type, msg.robot_id)
        else:
            logger.warning(f"Task not found for order {msg.order_id}, cannot send CookingOrder")

    def _send_cooking_order(self, order_id: str, menu_id: str, quantity: int,
                            sauce_type: str, robot_id: str):
        """
        Send CookingOrder to robot arm coordinator

        Args:
            order_id: Order ID
            menu_id: Menu ID (M001, M002, M003)
            quantity: Number of items
            sauce_type: Sauce type (mayo, mustard, ketchup)
            robot_id: Assigned serving robot ID
        """
        msg = CookingOrder()
        msg.order_id = order_id
        msg.menu_id = menu_id
        msg.quantity = quantity
        msg.sauce_type = sauce_type if sauce_type else ''
        msg.assigned_robot_id = robot_id

        self.cooking_order_pub.publish(msg)
        logger.info(f"Published CookingOrder: order={order_id}, menu={menu_id}, "
                   f"quantity={quantity}, sauce={sauce_type}, robot={robot_id}")

    def loading_complete_callback(self, msg: LoadingComplete):
        """
        Handle food loading complete from robot arm coordinator

        Args:
            msg: LoadingComplete message
        """
        logger.info(f"Received LoadingComplete: order={msg.order_id}, robot={msg.robot_id}, "
                   f"success={msg.success}")

        if not msg.success:
            logger.error(f"Food loading failed for order {msg.order_id}: {msg.message}")
            # TODO: Handle loading failure - retry or abort task
            return

        # Food is loaded, proceed to table delivery
        self.notify_food_loaded(msg.robot_id, msg.order_id)

    def robot_pose_callback(self, robot_id: str, msg: Pose):
        """
        Handle robot pose update

        Args:
            robot_id: Robot ID
            msg: Pose message
        """
        # Register heartbeat for error detection
        self.error_detector.register_heartbeat(robot_id)

        # Update fleet controller
        self.fleet_controller.update_robot_pose(robot_id, msg)

        # Update zone manager
        self.zone_manager.update_robot_position(robot_id, msg)

        # Check if robot reached destination
        self._check_navigation_status(robot_id)

    def robot_battery_voltage_callback(self, robot_id: str, msg: Float32):
        """
        Handle robot battery voltage update

        Args:
            robot_id: Robot ID
            msg: Float32 message with voltage
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if robot:
            self.fleet_controller.update_robot_battery(
                robot_id,
                msg.data,
                robot.battery_present
            )

    def robot_battery_present_callback(self, robot_id: str, msg: Bool):
        """
        Handle robot battery present update

        Args:
            robot_id: Robot ID
            msg: Bool message
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if robot:
            self.fleet_controller.update_robot_battery(
                robot_id,
                robot.battery_voltage,
                msg.data
            )

    # ========================================
    # Task Processing
    # ========================================

    def process_pending_tasks(self):
        """
        Process pending tasks and assign to available robots
        """
        if self.task_scheduler.get_pending_count() == 0:
            return

        # Get available robot
        robot = self.fleet_controller.get_available_robot()
        if not robot:
            return

        # Assign task from scheduler
        task = self.task_scheduler.assign_task_to_robot(robot.robot_id)
        if task:
            # Update fleet controller
            self.fleet_controller.assign_task_to_robot(
                robot.robot_id,
                task.task_id,
                task.order_id
            )

            # Try to reserve pickup zone
            if self.zone_manager.reserve_zone(robot.robot_id, 'zone_pickup'):
                # Zone reserved, send robot to pickup
                self._send_robot_to_pickup(robot.robot_id)
                logger.info(f"Assigned task {task.task_id} to robot {robot.robot_id} with zone reservation")
            else:
                # Pickup zone occupied, send to waiting zone
                waiting_zone = self.task_scheduler.get_next_waiting_zone(robot.robot_id)
                if waiting_zone:
                    self._send_robot_to_waiting_zone(robot.robot_id, waiting_zone)
                    logger.info(f"Assigned task {task.task_id} to robot {robot.robot_id}, waiting at {waiting_zone}")
                else:
                    logger.warning(f"No waiting zone available for robot {robot.robot_id}")

            logger.info(f"Assigned task {task.task_id} to robot {robot.robot_id}")

    def _send_robot_to_pickup(self, robot_id: str):
        """
        Send robot to pickup spot

        Args:
            robot_id: Robot ID
        """
        pickup_pose = self.map_positions.get('pickup_spot')
        if pickup_pose:
            self._navigate_robot(robot_id, pickup_pose)
            logger.info(f"Sending robot {robot_id} to pickup spot")

    def _send_robot_to_table(self, robot_id: str, table_number: str):
        """
        Send robot to table

        Args:
            robot_id: Robot ID
            table_number: Table number (T01-T08)
        """
        # Convert T01 -> table1
        table_name = table_number.lower().replace('t0', 'table').replace('t', 'table')
        table_pose = self.map_positions.get(table_name)

        if table_pose:
            self._navigate_robot(robot_id, table_pose)
            self.fleet_controller.robot_start_delivery(robot_id, table_number)
            logger.info(f"Sending robot {robot_id} to {table_number}")

    def _send_robot_to_parking(self, robot_id: str):
        """
        Send robot to parking spot

        Args:
            robot_id: Robot ID
        """
        parking_name = f"{robot_id}_spot"
        parking_pose = self.map_positions.get(parking_name)

        if parking_pose:
            self._navigate_robot(robot_id, parking_pose)
            logger.info(f"Sending robot {robot_id} to parking spot")

    def _send_robot_to_waiting_zone(self, robot_id: str, waiting_zone_name: str):
        """
        Send robot to waiting zone while waiting for pickup slot

        Args:
            robot_id: Robot ID
            waiting_zone_name: Waiting zone location name (e.g., 'point13', 'pinky1_spot')
        """
        waiting_pose = self.map_positions.get(waiting_zone_name)
        if waiting_pose:
            self._navigate_robot(robot_id, waiting_pose)
            logger.info(f"Sending robot {robot_id} to waiting zone: {waiting_zone_name}")
        else:
            logger.warning(f"Waiting zone {waiting_zone_name} not found in map positions")

    def _navigate_robot(self, robot_id: str, goal_pose: Pose):
        """
        Send navigation goal to robot

        Args:
            robot_id: Robot ID
            goal_pose: Goal pose
        """
        nav_client = self.nav_clients.get(robot_id)
        if not nav_client:
            logger.error(f"Navigation client not found for robot {robot_id}")
            return

        # Create goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose = goal_pose

        # Send goal
        nav_client.send_goal_async(goal_msg)
        logger.debug(f"Sent navigation goal to robot {robot_id}")

    def _check_navigation_status(self, robot_id: str):
        """
        Check if robot reached its destination

        Args:
            robot_id: Robot ID
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot or not robot.target_location:
            return

        # Get target pose
        target_pose = self.map_positions.get(robot.target_location)
        if not target_pose or not robot.current_pose:
            return

        # Calculate distance to target
        distance = self.fleet_controller.calculate_distance(robot.current_pose, target_pose)

        # Check if reached (within 0.1m threshold)
        if distance < 0.1:
            if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
                # Reached pickup spot (point13)
                self.fleet_controller.robot_reached_pickup(robot_id)
                logger.info(f"Robot {robot_id} reached point13 (pickup area)")

                # Get current task from scheduler
                scheduler_task = self.task_scheduler.get_robot_task(robot_id)
                task = None

                if scheduler_task:
                    # Find in task_manager for compatibility
                    for t in self.task_manager.assigned_tasks.values():
                        if t.assigned_robot == robot_id:
                            task = t
                            break
                else:
                    # Fallback to task_manager
                    for t in self.task_manager.assigned_tasks.values():
                        if t.assigned_robot == robot_id:
                            task = t
                            break

                if task:
                    # Request pickup slot access
                    can_enter = self.task_scheduler.request_pickup_access(robot_id, task.task_id)

                    if can_enter:
                        # Robot has pickup access, enter pickup spot
                        self.zone_manager.occupy_zone(robot_id, 'zone_pickup')
                        logger.info(f"Robot {robot_id} granted pickup access, entering pickup spot")

                        # Publish PickupArrival message to Precision Control Team
                        arrival_msg = PickupArrival()
                        arrival_msg.robot_id = robot_id
                        arrival_msg.order_id = task.order_id
                        arrival_msg.current_pose = robot.current_pose
                        arrival_msg.arrived_at = self.get_clock().now().to_msg()
                        self.pickup_arrival_pub.publish(arrival_msg)
                        logger.info(f"Published PickupArrival for {robot_id}, order {task.order_id}")
                    else:
                        # Robot must wait for pickup slot
                        logger.info(f"Robot {robot_id} waiting for pickup slot, sending to waiting zone")
                        waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
                        if waiting_zone:
                            self._send_robot_to_waiting_zone(robot_id, waiting_zone)

                    # Skip mode for precision parking and robot arm
                    if self.skip_robot_arm:
                        logger.info(f"[SKIP_MODE] Auto-mocking precision_parked after 2s, then food_loaded after 3s...")
                        # Auto precision parked after 2s, then food loaded after 3s (total 5s)
                        import threading
                        threading.Timer(2.0, lambda: self._auto_precision_parked(robot_id)).start()
                    else:
                        logger.info(f"Waiting for precision parking from Precision Control Team...")

            elif robot.status == RobotState.STATUS_IDLE and robot.target_location:
                # Robot reached a waiting zone or other intermediate location
                # Check if robot is waiting for pickup
                scheduler_task = self.task_scheduler.get_robot_task(robot_id)
                if scheduler_task:
                    task_state = self.task_scheduler.get_task_state(scheduler_task.task_id)
                    if task_state and task_state.value == 'WAITING_FOR_PICKUP':
                        # Robot reached waiting zone, check if pickup slot is now available
                        logger.info(f"Robot {robot_id} reached waiting zone, checking pickup availability...")
                        self._process_pickup_queue()

            elif robot.status == RobotState.STATUS_MOVING_TO_TABLE:
                # Reached table
                self.fleet_controller.robot_reached_table(robot_id)
                logger.info(f"Robot {robot_id} reached table, waiting for customer")

                # SC-183/321: Get current task for TableArrival message
                scheduler_task = self.task_scheduler.get_robot_task(robot_id)
                task = None

                if scheduler_task:
                    # Find in task_manager for compatibility
                    for t in self.task_manager.assigned_tasks.values():
                        if t.assigned_robot == robot_id:
                            task = t
                            break
                else:
                    # Fallback to task_manager
                    for t in self.task_manager.assigned_tasks.values():
                        if t.assigned_robot == robot_id:
                            task = t
                            break

                if task:
                    # Publish TableArrival message to Main Server
                    arrival_msg = TableArrival()
                    arrival_msg.robot_id = robot_id
                    arrival_msg.order_id = task.order_id
                    arrival_msg.table_number = task.table_number
                    arrival_msg.current_pose = robot.current_pose if robot.current_pose else Pose()
                    arrival_msg.arrived_at = self.get_clock().now().to_msg()
                    self.table_arrival_pub.publish(arrival_msg)
                    logger.info(f"Published TableArrival for {robot_id}, order {task.order_id}, table {task.table_number}")

            elif robot.status == RobotState.STATUS_RETURNING:
                # Returned home
                self.fleet_controller.robot_returned_home(robot_id)
                logger.info(f"Robot {robot_id} returned home, now IDLE")

    # ========================================
    # Status Publishing
    # ========================================

    def publish_fleet_status(self):
        """Publish fleet status"""
        fleet_status = FleetStatus()

        # Get all robots
        robots = self.fleet_controller.get_all_robots()

        # Build RobotStatus messages
        robot_statuses = []
        for robot in robots:
            robot_status = RobotStatus()
            robot_status.robot_id = robot.robot_id
            robot_status.status = robot.status

            if robot.current_pose:
                robot_status.current_pose = robot.current_pose
            else:
                robot_status.current_pose = Pose()

            robot_status.battery_voltage = robot.battery_voltage
            robot_status.battery_present = robot.battery_present
            robot_status.timestamp = self._datetime_to_ros_time(robot.last_update)

            robot_statuses.append(robot_status)

        fleet_status.robots = robot_statuses

        # Use scheduler pending/active counts (more accurate with scheduling logic)
        fleet_status.pending_orders = self.task_scheduler.get_pending_count()
        fleet_status.active_orders = self.task_scheduler.get_active_count()
        fleet_status.timestamp = self._datetime_to_ros_time(datetime.utcnow())

        self.fleet_status_pub.publish(fleet_status)

        # Log scheduler status periodically (every 5 publishes to avoid spam)
        if not hasattr(self, '_status_publish_count'):
            self._status_publish_count = 0
        self._status_publish_count += 1

        if self._status_publish_count % 5 == 0:
            scheduler_status = self.task_scheduler.get_scheduler_status()
            logger.debug(f"Scheduler Status: {scheduler_status}")

    def _datetime_to_ros_time(self, dt: datetime) -> Time:
        """Convert Python datetime to ROS Time message"""
        timestamp = dt.timestamp()
        time_msg = Time()
        time_msg.sec = int(timestamp)
        time_msg.nanosec = int((timestamp - int(timestamp)) * 1e9)
        return time_msg

    # ========================================
    # Skip Mode Functions (Precision Parking + Robot Arm)
    # ========================================

    def _auto_precision_parked(self, robot_id: str):
        """
        Skip mode: Auto-mock precision parking completion

        Args:
            robot_id: Robot ID
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            return

        # Find current task
        task = None
        for t in self.task_manager.assigned_tasks.values():
            if t.assigned_robot == robot_id:
                task = t
                break

        if task:
            logger.info(f"[SKIP_MODE] Auto precision_parked for {robot_id}, order {task.order_id}")

            # Mock PrecisionParked message
            parked_msg = PrecisionParked()
            parked_msg.robot_id = robot_id
            parked_msg.order_id = task.order_id
            parked_msg.success = True
            parked_msg.final_pose = robot.current_pose if robot.current_pose else Pose()
            parked_msg.message = "Skip mode: auto parked"
            parked_msg.completed_at = self.get_clock().now().to_msg()

            # Trigger precision_parked_callback
            self.precision_parked_callback(parked_msg)

            # After precision parking, trigger food loading after 3s
            import threading
            threading.Timer(3.0, lambda: self._auto_food_loaded(robot_id)).start()
        else:
            logger.warning(f"[SKIP_MODE] No task found for robot {robot_id}")

    def _auto_food_loaded(self, robot_id: str):
        """
        Skip mode: Auto-mock food loading completion

        In skip mode, this simulates the robot arm coordinator completing food preparation.
        In normal mode, the coordinator receives CookingOrder and publishes LoadingComplete.

        Args:
            robot_id: Robot ID
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            return

        # Find current task
        task = None
        for t in self.task_manager.assigned_tasks.values():
            if t.assigned_robot == robot_id:
                task = t
                break

        if task:
            logger.info(f"[SKIP_MODE] Auto food loaded for {robot_id}, order {task.order_id}")

            # In skip mode, mock LoadingComplete message
            mock_msg = LoadingComplete()
            mock_msg.order_id = task.order_id
            mock_msg.robot_id = robot_id
            mock_msg.success = True
            mock_msg.message = "Skip mode: auto loaded"
            mock_msg.completed_at = self.get_clock().now().to_msg()

            # Call callback directly
            self.loading_complete_callback(mock_msg)
        else:
            logger.warning(f"[SKIP_MODE] No task found for robot {robot_id}")

    # ========================================
    # External Interface (for robot arm team)
    # ========================================

    def notify_food_loaded(self, robot_id: str, order_id: str):
        """
        Notify that food has been loaded onto robot

        This is called after robot arm completes cooking and loads food

        Args:
            robot_id: Robot ID
            order_id: Order ID
        """
        logger.info(f"Food loaded onto robot {robot_id} for order {order_id}")

        # Find task
        task = self.task_manager.get_task_by_order_id(order_id)
        if task and task.assigned_robot == robot_id:
            # Start task
            self.task_manager.start_task(task.task_id)

            # Update scheduler state
            scheduler_task = self.task_scheduler.get_robot_task(robot_id)
            if scheduler_task:
                self.task_scheduler.robot_loaded(robot_id, scheduler_task.task_id)

            # Release pickup zone
            self.zone_manager.leave_zone(robot_id, 'zone_pickup')

            # Send robot to table
            self._send_robot_to_table(robot_id, task.table_number)

            # Process pickup queue - allow next waiting robot
            self._process_pickup_queue()

    # ========================================
    # Pickup Queue and Zone Management
    # ========================================

    def _process_pickup_queue(self):
        """
        Process waiting robots in pickup queue

        If pickup zone is available and robots are waiting,
        grant access to next robot in queue
        """
        # Check if any robots are waiting
        if self.task_scheduler.get_waiting_count() == 0:
            return

        # Check if pickup zone is available
        if not self.zone_manager.is_zone_available('zone_pickup'):
            return

        # Get next waiting robot
        next_robot = self.task_scheduler.pickup_manager.get_next_in_queue()
        if not next_robot:
            return

        logger.info(f"Granting pickup slot to waiting robot {next_robot}")

        # Grant pickup slot (this also removes from queue)
        self.task_scheduler.pickup_manager.request_pickup_slot(next_robot)

        # Reserve pickup zone for this robot
        if self.zone_manager.reserve_zone(next_robot, 'zone_pickup'):
            # Send to pickup spot
            self._send_robot_to_pickup(next_robot)
            logger.info(f"Robot {next_robot} can now proceed to pickup spot")
        else:
            logger.error(f"Failed to reserve pickup zone for robot {next_robot}")

    def _cleanup_expired_reservations(self):
        """
        Clean up expired zone reservations

        Called periodically (1Hz) to free up zones that have been
        reserved too long
        """
        cleaned_count = self.zone_manager.cleanup_expired_reservations()
        if cleaned_count > 0:
            logger.warning(f"Cleaned up {cleaned_count} expired zone reservations")

        # Also check pickup slot timeout
        if self.task_scheduler.pickup_manager.check_slot_timeout():
            logger.warning("Pickup slot timeout detected, forcing release")
            next_robot = self.task_scheduler.pickup_manager.force_release_slot()
            if next_robot:
                # Grant to next robot
                self._process_pickup_queue()

    # ========================================
    # Error Detection and Recovery
    # ========================================

    def _register_recovery_callbacks(self):
        """Register callbacks for operator commands"""
        self.error_recovery_handler.register_action_callback(
            OperatorCommand.RETRY,
            self._handle_retry_command
        )
        self.error_recovery_handler.register_action_callback(
            OperatorCommand.RETURN_HOME,
            self._handle_return_home_command
        )
        self.error_recovery_handler.register_action_callback(
            OperatorCommand.EMERGENCY_STOP,
            self._handle_emergency_stop_command
        )
        self.error_recovery_handler.register_action_callback(
            OperatorCommand.CLEAR_ERROR,
            self._handle_clear_error_command
        )
        logger.info("Recovery action callbacks registered")

    def operator_command_callback(self, msg: OperatorCommandMsg):
        """
        Handle operator command from Admin GUI

        Args:
            msg: OperatorCommand message
        """
        robot_id = msg.robot_id
        command_str = msg.command

        # Map string to OperatorCommand enum
        command_map = {
            'RETRY': OperatorCommand.RETRY,
            'RETURN_HOME': OperatorCommand.RETURN_HOME,
            'EMERGENCY_STOP': OperatorCommand.EMERGENCY_STOP,
            'CLEAR_ERROR': OperatorCommand.CLEAR_ERROR,
        }

        command = command_map.get(command_str)
        if not command:
            logger.warning(f"Unknown operator command: {command_str}")
            return

        # Submit operator action
        self.error_recovery_handler.submit_operator_command(
            robot_id=robot_id,
            command=command,
            order_id=msg.order_id if msg.order_id else None,
            reason=msg.reason if msg.reason else "Operator action"
        )

        logger.info(f"Operator command {command_str} queued for robot {robot_id}")

    def _monitor_errors(self):
        """
        Monitor robot errors continuously

        Called at 2Hz to check for:
        - Communication loss (heartbeat timeout)
        - Low battery
        - Task timeouts
        """
        robots = self.fleet_controller.get_all_robots()

        for robot in robots:
            # Check communication loss
            comm_error = self.error_detector.check_communication_loss(robot.robot_id)
            if comm_error:
                self._handle_detected_error(comm_error)

            # Check low battery
            battery_error = self.error_detector.check_low_battery(
                robot.robot_id,
                robot.battery_voltage,
                robot.current_pose
            )
            if battery_error:
                self._handle_detected_error(battery_error)

    def _handle_detected_error(self, error: RobotError):
        """
        Handle a detected error

        Args:
            error: RobotError object
        """
        # Check if this error already exists
        if self.error_detector.register_error(error):
            # New error - publish alert and update fleet controller
            self._publish_error_alert(error)
            self.fleet_controller.robot_error(error.robot_id, error.error_message)
            logger.error(f"Error detected for {error.robot_id}: {error.error_type.value}")

    def _publish_error_alert(self, error: RobotError):
        """
        Publish error alert message

        Args:
            error: RobotError object
        """
        alert_msg = ErrorAlert()
        alert_msg.robot_id = error.robot_id
        alert_msg.error_type = error.error_type.value
        alert_msg.error_message = error.error_message
        alert_msg.current_pose = error.current_pose if error.current_pose else Pose()
        alert_msg.battery_voltage = error.battery_voltage
        alert_msg.timestamp = self.get_clock().now().to_msg()

        self.error_alert_pub.publish(alert_msg)
        logger.warning(f"Published error alert for {error.robot_id}: {error.error_message}")

    def _process_recovery_actions(self):
        """
        Process pending operator recovery actions

        Called at 1Hz to execute queued recovery commands
        """
        robots = self.fleet_controller.get_all_robots()

        for robot in robots:
            # Check if there's a pending action
            if self.error_recovery_handler.has_pending_action(robot.robot_id):
                # Execute the action
                self.error_recovery_handler.execute_action(robot.robot_id)

    def _handle_retry_command(self, robot_id: str, order_id: str, reason: str):
        """
        Handle RETRY operator command - retry failed navigation task

        Args:
            robot_id: Target robot ID
            order_id: Associated order ID (unused for retry)
            reason: Reason for retry
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found")
            return

        logger.info(f"Retrying navigation for robot {robot_id}: {reason}")

        # Get current target location
        if robot.target_location:
            target_pose = self.map_positions.get(robot.target_location)
            if target_pose:
                # Resend navigation goal
                self._navigate_robot(robot_id, target_pose)
                logger.info(f"Resent navigation goal to {robot.target_location}")
        else:
            logger.warning(f"No target location set for robot {robot_id}")

    def _handle_return_home_command(self, robot_id: str, order_id: str, reason: str):
        """
        Handle RETURN_HOME operator command - force robot to return to parking

        Args:
            robot_id: Target robot ID
            order_id: Associated order ID (unused for return home)
            reason: Reason for return
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found")
            return

        logger.info(f"Forcing robot {robot_id} to return home: {reason}")

        # Mark task as failed/abandoned if in progress
        if robot.current_task_id:
            logger.warning(f"Abandoning task {robot.current_task_id} for robot {robot_id}")
            self.task_manager.abandon_task(robot.current_task_id)

        # Send to parking spot
        self._send_robot_to_parking(robot_id)
        robot.update_status(RobotState.STATUS_RETURNING)

        logger.info(f"Robot {robot_id} commanded to return home")

    def _handle_emergency_stop_command(self, robot_id: str, order_id: str, reason: str):
        """
        Handle EMERGENCY_STOP operator command - stop robot immediately

        Args:
            robot_id: Target robot ID
            order_id: Associated order ID (unused for emergency stop)
            reason: Reason for emergency stop
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found")
            return

        logger.critical(f"EMERGENCY STOP for robot {robot_id}: {reason}")

        # Update robot status to ERROR
        robot.update_status(RobotState.STATUS_ERROR)

        # Cancel any pending navigation
        nav_client = self.nav_clients.get(robot_id)
        if nav_client and hasattr(nav_client, 'cancel_all_goals'):
            try:
                nav_client.cancel_all_goals()
                logger.info(f"Cancelled navigation for robot {robot_id}")
            except Exception as e:
                logger.warning(f"Could not cancel navigation: {e}")

        # Mark task as failed
        if robot.current_task_id:
            logger.warning(f"Aborting task {robot.current_task_id} due to emergency stop")
            self.task_manager.abandon_task(robot.current_task_id)

        logger.critical(f"Robot {robot_id} emergency stop executed")

    def _handle_clear_error_command(self, robot_id: str, order_id: str, reason: str):
        """
        Handle CLEAR_ERROR operator command - manually clear error state

        Args:
            robot_id: Target robot ID
            order_id: Associated order ID (unused for clear error)
            reason: Reason for clearing error
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found")
            return

        logger.info(f"Clearing error state for robot {robot_id}: {reason}")

        # Clear error in error detector
        if self.error_detector.clear_error(robot_id):
            # Set robot to IDLE
            robot.update_status(RobotState.STATUS_IDLE)
            logger.info(f"Error cleared for robot {robot_id}, status set to IDLE")
        else:
            logger.warning(f"No active error for robot {robot_id} to clear")


def main():
    """Entry point for FMS Node"""
    rclpy.init()

    try:
        fms_node = FMSNode()

        # Register signal handlers
        def signal_handler(sig, frame):
            logger.info("Shutting down FMS...")
            fms_node.destroy_node()
            rclpy.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("FMS Node is running...")
        rclpy.spin(fms_node)

    except Exception as e:
        logger.error(f"FMS Node error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
