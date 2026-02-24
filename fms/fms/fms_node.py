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
    RobotArrival
)
from std_msgs.msg import Float32, Bool
from builtin_interfaces.msg import Time
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional

from .task_manager import TaskManager
from .fleet_controller import FleetController, RobotState
from .zone_manager import ZoneManager

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
    - Controls robots via: /{namespace}/navigate_to_pose action
    - Monitors robots via: /{namespace}/pose, /{namespace}/battery/* topics
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

        # TODO: Load robot configurations from config file
        robot_configs = [
            {'robot_id': 'pinky1', 'namespace': '/pinky1'},
            {'robot_id': 'pinky2', 'namespace': '/pinky2'},
            {'robot_id': 'pinky3', 'namespace': '/pinky3'}
        ]

        # Initialize core components
        self.task_manager = TaskManager()
        self.fleet_controller = FleetController(robot_configs)
        self.zone_manager = ZoneManager()

        # Navigation action clients for each robot
        self.nav_clients = {}
        # Initial pose publishers for AMCL
        self.initialpose_pubs = {}

        for config in robot_configs:
            robot_id = config['robot_id']
            namespace = config['namespace']

            # Navigation action client
            action_name = f"{namespace}/navigate_to_pose"
            self.nav_clients[robot_id] = ActionClient(self, NavigateToPose, action_name)
            logger.info(f"Created navigation client for {robot_id}: {action_name}")

            # Initial pose publisher for AMCL
            initialpose_topic = f"{namespace}/initialpose"
            self.initialpose_pubs[robot_id] = self.create_publisher(
                PoseWithCovarianceStamped, initialpose_topic, 10)
            logger.info(f"Created initialpose publisher for {robot_id}: {initialpose_topic}")

        # Publishers
        self.fleet_status_pub = self.create_publisher(
            FleetStatus,
            '/fms/fleet_status',
            10
        )

        # Robot arrival publisher (notifies Main Server when robot reaches table)
        self.robot_arrival_pub = self.create_publisher(
            RobotArrival,
            '/fms/robot_arrival',
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

        # Robot monitoring subscribers
        self._setup_robot_monitoring(robot_configs)

        # Fleet status publisher timer (publish every 1 second)
        self.status_timer = self.create_timer(1.0, self.publish_fleet_status)

        # Task assignment timer (check for pending tasks every 0.5 seconds)
        self.assignment_timer = self.create_timer(0.5, self.process_pending_tasks)

        # Load map positions from config file
        self.map_positions = self._load_map_positions()

        # Set initial poses for robots after a short delay (wait for AMCL to start)
        self.create_timer(3.0, self._set_initial_poses_once)
        self._initial_pose_set = False

        logger.info("Fleet Management System initialized successfully")

    def _setup_robot_monitoring(self, robot_configs: List[Dict]):
        """
        Setup subscribers for monitoring robot status

        Args:
            robot_configs: List of robot configurations
        """
        for config in robot_configs:
            robot_id = config['robot_id']
            namespace = config['namespace']

            # Subscribe to pose
            self.create_subscription(
                Pose,
                f"{namespace}/pose",
                lambda msg, rid=robot_id: self.robot_pose_callback(rid, msg),
                10
            )

            # Subscribe to battery voltage
            self.create_subscription(
                Float32,
                f"{namespace}/battery/voltage",
                lambda msg, rid=robot_id: self.robot_battery_voltage_callback(rid, msg),
                10
            )

            # Subscribe to battery present
            self.create_subscription(
                Bool,
                f"{namespace}/battery/present",
                lambda msg, rid=robot_id: self.robot_battery_present_callback(rid, msg),
                10
            )

            logger.info(f"Setup monitoring for robot {robot_id}")

    def _load_map_positions(self) -> Dict[str, Pose]:
        """
        Load map positions from fms_config.yaml

        Returns:
            Dictionary mapping location names to Pose objects
        """
        import yaml
        import os
        from ament_index_python.packages import get_package_share_directory

        positions = {}

        try:
            # Try to load from config file
            pkg_dir = get_package_share_directory('fms')
            config_file = os.path.join(pkg_dir, 'config', 'fms_config.yaml')

            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f)

                if 'positions' in config:
                    for name, pos in config['positions'].items():
                        x = pos.get('x', 0.0)
                        y = pos.get('y', 0.0)
                        theta = pos.get('theta', 0.0)
                        positions[name] = self._create_pose(x, y, theta)
                        logger.debug(f"Loaded position {name}: ({x}, {y}, {theta})")

                    logger.info(f"Loaded {len(positions)} positions from fms_config.yaml")
                else:
                    logger.warning("No 'positions' section found in fms_config.yaml")
            else:
                logger.warning(f"Config file not found: {config_file}")

        except Exception as e:
            logger.error(f"Error loading config file: {e}")

        # Fallback to default positions if config loading failed
        if not positions:
            logger.warning("Using fallback positions (config loading failed)")
            positions = {
                'pickup_spot': self._create_pose(0.47, 0.63, 0.0),
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

    def _set_initial_poses_once(self):
        """
        Set initial poses for all robots at their parking spots (one-time call)
        This is called after AMCL has started to set the initial localization
        """
        if self._initial_pose_set:
            return

        self._initial_pose_set = True
        logger.info("Setting initial poses for all robots...")

        robot_spots = {
            'pinky1': 'pinky1_spot',
            'pinky2': 'pinky2_spot',
            'pinky3': 'pinky3_spot',
        }

        for robot_id, spot_name in robot_spots.items():
            spot_pose = self.map_positions.get(spot_name)
            if spot_pose:
                self.set_initial_pose(robot_id, spot_pose)
                logger.info(f"Set initial pose for {robot_id} at {spot_name}")

    def set_initial_pose(self, robot_id: str, pose: Pose):
        """
        Set initial pose for AMCL localization

        Args:
            robot_id: Robot ID
            pose: Initial pose
        """
        pub = self.initialpose_pubs.get(robot_id)
        if not pub:
            logger.warning(f"No initialpose publisher for robot {robot_id}")
            return

        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose = pose

        # Set covariance (small values for good initial estimate)
        # [x, y, z, roll, pitch, yaw] variance on diagonal
        msg.pose.covariance = [
            0.01, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.01, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.04
        ]

        pub.publish(msg)
        logger.info(f"Published initial pose for {robot_id}: ({pose.position.x:.3f}, {pose.position.y:.3f})")

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
    # Callbacks
    # ========================================

    def order_request_callback(self, msg: OrderRequest):
        """
        Handle order request from Main Server

        Args:
            msg: OrderRequest message
        """
        logger.info(f"Received order request: order_id={msg.order_id}, table={msg.table_number}")

        # Create task
        task = self.task_manager.create_task(
            order_id=msg.order_id,
            menu_id=msg.menu_id,
            table_number=msg.table_number,
            quantity=msg.quantity,
            sauce_type=msg.sauce_type,
            voice_order=msg.voice_order
        )

        logger.info(f"Created task {task.task_id} for order {msg.order_id}")

    def delivery_complete_callback(self, msg: DeliveryComplete):
        """
        Handle delivery complete signal from Main Server

        Args:
            msg: DeliveryComplete message
        """
        logger.info(f"Received delivery complete: order_id={msg.order_id}, table={msg.table_number}")

        # Find task by order ID
        task = self.task_manager.get_task_by_order_id(msg.order_id)
        if task and task.assigned_robot:
            # Complete task
            self.task_manager.complete_task(task.task_id)

            # Update robot status - start returning home
            self.fleet_controller.robot_complete_delivery(task.assigned_robot)

            # Send robot back to parking spot
            self._send_robot_to_parking(task.assigned_robot)

    def robot_pose_callback(self, robot_id: str, msg: Pose):
        """
        Handle robot pose update

        Args:
            robot_id: Robot ID
            msg: Pose message
        """
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
        if self.task_manager.get_pending_count() == 0:
            return

        # Get available robot
        robot = self.fleet_controller.get_available_robot()
        if not robot:
            return

        # Assign task
        task = self.task_manager.assign_task(robot.robot_id)
        if task:
            # Update fleet controller
            self.fleet_controller.assign_task_to_robot(
                robot.robot_id,
                task.task_id,
                task.order_id
            )

            # Send robot to pickup spot
            self._send_robot_to_pickup(robot.robot_id)

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

        # Wait for action server
        if not nav_client.wait_for_server(timeout_sec=5.0):
            logger.error(f"Navigation action server not available for robot {robot_id}")
            return

        # Create goal
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = PoseStamped()
        goal_msg.pose.header.frame_id = 'map'
        goal_msg.pose.header.stamp = self.get_clock().now().to_msg()
        goal_msg.pose.pose = goal_pose

        logger.info(f"Sending nav goal to {robot_id}: ({goal_pose.position.x:.3f}, {goal_pose.position.y:.3f})")

        # Send goal with callbacks
        send_goal_future = nav_client.send_goal_async(
            goal_msg,
            feedback_callback=lambda fb: self._nav_feedback_callback(robot_id, fb)
        )
        send_goal_future.add_done_callback(
            lambda future: self._nav_goal_response_callback(robot_id, future)
        )

    def _nav_goal_response_callback(self, robot_id: str, future):
        """Handle navigation goal response"""
        goal_handle = future.result()
        if not goal_handle.accepted:
            logger.warning(f"Navigation goal rejected for robot {robot_id}")
            return

        logger.info(f"Navigation goal accepted for robot {robot_id}")

        # Get result
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            lambda future: self._nav_result_callback(robot_id, future)
        )

    def _nav_result_callback(self, robot_id: str, future):
        """Handle navigation result"""
        result = future.result()
        status = result.status

        # Status codes: 2=CANCELED, 4=SUCCEEDED, 5=ABORTED
        if status == 4:  # SUCCEEDED
            logger.info(f"Navigation succeeded for robot {robot_id}")
            # Robot reached destination - let _check_navigation_status handle state transition
        elif status == 5:  # ABORTED
            logger.error(f"Navigation aborted for robot {robot_id}")
            self.fleet_controller.robot_error(robot_id, "Navigation aborted")
        elif status == 2:  # CANCELED
            logger.warning(f"Navigation canceled for robot {robot_id}")
        else:
            logger.warning(f"Navigation finished with status {status} for robot {robot_id}")

    def _nav_feedback_callback(self, robot_id: str, feedback_msg):
        """Handle navigation feedback"""
        feedback = feedback_msg.feedback
        # Current pose during navigation
        current_pose = feedback.current_pose.pose
        logger.debug(f"Robot {robot_id} at ({current_pose.position.x:.2f}, {current_pose.position.y:.2f})")

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
                # Reached pickup spot
                self.fleet_controller.robot_reached_pickup(robot_id)
                logger.info(f"Robot {robot_id} reached pickup spot")

                # 로봇팔 스킵 모드: 3초 후 자동으로 테이블로 이동
                if self.skip_robot_arm:
                    logger.info(f"[SKIP_ARM] 3초 후 자동으로 food_loaded 처리...")
                    # 일회성 타이머 - threading 사용
                    import threading
                    threading.Timer(3.0, lambda: self._auto_food_loaded(robot_id)).start()
                else:
                    logger.info(f"Waiting for food loading from robot arm...")

            elif robot.status == RobotState.STATUS_MOVING_TO_TABLE:
                # Reached table
                self.fleet_controller.robot_reached_table(robot_id)
                logger.info(f"Robot {robot_id} reached table, waiting for customer")

                # Publish robot arrival notification to Main Server
                self._publish_robot_arrival(robot_id)

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
        fleet_status.pending_orders = self.task_manager.get_pending_count()
        fleet_status.active_orders = self.task_manager.get_active_count()
        fleet_status.timestamp = self._datetime_to_ros_time(datetime.utcnow())

        self.fleet_status_pub.publish(fleet_status)

    def _datetime_to_ros_time(self, dt: datetime) -> Time:
        """Convert Python datetime to ROS Time message"""
        timestamp = dt.timestamp()
        time_msg = Time()
        time_msg.sec = int(timestamp)
        time_msg.nanosec = int((timestamp - int(timestamp)) * 1e9)
        return time_msg

    def _publish_robot_arrival(self, robot_id: str):
        """
        Publish robot arrival notification when robot reaches table

        Args:
            robot_id: Robot ID
        """
        # Find current task for this robot
        task = None
        for t in self.task_manager.assigned_tasks.values():
            if t.assigned_robot == robot_id:
                task = t
                break

        if not task:
            logger.warning(f"No task found for robot {robot_id} when publishing arrival")
            return

        # Create and publish RobotArrival message
        arrival_msg = RobotArrival()
        arrival_msg.robot_id = robot_id
        arrival_msg.order_id = task.order_id
        arrival_msg.table_number = task.table_number
        arrival_msg.arrived_at = self.get_clock().now().to_msg()

        self.robot_arrival_pub.publish(arrival_msg)
        logger.info(f"Published robot arrival: {robot_id} at {task.table_number} for order {task.order_id}")

    # ========================================
    # Auto Food Loading (Skip Robot Arm Mode)
    # ========================================

    def _auto_food_loaded(self, robot_id: str):
        """
        로봇팔 스킵 모드에서 자동으로 음식 적재 완료 처리

        Args:
            robot_id: Robot ID
        """
        robot = self.fleet_controller.get_robot(robot_id)
        if not robot:
            return

        # 현재 task 찾기
        task = None
        for t in self.task_manager.assigned_tasks.values():
            if t.assigned_robot == robot_id:
                task = t
                break

        if task:
            logger.info(f"[SKIP_ARM] Auto food loaded for {robot_id}, order {task.order_id}")
            self.notify_food_loaded(robot_id, task.order_id)
        else:
            logger.warning(f"[SKIP_ARM] No task found for robot {robot_id}")

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

            # Send robot to table
            self._send_robot_to_table(robot_id, task.table_number)


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
