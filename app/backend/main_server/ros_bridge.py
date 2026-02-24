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
    RobotArrival
)
from builtin_interfaces.msg import Time
import logging
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ROSBridge(Node):
    """
    ROS 2 Bridge for Main Server
    Handles communication with FMS and Robot Arms via ROS 2 topics
    """

    def __init__(self):
        super().__init__('main_server_bridge')

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

        # Subscribe to robot arrival notifications from FMS
        self.robot_arrival_sub = self.create_subscription(
            RobotArrival,
            '/fms/robot_arrival',
            self.robot_arrival_callback,
            10
        )

        # Callback handlers (to be set by main_server_node)
        self.on_loading_complete = None
        self.on_fleet_status_update = None
        self.on_robot_arrival = None

        # Latest fleet status cache
        self.latest_fleet_status = None

        logger.info("ROS Bridge initialized")

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

    def set_robot_arrival_handler(self, handler: Callable):
        """
        Set callback handler for robot arrival notifications

        Args:
            handler: Function with signature:
                     handler(order_id: str, robot_id: str, table_number: str, arrived_at: datetime)
        """
        self.on_robot_arrival = handler
        logger.info("Robot arrival handler registered")

    def robot_arrival_callback(self, msg: RobotArrival):
        """
        Handle RobotArrival message from FMS

        This is called when a robot reaches the customer's table.
        The Main Server should notify the Customer GUI to display delivery notification.
        """
        logger.info(f"Received robot arrival: robot={msg.robot_id}, order={msg.order_id}, table={msg.table_number}")

        if self.on_robot_arrival:
            # Convert ROS time to datetime
            arrived_at = self._ros_time_to_datetime(msg.arrived_at)

            # Call handler
            self.on_robot_arrival(
                order_id=msg.order_id,
                robot_id=msg.robot_id,
                table_number=msg.table_number,
                arrived_at=arrived_at
            )


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
