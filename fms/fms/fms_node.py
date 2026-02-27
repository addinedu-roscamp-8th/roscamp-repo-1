"""
Fleet Management System (FMS) Node
Integrates TaskManager, FleetController, and ZoneManager
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from nav2_msgs.action import NavigateToPose, FollowWaypoints
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
from std_msgs.msg import Float32, Bool, String
from builtin_interfaces.msg import Time
import logging
import math
import os
import signal
import sys
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from .task_manager import TaskManager, Task
from .fleet_controller import FleetController, RobotState
from .zone_manager import ZoneManager
from .task_scheduler import TaskScheduler, PickupSlotManager
from .error_detector import ErrorDetector, ErrorType, RobotError
from .error_recovery import ErrorRecoveryHandler, OperatorCommand, OperatorAction
from .order_handler import OrderHandler
from .gui_tcp_server import GUITCPServer
from .path_planner import PathPlanner, NavigationGraph
from .collision_avoidance import CollisionAvoidanceController

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
        self.declare_parameter('skip_robot_arm', False)  # Production mode: use robot arm
        self.skip_robot_arm = self.get_parameter('skip_robot_arm').value
        if self.skip_robot_arm:
            logger.info("*** SKIP ROBOT ARM MODE ENABLED ***")
            logger.info("로봇이 pickup_spot 도착 후 3초 뒤 자동으로 테이블로 이동합니다.")
        else:
            logger.info("*** ROBOT ARM MODE ENABLED ***")
            logger.info("로봇이 pickup_spot 도착 후 로봇팔의 LoadingComplete를 기다립니다.")

        # Initial Pose 자동 설정 모드
        self.declare_parameter('auto_set_initial_pose', True)
        self.auto_set_initial_pose = self.get_parameter('auto_set_initial_pose').value

        # Robot configurations with ROS_DOMAIN_ID (not namespace)
        # Each robot runs on separate DOMAIN_ID in closed network
        # FMS runs on DOMAIN_ID=25, Domain Bridge handles cross-domain communication
        robot_configs = [
            {'robot_id': 'pinky1', 'domain_id': 11, 'ip': '192.168.1.7', 'enabled': True},
            {'robot_id': 'pinky2', 'domain_id': 12, 'ip': '192.168.1.6', 'enabled': True},
            {'robot_id': 'pinky3', 'domain_id': 13, 'ip': '192.168.1.11', 'enabled': True}
        ]

        # Initialize core components
        self.task_manager = TaskManager()
        self.fleet_controller = FleetController(robot_configs)
        self.zone_manager = ZoneManager()
        self.task_scheduler = TaskScheduler(self.zone_manager)
        self.error_detector = ErrorDetector()
        self.error_recovery_handler = ErrorRecoveryHandler()

        # Path planner for waypoint-based navigation
        self.path_planner = PathPlanner()

        # Collision avoidance controller for multi-robot coordination
        # Pass PickupSlotManager to sync pickup queues
        self.collision_avoidance = CollisionAvoidanceController(
            self.path_planner.graph,
            self.zone_manager,
            self.fleet_controller,
            pickup_slot_manager=self.task_scheduler.pickup_manager
        )

        # Initialize order handler (Application Layer)
        self.order_handler = OrderHandler()

        # Initialize GUI TCP server (Infrastructure Layer)
        self.gui_tcp_server = GUITCPServer(host='0.0.0.0', port=9000)

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

        # NOTE: FMS runs on DOMAIN_ID=25, Domain Bridge handles cross-domain communication
        # Action clients are created for ALL robots (bridge forwards to robot domains)
        self.nav_clients = {}
        current_domain = int(os.environ.get('ROS_DOMAIN_ID', 0))
        logger.info(f"FMS running on DOMAIN_ID={current_domain}")

        # Create action clients for ALL robots (Domain Bridge remaps to robot-specific names)
        for robot_id, domain_info in self.robot_domains.items():
            action_name = f'/{robot_id}/navigate_to_pose'  # Robot-specific via Domain Bridge
            self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
            logger.info(f"Created navigation client for {robot_id}: {action_name}")

        # FollowWaypoints action client for strict waypoint following (Domain Bridge remaps to robot-specific)
        self.follow_waypoints_clients = {}
        for robot_id, domain_info in self.robot_domains.items():
            action_name = f'/{robot_id}/follow_waypoints'  # Robot-specific via Domain Bridge
            self.follow_waypoints_clients[robot_id] = ActionClient(self, FollowWaypoints, action_name)
            logger.info(f"Created FollowWaypoints client for {robot_id}: {action_name}")

        # NOTE: goal_pose publisher removed - using FollowWaypoints action instead
        # The _navigate_robot() method that used this publisher is deprecated
        # All navigation now uses _follow_waypoints() via _navigate_robot_by_name()

        # Initial pose publishers (Domain Bridge remaps to robot-specific names)
        self.initialpose_pubs = {}
        for robot_id, domain_info in self.robot_domains.items():
            topic_name = f'/{robot_id}/initialpose'  # Robot-specific via Domain Bridge
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

        # CookingCommand publisher - send cooking command to robot arm
        # Topic: /cooking/command (String type for simple command interface)
        self.cooking_command_pub = self.create_publisher(
            String,
            '/cooking/command',
            10
        )

        # Error alert publisher - notify operators about robot errors
        self.error_alert_pub = self.create_publisher(
            ErrorAlert,
            '/fms/error_alert',
            10
        )

        # Cooking status subscriber - receive cooking status from robot arm
        self.cooking_status_sub = self.create_subscription(
            String,
            '/cooking/status',
            self.cooking_status_callback,
            10
        )
        logger.info("Subscribed to /cooking/status for cooking completion")

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

        # Collision check timer (5Hz) for multi-robot coordination
        self.collision_check_timer = self.create_timer(0.2, self._check_collisions)

        # Pending order check timer (0.5Hz = every 2 seconds)
        # Checks if there are queued orders and available robots
        self.pending_order_timer = self.create_timer(2.0, self._check_pending_orders)

        # Register recovery action callbacks
        self._register_recovery_callbacks()

        # Register order handler callbacks (Infrastructure -> Application layer)
        self._register_order_handler_callbacks()

        # Register GUI TCP server handlers (Application -> Infrastructure layer)
        self._register_gui_tcp_handlers()

        # Start GUI TCP server
        self.gui_tcp_server.start()
        logger.info("GUI TCP server started on port 9000")

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

        NOTE: FMS runs on DOMAIN_ID=25, Domain Bridge forwards topics from all robot domains.
        Each robot's topics are remapped to robot-specific names:
        - /amcl_pose -> /{robot_id}/amcl_pose
        - /battery/voltage -> /{robot_id}/battery/voltage
        - /battery/present -> /{robot_id}/battery/present

        Args:
            robot_configs: List of robot configurations
        """
        for config in robot_configs:
            if config.get('enabled', True) is False:
                continue
            robot_id = config['robot_id']
            domain_id = config.get('domain_id', 0)

            # Subscribe to robot-specific amcl_pose for localization (via Domain Bridge remapping)
            # Use VOLATILE durability for compatibility with Domain Bridge
            # Domain Bridge republishes AMCL pose with VOLATILE durability
            amcl_qos = QoSProfile(
                depth=10,
                reliability=ReliabilityPolicy.RELIABLE,
                durability=DurabilityPolicy.VOLATILE
            )
            amcl_topic = f'/{robot_id}/amcl_pose'
            self.create_subscription(
                PoseWithCovarianceStamped,
                amcl_topic,
                lambda msg, rid=robot_id: self.robot_pose_callback(rid, msg.pose.pose),
                amcl_qos
            )

            # Subscribe to robot-specific battery voltage (via Domain Bridge remapping)
            voltage_topic = f'/{robot_id}/battery/voltage'
            self.create_subscription(
                Float32,
                voltage_topic,
                lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
                10
            )

            # Subscribe to robot-specific battery present (via Domain Bridge remapping)
            present_topic = f'/{robot_id}/battery/present'
            self.create_subscription(
                Bool,
                present_topic,
                lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
                10
            )

            logger.info(f"Setup monitoring for {robot_id}: {amcl_topic}, {voltage_topic}, {present_topic}")

    def _load_map_positions(self) -> Dict[str, Pose]:
        """
        Load map positions from config file

        Returns:
            Dictionary mapping location names to Pose objects
        """
        import yaml
        import os

        # Load from fms_config.yaml (source directory)
        config_path = '/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml'

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
            # Load from fms_config.yaml (source directory)
            config_path = '/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml'

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

        # Notify order handler about cooking completion
        self.order_handler.handle_cooking_complete(msg.order_id)

        # Legacy: Food is loaded, proceed to table delivery
        self.notify_food_loaded(msg.robot_id, msg.order_id)

    def robot_pose_callback(self, robot_id: str, msg: Pose):
        """
        Handle robot pose update

        Args:
            robot_id: Robot ID
            msg: Pose message
        """
        # Debug: Log received pose
        if not hasattr(self, '_pose_log_count'):
            self._pose_log_count = {}
        self._pose_log_count[robot_id] = self._pose_log_count.get(robot_id, 0) + 1
        if self._pose_log_count[robot_id] <= 3 or self._pose_log_count[robot_id] % 100 == 0:
            logger.info(f"[POSE] Received pose for {robot_id}: x={msg.position.x:.3f}, y={msg.position.y:.3f} (count: {self._pose_log_count[robot_id]})")

        # Register heartbeat for error detection
        self.error_detector.register_heartbeat(robot_id)

        # Update fleet controller
        self.fleet_controller.update_robot_pose(robot_id, msg)

        # Update zone manager
        self.zone_manager.update_robot_position(robot_id, msg)

        # Update collision avoidance - release passed nodes in real-time
        released_nodes = self.collision_avoidance.update_robot_position(
            robot_id, msg.position.x, msg.position.y
        )

        # If nodes were released, trigger replan for waiting robots
        if released_nodes:
            self._trigger_waiting_robots_replan(robot_id, released_nodes)

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
        Send robot to pickup_spot using waypoint-based navigation

        Flow:
        1. Robot moves to pickup_spot via waypoints (FollowWaypoints action)
        2. At pickup_spot: precision control mode (skip mode auto-handles this)
        3. After food loaded: robot moves to table

        Args:
            robot_id: Robot ID
        """
        # Use waypoint navigation to ensure robot follows defined paths
        logger.info(f"[WAYPOINT NAV] Sending robot {robot_id} to pickup_spot")
        self._navigate_robot_by_name(robot_id, 'pickup_spot')

    def _send_robot_to_table(self, robot_id: str, table_number: str):
        """
        Send robot to table using waypoint-based navigation

        Args:
            robot_id: Robot ID
            table_number: Table number (T01-T08)
        """
        # Convert T01 -> table1
        table_name = table_number.lower().replace('t0', 'table').replace('t', 'table')

        # Verify table exists in map positions
        if table_name not in self.map_positions:
            logger.error(f"Table {table_name} not found in map positions")
            return

        # Use waypoint navigation to ensure robot follows defined paths
        logger.info(f"[WAYPOINT NAV] Sending robot {robot_id} to {table_number} ({table_name})")
        self._navigate_robot_by_name(robot_id, table_name)
        self.fleet_controller.robot_start_delivery(robot_id, table_number)

    def _send_robot_to_parking(self, robot_id: str):
        """
        Send robot to parking spot using waypoint-based navigation

        Args:
            robot_id: Robot ID
        """
        parking_name = f"{robot_id}_spot"

        # Verify parking spot exists in map positions
        if parking_name not in self.map_positions:
            logger.error(f"Parking spot {parking_name} not found in map positions")
            return

        # Use waypoint navigation to ensure robot follows defined paths
        logger.info(f"[WAYPOINT NAV] Sending robot {robot_id} to parking spot ({parking_name})")
        self._navigate_robot_by_name(robot_id, parking_name)

    def _send_robot_to_waiting_zone(self, robot_id: str, waiting_zone_name: str):
        """
        Send robot to waiting zone using waypoint-based navigation

        Args:
            robot_id: Robot ID
            waiting_zone_name: Waiting zone location name (e.g., 'point13', 'pinky1_spot')
        """
        # Verify waiting zone exists in map positions
        if waiting_zone_name not in self.map_positions:
            logger.warning(f"Waiting zone {waiting_zone_name} not found in map positions")
            return

        # Use waypoint navigation to ensure robot follows defined paths
        logger.info(f"[WAYPOINT NAV] Sending robot {robot_id} to waiting zone: {waiting_zone_name}")
        self._navigate_robot_by_name(robot_id, waiting_zone_name)

    # NOTE: _navigate_robot() method removed - was unused
    # This method used /goal_pose topic which bypasses waypoint constraints
    # All navigation now uses _follow_waypoints() via _navigate_robot_by_name()
    # for strict waypoint following with collision avoidance

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
            # Call order handler integration for order-based navigation
            self._check_navigation_status_with_order_handler(robot_id)

            if robot.status == RobotState.STATUS_MOVING_TO_PICKUP:
                # Reached pickup_spot
                self.fleet_controller.robot_reached_pickup(robot_id)
                logger.info(f"Robot {robot_id} reached pickup_spot")

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

                # Clear collision avoidance path - robot has arrived at destination
                self.collision_avoidance.clear_robot_path(robot_id)

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

                # Clear collision avoidance path - robot returned home
                self.collision_avoidance.clear_robot_path(robot_id)

    # ========================================
    # Order Handler Callbacks (Infrastructure Layer)
    # ========================================

    def _send_cooking_command_to_arm(self, cooking_command: Dict[str, Any]):
        """
        Send cooking command to robot arm via ROS2 topic

        Publishes to:
        - /cooking/command (String): Simple command format "START|order_id|menu_id|quantity"
        - /cooking/order (CookingOrder): Full order message for compatibility

        Args:
            cooking_command: {
                'order_id': str,
                'operation': 'START',
                'menu_items': [...],
                'table_number': int
            }
        """
        order_id = cooking_command['order_id']
        menu_items = cooking_command.get('menu_items', [{}])
        logger.info(f"[DEBUG] cooking_command: {cooking_command}")
        logger.info(f"[DEBUG] menu_items: {menu_items}")
        menu_id = menu_items[0].get('menu_id', 'M001') if menu_items else 'M001'
        quantity = menu_items[0].get('quantity', 1) if menu_items else 1
        operation = cooking_command.get('operation', 'START')
        # Extract sauce from first menu item (GUI sends sauce per item)
        sauce_type = menu_items[0].get('sauce', '') if menu_items else ''
        logger.info(f"[DEBUG] extracted sauce_type: '{sauce_type}'")

        # Publish to /cooking/command (String - JSON format for cooking_interface_node)
        import json
        command_msg = String()
        command_json = {
            'job_id': order_id,
            'order_id': order_id,
            'operation': operation,
            'menu_items': menu_items
        }
        command_msg.data = json.dumps(command_json)
        self.cooking_command_pub.publish(command_msg)
        logger.info(f"Published /cooking/command: {command_msg.data}")

        # Also publish CookingOrder for compatibility
        order_msg = CookingOrder()
        order_msg.order_id = order_id
        order_msg.menu_id = menu_id
        order_msg.quantity = quantity
        order_msg.sauce_type = sauce_type
        order_msg.assigned_robot_id = 'pinky1'  # Always pinky1 as per requirements

        self.cooking_order_pub.publish(order_msg)
        logger.info(f"Published /cooking/order: order={order_id}, menu={menu_id}, qty={quantity}, sauce={sauce_type}")

    def _navigate_robot_by_name(self, robot_id: str, location_name: str):
        """
        Navigate robot to named location using waypoint-based path planning with collision avoidance

        Args:
            robot_id: Robot ID (e.g., 'pinky1')
            location_name: Location name (e.g., 'point13', 'table1')
        """
        pose = self.map_positions.get(location_name)
        if not pose:
            logger.error(f"Location {location_name} not found in map positions")
            return

        # Get robot's current position (use last known or parking spot)
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.error(f"Robot {robot_id} not found")
            return

        # Determine starting waypoint
        current_waypoint = None
        own_spot = f"{robot_id}_spot"

        if robot.current_pose:
            # First, check if robot is near its own spot (within 0.2m)
            own_spot_pos = self.path_planner.graph.get_position(own_spot)
            if own_spot_pos:
                dist_to_own_spot = math.sqrt(
                    (robot.current_pose.position.x - own_spot_pos[0])**2 +
                    (robot.current_pose.position.y - own_spot_pos[1])**2
                )
                if dist_to_own_spot < 0.2:
                    # Robot is near its own spot, use that as starting point
                    current_waypoint = own_spot
                    logger.info(f"Robot {robot_id} is near its own spot ({dist_to_own_spot:.3f}m), using {own_spot}")

            # If not near own spot, find nearest waypoint
            if not current_waypoint:
                current_waypoint = self.path_planner.graph.get_nearest_waypoint(
                    robot.current_pose.position.x,
                    robot.current_pose.position.y
                )
                logger.info(f"Robot {robot_id} nearest waypoint: {current_waypoint}")

        if not current_waypoint:
            # Use parking spot as default starting point
            current_waypoint = own_spot
            logger.info(f"Using {current_waypoint} as starting waypoint for {robot_id}")

        # Set final target location
        robot.target_location = location_name
        robot.final_destination = location_name  # Store final destination
        logger.info(f"Set target_location={location_name} for {robot_id}")

        # Use collision avoidance for path planning
        route, success = self.collision_avoidance.plan_path_with_avoidance(
            robot_id, current_waypoint, location_name
        )

        if success and route:
            # No collision, proceed with planned route
            robot.current_route = route
            robot.route_index = 0
            logger.info(f"[COLLISION_AVOIDANCE] Route planned for {robot_id}: {' -> '.join(route)}")
            self._follow_waypoints(robot_id, route)
        elif route and not success:
            # Collision detected, move to waiting position
            robot.current_route = route
            robot.route_index = 0
            wait_state = self.collision_avoidance.get_robot_wait_state(robot_id)
            if wait_state:
                logger.info(f"[COLLISION_AVOIDANCE] {robot_id} waiting at {wait_state.waiting_at} "
                           f"for {wait_state.waiting_for}, goal: {location_name}")
            else:
                logger.info(f"[COLLISION_AVOIDANCE] {robot_id} moving to waiting position")
            # Navigate to waiting position
            self._follow_waypoints(robot_id, route)
        elif current_waypoint == location_name:
            # Robot is already at or very near the destination
            logger.info(f"[WAYPOINT] Robot {robot_id} already at destination {location_name}")
            robot.current_route = []
            robot.route_index = 0
            self._start_arrival_timer(robot_id, location_name)
        else:
            # Fallback: No route found, try basic path planning without collision avoidance
            logger.warning(f"[COLLISION_AVOIDANCE] No route found with collision avoidance, trying basic planning")
            basic_route = self.path_planner.plan_route(robot_id, current_waypoint, location_name)

            if basic_route:
                robot.current_route = basic_route
                robot.route_index = 0
                logger.info(f"[WAYPOINT] Basic route planned for {robot_id}: {' -> '.join(basic_route)}")
                self._follow_waypoints(robot_id, basic_route)
            else:
                # Last resort: single waypoint navigation
                logger.warning(f"[WAYPOINT] No route found from {current_waypoint} to {location_name}, using single waypoint")
                robot.current_route = [location_name]
                robot.route_index = 0
                self._follow_waypoints(robot_id, [location_name])

    def _follow_waypoints(self, robot_id: str, waypoints: List[str]):
        """
        Use FollowWaypoints action to navigate through all waypoints strictly

        Args:
            robot_id: Robot ID
            waypoints: List of waypoint names to follow in order
        """
        client = self.follow_waypoints_clients.get(robot_id)
        if not client:
            logger.error(f"No FollowWaypoints client for {robot_id}")
            return

        # Wait for action server
        if not client.wait_for_server(timeout_sec=5.0):
            logger.warning(f"FollowWaypoints action server not available via domain bridge for {robot_id}")
            logger.info(f"Falling back to SSH-based navigation for {robot_id}")
            self._follow_waypoints_via_ssh(robot_id, waypoints)
            return

        # Build waypoint poses with orientation towards next waypoint
        # First, collect all waypoint positions
        waypoint_positions = []
        waypoint_names = []
        for wp_name in waypoints:
            pose = self.map_positions.get(wp_name)
            if not pose:
                logger.warning(f"Waypoint {wp_name} not found, skipping")
                continue

            if hasattr(pose, 'position'):
                waypoint_positions.append((pose.position.x, pose.position.y))
            else:
                waypoint_positions.append((pose['x'], pose['y']))
            waypoint_names.append(wp_name)

        # Build poses with calculated orientations
        poses = []
        for i, (wp_name, (x, y)) in enumerate(zip(waypoint_names, waypoint_positions)):
            pose_stamped = PoseStamped()
            pose_stamped.header.frame_id = 'map'
            pose_stamped.header.stamp = self.get_clock().now().to_msg()
            pose_stamped.pose.position.x = x
            pose_stamped.pose.position.y = y
            pose_stamped.pose.position.z = 0.0

            # Calculate orientation towards next waypoint
            if i < len(waypoint_positions) - 1:
                # For non-final waypoints: orient towards the next waypoint
                next_x, next_y = waypoint_positions[i + 1]
                yaw = math.atan2(next_y - y, next_x - x)
            else:
                # For final waypoint (pickup_spot): face +x direction for robot arm loading
                yaw = 0.0

            # Convert yaw to quaternion (rotation around z-axis only)
            pose_stamped.pose.orientation.x = 0.0
            pose_stamped.pose.orientation.y = 0.0
            pose_stamped.pose.orientation.z = math.sin(yaw / 2.0)
            pose_stamped.pose.orientation.w = math.cos(yaw / 2.0)

            poses.append(pose_stamped)
            logger.info(f"[WAYPOINT] Added {wp_name}: x={x:.3f}, y={y:.3f}, yaw={math.degrees(yaw):.1f}deg")

        if not poses:
            logger.error(f"No valid waypoints to follow for {robot_id}")
            return

        # Create goal
        goal_msg = FollowWaypoints.Goal()
        goal_msg.poses = poses

        logger.info(f"[WAYPOINT] Sending {len(poses)} waypoints to FollowWaypoints for {robot_id}")

        # Send goal with callbacks
        send_goal_future = client.send_goal_async(
            goal_msg,
            feedback_callback=lambda feedback: self._follow_waypoints_feedback(robot_id, feedback)
        )
        send_goal_future.add_done_callback(
            lambda future: self._follow_waypoints_goal_response(robot_id, future, waypoints)
        )

    def _follow_waypoints_feedback(self, robot_id: str, feedback_msg):
        """FollowWaypoints feedback 처리"""
        feedback = feedback_msg.feedback
        current_idx = feedback.current_waypoint
        logger.info(f"[WAYPOINT] {robot_id} navigating to waypoint {current_idx + 1}")

    def _follow_waypoints_goal_response(self, robot_id: str, future, waypoints: List[str]):
        """FollowWaypoints goal 응답 처리"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            logger.error(f"[WAYPOINT] FollowWaypoints goal rejected for {robot_id}")
            return

        logger.info(f"[WAYPOINT] FollowWaypoints goal accepted for {robot_id}")

        # Get result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda future: self._follow_waypoints_result(robot_id, future, waypoints)
        )

    def _follow_waypoints_result(self, robot_id: str, future, waypoints: List[str]):
        """FollowWaypoints 결과 처리"""
        result = future.result().result
        missed_waypoints = result.missed_waypoints

        if missed_waypoints:
            logger.warning(f"[WAYPOINT] {robot_id} missed waypoints: {missed_waypoints}")
        else:
            logger.info(f"[WAYPOINT] {robot_id} completed all {len(waypoints)} waypoints successfully!")

        # Trigger final destination arrival
        robot = self.fleet_controller.get_robot(robot_id)
        if robot:
            final_dest = getattr(robot, 'final_destination', robot.target_location)
            logger.info(f"[WAYPOINT] {robot_id} route complete, arrived at {final_dest}")
            robot.current_route = None
            robot.route_index = 0
            self._on_final_destination_reached(robot_id, final_dest)

    def _follow_waypoints_via_ssh(self, robot_id: str, waypoints: List[str]):
        """
        Fallback method: Send waypoints to robot via SSH when domain bridge action fails

        Args:
            robot_id: Robot ID (pinky1, pinky2, pinky3)
            waypoints: List of waypoint names to follow
        """
        # Get robot configuration
        robot_config = {
            'pinky1': {'ip': '192.168.1.7', 'domain': 11},
            'pinky2': {'ip': '192.168.1.6', 'domain': 12},
            'pinky3': {'ip': '192.168.1.11', 'domain': 13},
        }

        config = robot_config.get(robot_id)
        if not config:
            logger.error(f"Unknown robot {robot_id} for SSH navigation")
            return

        # Build waypoints JSON with positions
        waypoint_positions = []
        for wp_name in waypoints:
            pose = self.map_positions.get(wp_name)
            if pose:
                if hasattr(pose, 'position'):
                    waypoint_positions.append({'x': pose.position.x, 'y': pose.position.y})
                else:
                    waypoint_positions.append({'x': pose['x'], 'y': pose['y']})

        if not waypoint_positions:
            logger.error(f"No valid waypoints for SSH navigation: {waypoints}")
            return

        # Build ROS2 message for FollowWaypoints with orientation towards next waypoint
        poses_str_list = []
        for i, wp in enumerate(waypoint_positions):
            # Calculate orientation towards next waypoint
            if i < len(waypoint_positions) - 1:
                # For non-final waypoints: orient towards the next waypoint
                next_wp = waypoint_positions[i + 1]
                yaw = math.atan2(next_wp['y'] - wp['y'], next_wp['x'] - wp['x'])
            else:
                # For final waypoint (pickup_spot): face +x direction for robot arm loading
                yaw = 0.0

            # Convert yaw to quaternion
            qz = math.sin(yaw / 2.0)
            qw = math.cos(yaw / 2.0)

            pose_str = f'{{header: {{frame_id: "map"}}, pose: {{position: {{x: {wp["x"]:.3f}, y: {wp["y"]:.3f}, z: 0.0}}, orientation: {{x: 0.0, y: 0.0, z: {qz:.6f}, w: {qw:.6f}}}}}}}'
            poses_str_list.append(pose_str)
        poses_str = '[' + ', '.join(poses_str_list) + ']'

        # Build SSH command
        ssh_cmd = [
            'ssh', f'pinky@{config["ip"]}',
            f'source /opt/ros/jazzy/setup.bash && source ~/pinky_pro/install/setup.bash && '
            f'ROS_DOMAIN_ID={config["domain"]} ros2 action send_goal /follow_waypoints '
            f'nav2_msgs/action/FollowWaypoints "{{poses: {poses_str}}}"'
        ]

        logger.info(f"[SSH-NAV] Sending {len(waypoint_positions)} waypoints to {robot_id} via SSH")

        # Execute in background
        try:
            process = subprocess.Popen(
                ssh_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"[SSH-NAV] Navigation command sent to {robot_id}, PID: {process.pid}")

            # Store process for monitoring
            if not hasattr(self, '_ssh_nav_processes'):
                self._ssh_nav_processes = {}
            self._ssh_nav_processes[robot_id] = {
                'process': process,
                'waypoints': waypoints,
                'start_time': datetime.utcnow()
            }

            # Start a timer to check completion (simple polling)
            self.create_timer(2.0, lambda: self._check_ssh_nav_completion(robot_id))

        except Exception as e:
            logger.error(f"[SSH-NAV] Failed to send navigation to {robot_id}: {e}")

    def _check_ssh_nav_completion(self, robot_id: str):
        """SSH 기반 navigation 완료 확인"""
        if not hasattr(self, '_ssh_nav_processes') or robot_id not in self._ssh_nav_processes:
            return

        nav_info = self._ssh_nav_processes[robot_id]
        process = nav_info['process']

        poll_result = process.poll()
        if poll_result is not None:
            # Process completed
            stdout, stderr = process.communicate()
            logger.info(f"[SSH-NAV] {robot_id} navigation completed with exit code: {poll_result}")
            if stdout:
                logger.debug(f"[SSH-NAV] stdout: {stdout[:500]}")
            if stderr and 'Goal accepted' not in stderr:
                logger.warning(f"[SSH-NAV] stderr: {stderr[:500]}")

            # Trigger destination reached
            waypoints = nav_info['waypoints']
            if waypoints:
                robot = self.fleet_controller.get_robot(robot_id)
                if robot:
                    final_dest = getattr(robot, 'final_destination', robot.target_location)
                    logger.info(f"[SSH-NAV] {robot_id} route complete via SSH, arrived at {final_dest}")
                    robot.current_route = None
                    robot.route_index = 0
                    self._on_final_destination_reached(robot_id, final_dest)

            del self._ssh_nav_processes[robot_id]

    def _navigate_to_waypoint(self, robot_id: str, waypoint_name: str):
        """
        [DEPRECATED] Legacy method - DO NOT USE.
        Use _navigate_robot_by_name() which uses FollowWaypoints action instead.

        This method uses direct /goal_pose navigation which allows Nav2 to plan
        its own path, bypassing waypoint constraints. It has been replaced by
        _follow_waypoints() which enforces strict waypoint following.

        Args:
            robot_id: Robot ID
            waypoint_name: Waypoint name
        """
        logger.warning(f"[DEPRECATED] _navigate_to_waypoint() called for {robot_id} -> {waypoint_name}. "
                      f"This legacy method uses direct navigation. Use _navigate_robot_by_name() instead!")

        # Redirect to proper waypoint navigation
        self._navigate_robot_by_name(robot_id, waypoint_name)

    def _on_waypoint_reached(self, robot_id: str, waypoint_name: str):
        """
        [DEPRECATED] Legacy callback for sequential waypoint navigation.
        This is no longer used with FollowWaypoints action which handles
        all waypoints in a single action call.

        The FollowWaypoints action provides its own feedback and result callbacks:
        - _follow_waypoints_feedback(): Reports progress through waypoints
        - _follow_waypoints_result(): Handles completion of all waypoints

        Args:
            robot_id: Robot ID
            waypoint_name: Waypoint name reached
        """
        logger.warning(f"[DEPRECATED] _on_waypoint_reached() called for {robot_id} at {waypoint_name}. "
                      f"This legacy callback should not be called when using FollowWaypoints action.")

        # Do nothing - FollowWaypoints handles waypoint progression internally

    def _on_final_destination_reached(self, robot_id: str, location_name: str):
        """
        Called when robot reaches final destination

        Args:
            robot_id: Robot ID
            location_name: Final destination name
        """
        logger.info(f"[ARRIVED] {robot_id} reached final destination: {location_name}")

        # Trigger appropriate handler based on destination type
        if location_name.startswith('table'):
            # Table arrival - trigger delivery notification
            active_orders = self.order_handler.get_all_active_orders()
            order_id = None
            for oid, order_status in active_orders.items():
                if order_status.get('robot_id') == robot_id:
                    order_id = oid
                    break
            if order_id:
                self.order_handler.handle_robot_arrived_table(robot_id, order_id)

            # Clear collision avoidance path - robot has arrived at table
            self.collision_avoidance.clear_robot_path(robot_id)

        elif location_name == 'pickup_spot':
            # Pickup spot arrival
            active_orders = self.order_handler.get_all_active_orders()
            order_id = None
            for oid, order_status in active_orders.items():
                if order_status.get('robot_id') == robot_id:
                    order_id = oid
                    break
            if order_id:
                self.order_handler.handle_robot_arrived_pickup_spot(robot_id, order_id)

                # Publish PickupArrival message
                robot = self.fleet_controller.get_robot(robot_id)
                if robot:
                    arrival_msg = PickupArrival()
                    arrival_msg.robot_id = robot_id
                    arrival_msg.order_id = order_id
                    arrival_msg.current_pose = robot.current_pose
                    arrival_msg.arrived_at = self.get_clock().now().to_msg()
                    self.pickup_arrival_pub.publish(arrival_msg)
                    logger.info(f"Published PickupArrival for {robot_id}, order {order_id} to /fms/pickup_arrival")

            # Clear collision avoidance path - robot reached pickup spot
            # The next path (pickup_spot -> table) will be set after cooking completes
            self.collision_avoidance.clear_robot_path(robot_id)

        elif location_name.endswith('_spot') and location_name != 'pickup_spot':
            # Parking spot arrival
            logger.info(f"{robot_id} returned to parking spot {location_name}")

            # Clear collision avoidance path - robot returned home
            self.collision_avoidance.clear_robot_path(robot_id)

    def _start_arrival_timer(self, robot_id: str, location_name: str):
        """
        Start timer for simulated arrival (used for direct navigation)

        Args:
            robot_id: Robot ID
            location_name: Target location
        """
        import threading
        robot = self.fleet_controller.get_robot(robot_id)

        def auto_arrival():
            import time
            time.sleep(5.0)  # Wait for simulated navigation
            if robot and robot.target_location == location_name:
                logger.info(f"[SIMULATION] Auto-triggering arrival for {robot_id} at {location_name}")
                self._on_final_destination_reached(robot_id, location_name)

        timer_thread = threading.Thread(target=auto_arrival, daemon=True)
        timer_thread.start()
        logger.info(f"[SIMULATION] Started auto-arrival timer for {robot_id} -> {location_name}")

    def _send_gui_notification(self, notification: Dict[str, Any]):
        """
        Send push notification to GUI clients

        Args:
            notification: {
                'type': 'delivery_notification',
                'data': {...}
            }
        """
        self.gui_tcp_server.broadcast(notification)
        logger.info(f"Sent notification to GUI: {notification['type']}")

    def _fleet_controller_operation(self, robot_id: str, operation: str):
        """
        Execute fleet controller operation

        Args:
            robot_id: Robot ID
            operation: Operation name (e.g., 'complete_delivery')
        """
        if operation == 'complete_delivery':
            self.fleet_controller.robot_complete_delivery(robot_id)
        else:
            logger.warning(f"Unknown fleet controller operation: {operation}")

    def _get_available_robot_for_order(self) -> Optional[str]:
        """
        Get available robot for order processing

        Returns:
            robot_id if available, None otherwise
        """
        available_robot = self.fleet_controller.get_available_robot()
        if available_robot:
            logger.info(f"Available robot for order: {available_robot.robot_id}")
            return available_robot.robot_id
        logger.info("No available robot for order")
        return None

    def _assign_robot_to_order(self, robot_id: str, order_id: str) -> bool:
        """
        Assign robot to order in fleet controller

        This method handles both:
        1. Normal assignment when robot is IDLE
        2. Auto-dispatch when robot just completed a delivery (may be in DELIVERING state)

        Args:
            robot_id: Robot ID to assign
            order_id: Order ID to assign to

        Returns:
            True if assignment successful, False otherwise
        """
        try:
            # Find or create task for this order
            task = self.task_manager.get_task_by_order_id(order_id)
            if task:
                task_id = task.task_id
            else:
                # Create a minimal task for order handler workflow
                task_id = f"task_{order_id}"

            # First, try normal assignment
            success = self.fleet_controller.assign_task_to_robot(robot_id, task_id, order_id)

            if not success:
                # Robot may be in DELIVERING state from previous order (auto-dispatch case)
                # Force clear the robot state and retry assignment
                robot = self.fleet_controller.get_robot(robot_id)
                if robot:
                    logger.info(f"Robot {robot_id} is in state {robot.status}, forcing reset for auto-dispatch")
                    # Clear previous task and set to available
                    self.fleet_controller.mark_robot_available(robot_id)
                    # Retry assignment
                    success = self.fleet_controller.assign_task_to_robot(robot_id, task_id, order_id)

            if success:
                logger.info(f"Assigned robot {robot_id} to order {order_id}")
            else:
                logger.warning(f"Failed to assign robot {robot_id} to order {order_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to assign robot {robot_id} to order {order_id}: {e}")
            return False

    def _navigate_robot_to_home(self, robot_id: str):
        """
        Navigate robot to its home (parking) position

        Args:
            robot_id: Robot ID (e.g., 'pinky1', 'pinky2', 'pinky3')
        """
        home_position = f"{robot_id}_spot"  # pinky1_spot, pinky2_spot, pinky3_spot
        logger.info(f"Navigating robot {robot_id} to home: {home_position}")
        self._navigate_robot_by_name(robot_id, home_position)

    def _send_cooking_command(self, order_id: str, order_data: Dict):
        """
        Send cooking command to robot arm

        Args:
            order_id: Order ID
            order_data: Order data with menu items
        """
        import json
        command = {
            'job_id': order_id,
            'order_id': order_id,
            'operation': 'START',
            'menu_items': order_data.get('items', [])
        }
        self.cooking_command_pub.publish(String(data=json.dumps(command)))
        logger.info(f"Sent cooking command for order {order_id}")

    # ========================================
    # GUI TCP Message Handlers (Infrastructure Layer)
    # ========================================

    def _handle_gui_new_order(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle new order from GUI

        Args:
            message: {
                'command': 'new_order',
                'table_number': 1,
                'order': {...}
            }

        Returns:
            Response dict with order_id and status
        """
        logger.info(f"Received new order from GUI: table={message.get('table_number')}")

        try:
            result = self.order_handler.handle_new_order(message)
            logger.info(f"Order processed: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to process order: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def _handle_gui_delivery_complete(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle delivery confirmation from GUI (customer received order)

        Args:
            message: {
                'command': 'delivery_complete',
                'order_id': 'ORD-XXX',
                'table_number': 1
            }
            OR (nested format from GUI):
            {
                'type': 'delivery_complete',
                'data': {'order_id': 'ORD-XXX', 'table_number': '1'}
            }

        Returns:
            Response dict
        """
        # Support both flat and nested message formats
        if 'data' in message:
            data = message.get('data', {})
            order_id = data.get('order_id')
            table_number = data.get('table_number')
        else:
            order_id = message.get('order_id')
            table_number = message.get('table_number')

        logger.info(f"Received delivery confirmation from GUI: order={order_id}")

        try:
            self.order_handler.handle_delivery_confirmation(order_id, table_number)
            return {
                'success': True,
                'message': 'Delivery confirmed, robot returning home'
            }
        except Exception as e:
            logger.error(f"Failed to handle delivery confirmation: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    # ========================================
    # Enhanced Navigation Status Checking (with Order Handler integration)
    # ========================================

    def _check_navigation_status_with_order_handler(self, robot_id: str):
        """
        Enhanced navigation status checking with order handler integration

        This method extends the original _check_navigation_status to integrate
        with the order handler for proper workflow management.
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
            # pickup_spot arrival
            if robot.target_location == 'pickup_spot':
                logger.info(f"Robot {robot_id} reached pickup_spot")

                # Get current order
                # Try to find order from order_handler
                active_orders = self.order_handler.get_all_active_orders()
                order_id = None
                for oid, order_status in active_orders.items():
                    if order_status.get('robot_id') == robot_id:
                        order_id = oid
                        break

                if order_id:
                    self.order_handler.handle_robot_arrived_pickup_spot(robot_id, order_id)

                    # Skip robot arm mode: auto-trigger cooking complete after 3 seconds
                    if self.skip_robot_arm:
                        logger.info(f"[SKIP_MODE] Robot {robot_id} at pickup_spot, auto cooking complete in 3s...")
                        import threading
                        threading.Timer(3.0, lambda oid=order_id: self.order_handler.handle_cooking_complete(oid)).start()

            # Table arrival
            elif robot.target_location.startswith('table'):
                logger.info(f"Robot {robot_id} reached {robot.target_location}")

                # Get current order
                active_orders = self.order_handler.get_all_active_orders()
                order_id = None
                for oid, order_status in active_orders.items():
                    if order_status.get('robot_id') == robot_id:
                        order_id = oid
                        break

                if order_id:
                    self.order_handler.handle_robot_arrived_table(robot_id, order_id)

    # ========================================
    # Status Publishing
    # ========================================

    def publish_fleet_status(self):
        """fleet 상태 발행"""
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
        """Python datetime을 ROS Time 메시지로 변환"""
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

    def _check_pending_orders(self):
        """
        Check for pending orders and dispatch to available robots

        Called periodically (every 2 seconds) to check if:
        1. There are orders waiting in the queue
        2. There is an available robot to handle the order

        If both conditions are met, dispatches the next queued order.
        """
        # Check if there are queued orders
        queued_count = self.order_handler.get_queued_order_count()
        if queued_count == 0:
            return

        # Check for available robot
        available_robot = self._get_available_robot_for_order()
        if not available_robot:
            return

        # Process the next queued order
        result = self.order_handler.process_queued_order(available_robot)
        if result:
            logger.info(f"[PENDING ORDER] Dispatched queued order to {available_robot}: {result}")
        else:
            logger.debug(f"[PENDING ORDER] No order dispatched (result: {result})")

    # ========================================
    # Error Detection and Recovery
    # ========================================

    def _register_recovery_callbacks(self):
        """운영자 명령용 callback 등록"""
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

    def _register_order_handler_callbacks(self):
        """
        Register callbacks for order handler (Application Layer -> Infrastructure Layer)
        Following Dependency Inversion Principle
        """
        # Register base callbacks
        self.order_handler.register_callbacks(
            send_cooking_command=self._send_cooking_command_to_arm,
            navigate_robot=self._navigate_robot_by_name,
            send_gui_notification=self._send_gui_notification,
            fleet_controller=self._fleet_controller_operation
        )

        # Register additional callbacks for enhanced workflow
        # Available robot callback
        self.order_handler.set_get_available_robot_callback(
            self._get_available_robot_for_order
        )

        # Robot home callback
        self.order_handler.set_navigate_robot_home_callback(
            self._navigate_robot_to_home
        )

        # Robot navigation callback (already registered via register_callbacks but also via setter)
        self.order_handler.set_navigate_robot_callback(
            self._navigate_robot_by_name
        )

        # Cooking command callback (already registered via register_callbacks but also via setter)
        self.order_handler.set_send_cooking_command_callback(
            self._send_cooking_command_to_arm
        )

        # Assign robot callback - for assigning robot to order in fleet controller
        self.order_handler.set_assign_robot_callback(
            self._assign_robot_to_order
        )

        logger.info("Order handler callbacks registered (with enhanced callbacks)")

    def _register_gui_tcp_handlers(self):
        """
        Register message handlers for GUI TCP server (Infrastructure Layer)
        """
        self.gui_tcp_server.register_handler('new_order', self._handle_gui_new_order)
        self.gui_tcp_server.register_handler('delivery_complete', self._handle_gui_delivery_complete)
        logger.info("GUI TCP server handlers registered")

    def cooking_status_callback(self, msg: String):
        """
        Handle cooking status from robot arm

        Args:
            msg: String message with JSON cooking status
                {
                    'job_id': 'order_id',
                    'order_id': 'order_id',
                    'status': 'cooking' | 'ready' | 'error',
                    'progress': 0-100
                }
        """
        import json
        try:
            status_data = json.loads(msg.data)
            order_id = status_data.get('order_id') or status_data.get('job_id')
            status = status_data.get('status')
            progress = status_data.get('progress', 0)

            logger.info(f"Cooking status: order={order_id}, status={status}, progress={progress}%")

            if status == 'ready':
                logger.info(f"Cooking completed for order {order_id}")
                self.order_handler.handle_cooking_complete(order_id)
            elif status == 'error':
                logger.error(f"Cooking error for order {order_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid cooking status JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing cooking status: {e}")

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

    def _trigger_waiting_robots_replan(self, moved_robot_id: str, released_nodes: List[str]):
        """
        특정 로봇이 노드를 지나가서 해제되었을 때, 대기 중인 다른 로봇들의 재계획을 트리거

        Args:
            moved_robot_id: 이동한 로봇 ID
            released_nodes: 해제된 노드 목록
        """
        from .collision_avoidance import ReplanTrigger, WaitState

        robots = self.fleet_controller.get_all_robots()

        for robot in robots:
            # 이동한 로봇 자신은 제외
            if robot.robot_id == moved_robot_id:
                continue

            # 대기 중인 로봇만 확인
            wait_state = self.collision_avoidance.get_robot_wait_state(robot.robot_id)
            if not wait_state or wait_state.state == WaitState.NOT_WAITING:
                continue

            # 이동한 로봇을 기다리고 있는지 확인
            if wait_state.waiting_for != moved_robot_id:
                continue

            # 해제된 노드가 블로킹된 노드 목록에 있는지 확인
            blocked_released = set(released_nodes) & set(wait_state.blocked_nodes)
            if not blocked_released:
                continue

            logger.info(f"[COLLISION] {robot.robot_id}: 노드 {blocked_released} 해제됨, 재계획 시도")

            # 재계획 시도
            if wait_state.original_goal:
                new_path, success = self.collision_avoidance.handle_replan_trigger(
                    robot.robot_id, ReplanTrigger.ROBOT_MOVED
                )
                if success and new_path:
                    logger.info(f"[COLLISION] {robot.robot_id} 경로 확보, 이동 시작!")
                    robot.current_route = new_path
                    robot.route_index = 0
                    self._follow_waypoints(robot.robot_id, new_path)

    def _check_collisions(self):
        """
        Periodic collision check for multi-robot coordination (5Hz)

        This method:
        1. Checks for deadlock conditions and resolves them
        2. Checks waiting robots for timeout and triggers replanning
        3. Checks if waiting positions have become available
        4. Updates collision avoidance controller with current robot positions
        5. Triggers replanning for robots whose paths are now clear
        """
        from .collision_avoidance import ReplanTrigger, WaitState

        # Check for deadlock (two robots waiting for each other)
        if self.collision_avoidance.check_and_resolve_deadlock():
            logger.info("[COLLISION] Deadlock resolved automatically")

        robots = self.fleet_controller.get_all_robots()

        for robot in robots:
            robot_id = robot.robot_id

            # Skip robots that are idle or not moving
            if robot.status in [RobotState.STATUS_IDLE, RobotState.STATUS_ERROR]:
                continue

            # Check wait timeout
            if self.collision_avoidance.check_wait_timeout(robot_id):
                logger.warning(f"[COLLISION] {robot_id} wait timeout, attempting replan")
                wait_state = self.collision_avoidance.get_robot_wait_state(robot_id)
                if wait_state and wait_state.original_goal:
                    # Attempt to replan after timeout
                    new_path, success = self.collision_avoidance.handle_replan_trigger(
                        robot_id, ReplanTrigger.TIMEOUT
                    )
                    if success and new_path:
                        logger.info(f"[COLLISION] {robot_id} replanned successfully after timeout")
                        robot.current_route = new_path
                        robot.route_index = 0
                        self._follow_waypoints(robot_id, new_path)

            # Check waiting robots - see if their path is now clear
            wait_state = self.collision_avoidance.get_robot_wait_state(robot_id)
            if wait_state and wait_state.state != WaitState.NOT_WAITING:
                # Check if the blocking robot has moved
                if wait_state.waiting_for:
                    blocking_robot = self.fleet_controller.get_robot(wait_state.waiting_for)
                    if blocking_robot:
                        # Get blocking robot's current node
                        blocking_current_node = None
                        if blocking_robot.current_pose:
                            blocking_current_node = self.path_planner.graph.get_nearest_waypoint(
                                blocking_robot.current_pose.position.x,
                                blocking_robot.current_pose.position.y
                            )

                        # Check if blocking robot has moved away from blocked nodes
                        if blocking_current_node and blocking_current_node not in wait_state.blocked_nodes:
                            logger.info(f"[COLLISION] {robot_id}: blocking robot {wait_state.waiting_for} "
                                       f"moved to {blocking_current_node}, attempting replan")

                            # Try to replan
                            if wait_state.original_goal:
                                new_path, success = self.collision_avoidance.handle_replan_trigger(
                                    robot_id, ReplanTrigger.ROBOT_MOVED
                                )
                                if success and new_path:
                                    logger.info(f"[COLLISION] {robot_id} path now clear, proceeding with route")
                                    robot.current_route = new_path
                                    robot.route_index = 0
                                    self._follow_waypoints(robot_id, new_path)

                # Check for pickup slot availability
                if wait_state.state == WaitState.WAITING_FOR_PICKUP:
                    position, rank = self.collision_avoidance.manage_pickup_queue(robot_id, "check")
                    if rank == 0:
                        # Pickup slot is now available
                        logger.info(f"[COLLISION] {robot_id} pickup slot available, proceeding")
                        new_path, success = self.collision_avoidance.handle_replan_trigger(
                            robot_id, ReplanTrigger.PICKUP_SLOT_AVAILABLE
                        )
                        if success and new_path:
                            robot.current_route = new_path
                            robot.route_index = 0
                            self._follow_waypoints(robot_id, new_path)

        # Log collision avoidance status periodically (every 25 checks = 5 seconds)
        if not hasattr(self, '_collision_check_count'):
            self._collision_check_count = 0
        self._collision_check_count += 1

        if self._collision_check_count % 25 == 0:
            status = self.collision_avoidance.get_collision_status_summary()
            if status['waiting_robots']:
                logger.info(f"[COLLISION] Status: {len(status['waiting_robots'])} robots waiting, "
                           f"{status['reserved_nodes_count']} nodes reserved")

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
        Handle RETRY operator command - retry failed navigation task using waypoint navigation

        Args:
            robot_id: Target robot ID
            order_id: Associated order ID (unused for retry)
            reason: Reason for retry
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found")
            return

        logger.info(f"[WAYPOINT NAV] Retrying navigation for robot {robot_id}: {reason}")

        # Get current target location and use waypoint navigation
        if robot.target_location:
            if robot.target_location in self.map_positions:
                # Use waypoint navigation to ensure robot follows defined paths
                self._navigate_robot_by_name(robot_id, robot.target_location)
                logger.info(f"[WAYPOINT NAV] Resent waypoint navigation to {robot.target_location}")
            else:
                logger.error(f"Target location {robot.target_location} not found in map positions")
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
    """FMS Node 진입점"""
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
