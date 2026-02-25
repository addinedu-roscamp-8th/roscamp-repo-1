"""
ROS 2 Bridge for Kitchmatic Main Server
Handles ROS 2 communication with FMS and Robot Arms
"""

import rclpy
from rclpy.node import Node
from fleet_interfaces.msg import (
    OrderRequest,
    CookingOrder,
    LoadingComplete,
    RobotStatus,
    FleetStatus,
    DeliveryComplete,
    PickupArrival,
    PrecisionParked,
    TableArrival
)
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Pose, Point, Quaternion
import logging
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ROSBridge(Node):
    """
    ROS 2 Bridge for Main Server
    Handles communication with FMS and Robot Arms via ROS 2 topics
    """

    def __init__(self, skip_mode: bool = False):
        """
        Initialize ROS Bridge

        Args:
            skip_mode: If True, enables skip mode for testing without external teams
        """
        super().__init__('main_server_bridge')

        self.skip_mode = skip_mode

        # Skip mode configuration
        self.precision_parking_delay = 2.0  # seconds
        self.food_loading_delay = 3.0  # seconds

        # Publishers
        self.order_request_pub = self.create_publisher(
            OrderRequest,
            '/fms/order_request',
            10
        )

        self.cooking_order_pub = self.create_publisher(
            CookingOrder,
            '/robot_arm/cooking_order',
            10
        )

        self.delivery_complete_pub = self.create_publisher(
            DeliveryComplete,
            '/fms/delivery_complete',
            10
        )

        self.precision_parked_pub = self.create_publisher(
            PrecisionParked,
            '/fms/precision_parked',
            10
        )

        # Subscribers
        self.loading_complete_sub = self.create_subscription(
            LoadingComplete,
            '/robot_arm/loading_complete',
            self.loading_complete_callback,
            10
        )

        self.fleet_status_sub = self.create_subscription(
            FleetStatus,
            '/fms/fleet_status',
            self.fleet_status_callback,
            10
        )

        self.pickup_arrival_sub = self.create_subscription(
            PickupArrival,
            '/fms/pickup_arrival',
            self.pickup_arrival_callback,
            10
        )

        self.table_arrival_sub = self.create_subscription(
            TableArrival,
            '/fms/table_arrival',
            self.table_arrival_callback,
            10
        )

        # Callback handlers (to be set by main_server_node)
        self.on_loading_complete = None
        self.on_fleet_status_update = None
        self.on_pickup_arrival = None
        self.on_table_arrival = None

        # Latest fleet status cache
        self.latest_fleet_status = None

        logger.info(f"ROS Bridge initialized (skip_mode={skip_mode})")

    def publish_order_request(self, order_id: str, menu_id: str, table_number: str,
                             quantity: int, sauce_type: str, voice_order: bool,
                             created_at: datetime):
        """
        Publish order request to FMS

        Args:
            order_id: Order UUID string
            menu_id: Menu ID (M001, M002, etc.)
            table_number: Table number (T01-T08)
            quantity: Order quantity
            sauce_type: Sauce type (mayo, mustard, ketchup)
            voice_order: Whether order was placed via voice
            created_at: Order creation timestamp
        """
        msg = OrderRequest()
        msg.order_id = order_id
        msg.menu_id = menu_id
        msg.table_number = table_number
        msg.quantity = quantity
        msg.sauce_type = sauce_type
        msg.voice_order = voice_order
        msg.created_at = self._datetime_to_ros_time(created_at)

        self.order_request_pub.publish(msg)
        logger.info(f"Published order request to FMS: {order_id}")

    def publish_cooking_order(self, order_id: str, menu_id: str, quantity: int,
                             sauce_type: str, assigned_robot_id: str):
        """
        Publish cooking order to Robot Arm team

        Args:
            order_id: Order UUID string
            menu_id: Menu ID (M001, M002)
            quantity: Order quantity
            sauce_type: Sauce type
            assigned_robot_id: Assigned serving robot ID (pinky1, pinky2, pinky3)
        """
        msg = CookingOrder()
        msg.order_id = order_id
        msg.menu_id = menu_id
        msg.quantity = quantity
        msg.sauce_type = sauce_type
        msg.assigned_robot_id = assigned_robot_id

        self.cooking_order_pub.publish(msg)
        logger.info(f"Published cooking order to Robot Arm: {order_id}")

    def publish_delivery_complete(self, order_id: str, table_number: str, received_at: datetime):
        """
        Publish delivery complete signal to FMS

        Args:
            order_id: Order UUID string
            table_number: Table number
            received_at: Delivery completion timestamp
        """
        msg = DeliveryComplete()
        msg.order_id = order_id
        msg.table_number = table_number
        msg.received_at = self._datetime_to_ros_time(received_at)

        self.delivery_complete_pub.publish(msg)
        logger.info(f"Published delivery complete to FMS: {order_id}")

    def loading_complete_callback(self, msg: LoadingComplete):
        """
        Handle LoadingComplete message from Robot Arm

        This is called when robot arm finishes cooking and loading food onto serving robot
        """
        logger.info(f"Received loading complete: order={msg.order_id}, success={msg.success}, robot={msg.robot_id}")

        if self.on_loading_complete:
            # Convert ROS time to datetime
            completed_at = self._ros_time_to_datetime(msg.completed_at)

            # Call handler
            self.on_loading_complete(
                order_id=msg.order_id,
                success=msg.success,
                robot_id=msg.robot_id,
                message=msg.message,
                completed_at=completed_at
            )

    def fleet_status_callback(self, msg: FleetStatus):
        """
        Handle FleetStatus message from FMS

        This provides overall fleet status updates
        """
        logger.debug("Received fleet status update from FMS")

        # Cache latest status
        self.latest_fleet_status = msg

        if self.on_fleet_status_update:
            # Convert to dict format for easier handling
            robots_status = []
            for robot in msg.robots:
                robots_status.append({
                    'robot_id': robot.robot_id,
                    'status': robot.status,
                    'current_pose': {
                        'position': {
                            'x': robot.current_pose.position.x,
                            'y': robot.current_pose.position.y,
                            'z': robot.current_pose.position.z
                        },
                        'orientation': {
                            'x': robot.current_pose.orientation.x,
                            'y': robot.current_pose.orientation.y,
                            'z': robot.current_pose.orientation.z,
                            'w': robot.current_pose.orientation.w
                        }
                    },
                    'battery_voltage': robot.battery_voltage,
                    'battery_present': robot.battery_present,
                    'timestamp': self._ros_time_to_datetime(robot.timestamp)
                })

            fleet_data = {
                'robots': robots_status,
                'pending_orders': msg.pending_orders,
                'active_orders': msg.active_orders,
                'timestamp': self._ros_time_to_datetime(msg.timestamp)
            }

            # Call handler
            self.on_fleet_status_update(fleet_data)

    def pickup_arrival_callback(self, msg: PickupArrival):
        """
        Handle PickupArrival message from FMS

        This is called when a robot arrives at point13 (kitchen pickup area)
        """
        logger.info(f"Received pickup arrival: robot={msg.robot_id}, order={msg.order_id}")

        if self.on_pickup_arrival:
            # Convert ROS time to datetime
            arrived_at = self._ros_time_to_datetime(msg.arrived_at)

            # Convert pose to dict
            current_pose = {
                'position': {
                    'x': msg.current_pose.position.x,
                    'y': msg.current_pose.position.y,
                    'z': msg.current_pose.position.z
                },
                'orientation': {
                    'x': msg.current_pose.orientation.x,
                    'y': msg.current_pose.orientation.y,
                    'z': msg.current_pose.orientation.z,
                    'w': msg.current_pose.orientation.w
                }
            }

            # Call handler
            self.on_pickup_arrival(
                robot_id=msg.robot_id,
                order_id=msg.order_id,
                current_pose=current_pose,
                arrived_at=arrived_at
            )

        # If skip mode enabled, automatically send precision_parked after delay
        if self.skip_mode:
            logger.info(f"Skip mode: Scheduling precision_parked for {msg.robot_id} in {self.precision_parking_delay}s")
            self.create_timer(
                self.precision_parking_delay,
                lambda: self._send_mock_precision_parked(msg.robot_id, msg.order_id, msg.current_pose)
            )

    def table_arrival_callback(self, msg: TableArrival):
        """
        Handle TableArrival message from FMS

        SC-183/321: This is called when a robot arrives at a table for delivery
        """
        logger.info(f"Received table arrival: robot={msg.robot_id}, order={msg.order_id}, table={msg.table_number}")

        if self.on_table_arrival:
            # Convert ROS time to datetime
            arrived_at = self._ros_time_to_datetime(msg.arrived_at)

            # Convert pose to dict
            current_pose = {
                'position': {
                    'x': msg.current_pose.position.x,
                    'y': msg.current_pose.position.y,
                    'z': msg.current_pose.position.z
                },
                'orientation': {
                    'x': msg.current_pose.orientation.x,
                    'y': msg.current_pose.orientation.y,
                    'z': msg.current_pose.orientation.z,
                    'w': msg.current_pose.orientation.w
                }
            }

            # Call handler
            self.on_table_arrival(
                robot_id=msg.robot_id,
                order_id=msg.order_id,
                table_number=msg.table_number,
                current_pose=current_pose,
                arrived_at=arrived_at
            )

    def _send_mock_precision_parked(self, robot_id: str, order_id: str, pose):
        """
        Send mock PrecisionParked message for skip mode testing

        Args:
            robot_id: Robot ID
            order_id: Order ID
            pose: Current pose
        """
        logger.info(f"Skip mode: Sending mock precision_parked for {robot_id}")

        msg = PrecisionParked()
        msg.robot_id = robot_id
        msg.order_id = order_id
        msg.success = True
        msg.final_pose = pose
        msg.message = "Mock precision parking completed (skip mode)"
        msg.completed_at = self._datetime_to_ros_time(datetime.utcnow())

        self.precision_parked_pub.publish(msg)
        logger.info(f"Published mock precision_parked: robot={robot_id}, order={order_id}")

    def get_latest_fleet_status(self):
        """
        Get latest cached fleet status

        Returns:
            FleetStatus message or None if no status received yet
        """
        return self.latest_fleet_status

    def _datetime_to_ros_time(self, dt: datetime) -> Time:
        """Convert Python datetime to ROS Time message"""
        timestamp = dt.timestamp()
        time_msg = Time()
        time_msg.sec = int(timestamp)
        time_msg.nanosec = int((timestamp - int(timestamp)) * 1e9)
        return time_msg

    def _ros_time_to_datetime(self, time_msg: Time) -> datetime:
        """Convert ROS Time message to Python datetime"""
        timestamp = time_msg.sec + time_msg.nanosec / 1e9
        return datetime.fromtimestamp(timestamp)

    def set_loading_complete_handler(self, handler: Callable):
        """
        Set callback handler for loading complete events

        Args:
            handler: Function with signature:
                     handler(order_id: str, success: bool, robot_id: str,
                            message: str, completed_at: datetime)
        """
        self.on_loading_complete = handler
        logger.info("Loading complete handler registered")

    def set_fleet_status_handler(self, handler: Callable):
        """
        Set callback handler for fleet status updates

        Args:
            handler: Function with signature:
                     handler(fleet_data: dict)
        """
        self.on_fleet_status_update = handler
        logger.info("Fleet status handler registered")

    def set_pickup_arrival_handler(self, handler: Callable):
        """
        Set callback handler for pickup arrival events

        Args:
            handler: Function with signature:
                     handler(robot_id: str, order_id: str,
                            current_pose: dict, arrived_at: datetime)
        """
        self.on_pickup_arrival = handler
        logger.info("Pickup arrival handler registered")

    def set_table_arrival_handler(self, handler: Callable):
        """
        Set callback handler for table arrival events

        SC-183/321: Called when robot arrives at table for delivery

        Args:
            handler: Function with signature:
                     handler(robot_id: str, order_id: str, table_number: str,
                            current_pose: dict, arrived_at: datetime)
        """
        self.on_table_arrival = handler
        logger.info("Table arrival handler registered")

    def publish_precision_parked(self, robot_id: str, order_id: str, success: bool,
                                 final_pose: dict, message: str = ""):
        """
        Publish PrecisionParked message to FMS

        Args:
            robot_id: Robot ID (pinky1/2/3)
            order_id: Order UUID string
            success: Whether precision parking succeeded
            final_pose: Final precise pose dict with position and orientation
            message: Optional error message if success=false
        """
        msg = PrecisionParked()
        msg.robot_id = robot_id
        msg.order_id = order_id
        msg.success = success
        msg.message = message
        msg.completed_at = self._datetime_to_ros_time(datetime.utcnow())

        # Convert pose dict to geometry_msgs/Pose
        from geometry_msgs.msg import Pose, Point, Quaternion
        pose_msg = Pose()
        pose_msg.position = Point(
            x=final_pose['position']['x'],
            y=final_pose['position']['y'],
            z=final_pose['position']['z']
        )
        pose_msg.orientation = Quaternion(
            x=final_pose['orientation']['x'],
            y=final_pose['orientation']['y'],
            z=final_pose['orientation']['z'],
            w=final_pose['orientation']['w']
        )
        msg.final_pose = pose_msg

        self.precision_parked_pub.publish(msg)
        logger.info(f"Published precision_parked: robot={robot_id}, order={order_id}, success={success}")


def spin_ros_bridge(bridge: ROSBridge):
    """
    Helper function to spin ROS bridge in separate thread

    Args:
        bridge: ROSBridge instance
    """
    try:
        rclpy.spin(bridge)
    except Exception as e:
        logger.error(f"ROS Bridge spin error: {e}")
