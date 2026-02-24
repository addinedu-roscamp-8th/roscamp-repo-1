"""
Main Server Node for Kitchmatic Fleet Management System
Integrates Database, TCP Server, and ROS 2 Bridge
"""

import rclpy
from rclpy.executors import MultiThreadedExecutor
import threading
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Any

from .database_manager import DatabaseManager
from .tcp_server import TCPServer
from .ros_bridge import ROSBridge, spin_ros_bridge

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class MainServer:
    """
    Main Server for Kitchmatic Fleet Management System

    Architecture:
    - Database Manager: PostgreSQL connection and ORM operations
    - TCP Server: Communication with Kiosks and Admin GUI
    - ROS Bridge: Communication with FMS and Robot Arms

    Message Flow:
    1. Kiosk -> TCP -> Main Server -> ROS -> FMS
    2. FMS -> ROS -> Main Server -> Database
    3. Robot Arm -> ROS -> Main Server -> Database
    4. Main Server -> TCP -> Admin GUI (status updates)
    """

    def __init__(self):
        """Initialize Main Server components"""
        self.running = False

        # TODO: Load these configurations from config file or environment variables
        # Database configuration
        db_config = {
            'db_host': 'localhost',  # TODO: Set database server IP
            'db_port': 5432,
            'db_name': 'kitchmatic',
            'db_user': 'kitchmatic_user',
            'db_password': 'your_password_here'  # TODO: Set secure password
        }

        # TCP Server configuration
        tcp_config = {
            'host': '0.0.0.0',  # Listen on all interfaces
            'port': 9999  # TODO: Configure port if needed
        }

        # Initialize components
        logger.info("Initializing Main Server components...")

        # 1. Database Manager
        self.db = DatabaseManager(**db_config)
        if not self.db.connect():
            logger.error("Failed to initialize database connection")
            sys.exit(1)

        # 2. TCP Server
        self.tcp_server = TCPServer(**tcp_config)
        self._register_tcp_handlers()
        if not self.tcp_server.start():
            logger.error("Failed to start TCP server")
            sys.exit(1)

        # 3. ROS Bridge
        rclpy.init()
        self.ros_bridge = ROSBridge()
        self._register_ros_handlers()

        # Start ROS bridge in separate thread
        self.ros_thread = threading.Thread(target=spin_ros_bridge, args=(self.ros_bridge,), daemon=True)
        self.ros_thread.start()

        logger.info("Main Server initialized successfully")

    def _register_tcp_handlers(self):
        """Register TCP message handlers"""
        self.tcp_server.register_handler('order_request', self.handle_order_request)
        self.tcp_server.register_handler('order_status_query', self.handle_order_status_query)
        self.tcp_server.register_handler('fleet_status_query', self.handle_fleet_status_query)
        self.tcp_server.register_handler('delivery_complete', self.handle_delivery_complete)

    def _register_ros_handlers(self):
        """Register ROS message handlers"""
        self.ros_bridge.set_loading_complete_handler(self.handle_loading_complete)
        self.ros_bridge.set_fleet_status_handler(self.handle_fleet_status_update)
        self.ros_bridge.set_robot_arrival_handler(self.handle_robot_arrival)

    # ========================================
    # TCP Message Handlers (from Kiosk/Admin GUI)
    # ========================================

    def handle_order_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle order request from Kiosk

        Args:
            data: {
                'table_number': str,
                'menu_id': str,
                'quantity': int,
                'sauce_type': str,
                'voice_order': bool
            }

        Returns:
            {
                'order_id': str,
                'estimated_time': int (seconds)
            }
        """
        logger.info(f"Received order request: {data}")

        try:
            # Validate menu
            menu = self.db.get_menu(data['menu_id'])
            if not menu or not menu.available:
                raise Exception(f"Menu {data['menu_id']} not available")

            # Create order in database
            order_id = self.db.create_order(
                table_number=data['table_number'],
                menu_id=data['menu_id'],
                quantity=data.get('quantity', 1),
                voice_order=data.get('voice_order', False)
            )

            if not order_id:
                raise Exception("Failed to create order in database")

            # Update order status to CONFIRMED
            self.db.update_order_status(str(order_id), 'CONFIRMED')

            # Send order to FMS via ROS
            self.ros_bridge.publish_order_request(
                order_id=str(order_id),
                menu_id=data['menu_id'],
                table_number=data['table_number'],
                quantity=data.get('quantity', 1),
                sauce_type=data.get('sauce_type', 'mayo'),
                voice_order=data.get('voice_order', False),
                created_at=datetime.utcnow()
            )

            # Broadcast order status update to all TCP clients
            self.tcp_server.broadcast({
                'type': 'order_status_update',
                'data': {
                    'order_id': str(order_id),
                    'status': 'CONFIRMED',
                    'table_number': data['table_number'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

            # Estimate cooking time (TODO: Calculate based on queue and recipe)
            estimated_time = 120  # 2 minutes default

            return {
                'order_id': str(order_id),
                'estimated_time': estimated_time
            }

        except Exception as e:
            logger.error(f"Error handling order request: {e}")
            raise

    def handle_order_status_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle order status query from Kiosk or Admin GUI

        Args:
            data: {
                'order_id': str
            }

        Returns:
            {
                'order_id': str,
                'status': str,
                'table_number': str,
                'menu_id': str,
                'created_at': str,
                'updated_at': str
            }
        """
        logger.debug(f"Received order status query: {data}")

        try:
            order = self.db.get_order(data['order_id'])
            if not order:
                raise Exception(f"Order {data['order_id']} not found")

            return {
                'order_id': str(order.id),
                'status': order.status,
                'table_number': order.table_number,
                'menu_id': order.menu_id,
                'quantity': order.quantity,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            }

        except Exception as e:
            logger.error(f"Error handling order status query: {e}")
            raise

    def handle_fleet_status_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle fleet status query from Admin GUI

        Returns:
            {
                'robots': [
                    {
                        'robot_id': str,
                        'status': str,
                        'battery_voltage': float,
                        'battery_present': bool
                    },
                    ...
                ],
                'pending_orders': int,
                'active_orders': int
            }
        """
        logger.debug("Received fleet status query")

        try:
            # Get latest fleet status from ROS bridge cache
            fleet_status = self.ros_bridge.get_latest_fleet_status()

            if fleet_status:
                robots = []
                for robot in fleet_status.robots:
                    robots.append({
                        'robot_id': robot.robot_id,
                        'status': robot.status,
                        'battery_voltage': robot.battery_voltage,
                        'battery_present': robot.battery_present
                    })

                return {
                    'robots': robots,
                    'pending_orders': fleet_status.pending_orders,
                    'active_orders': fleet_status.active_orders
                }
            else:
                # No fleet status received yet, return empty
                return {
                    'robots': [],
                    'pending_orders': 0,
                    'active_orders': 0
                }

        except Exception as e:
            logger.error(f"Error handling fleet status query: {e}")
            raise

    def handle_delivery_complete(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle delivery complete signal from Kiosk

        Args:
            data: {
                'order_id': str,
                'table_number': str
            }

        Returns:
            {
                'message': str
            }
        """
        logger.info(f"Received delivery complete: {data}")

        try:
            # Update order status to COMPLETED in database
            self.db.update_order_status(data['order_id'], 'COMPLETED')

            # Publish delivery complete to FMS via ROS
            self.ros_bridge.publish_delivery_complete(
                order_id=data['order_id'],
                table_number=data['table_number'],
                received_at=datetime.utcnow()
            )

            # Broadcast order status update to all TCP clients
            self.tcp_server.broadcast({
                'type': 'order_status_update',
                'data': {
                    'order_id': data['order_id'],
                    'status': 'COMPLETED',
                    'table_number': data['table_number'],
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

            return {
                'message': 'Order completed successfully'
            }

        except Exception as e:
            logger.error(f"Error handling delivery complete: {e}")
            raise

    # ========================================
    # ROS Message Handlers (from FMS/Robot Arms)
    # ========================================

    def handle_loading_complete(self, order_id: str, success: bool, robot_id: str,
                                message: str, completed_at: datetime):
        """
        Handle loading complete signal from Robot Arm

        This is called when robot arm finishes cooking and loading food onto serving robot
        """
        logger.info(f"Loading complete: order={order_id}, success={success}, robot={robot_id}")

        try:
            if success:
                # Update order status to READY in database
                self.db.update_order_status(order_id, 'READY')

                # Get order details
                order = self.db.get_order(order_id)

                # Broadcast order status update to all TCP clients
                if order:
                    self.tcp_server.broadcast({
                        'type': 'order_status_update',
                        'data': {
                            'order_id': str(order_id),
                            'status': 'READY',
                            'table_number': order.table_number,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    })
            else:
                # Cooking failed, update status to HALTED
                logger.error(f"Cooking failed for order {order_id}: {message}")
                self.db.update_order_status(order_id, 'HALTED')

                # Get order details
                order = self.db.get_order(order_id)

                # Broadcast error to all TCP clients
                if order:
                    self.tcp_server.broadcast({
                        'type': 'order_status_update',
                        'data': {
                            'order_id': str(order_id),
                            'status': 'HALTED',
                            'table_number': order.table_number,
                            'error_message': message,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    })

        except Exception as e:
            logger.error(f"Error handling loading complete: {e}")

    def handle_fleet_status_update(self, fleet_data: Dict[str, Any]):
        """
        Handle fleet status update from FMS

        This is automatically broadcast to Admin GUI clients
        """
        logger.debug("Processing fleet status update")

        try:
            # Update robot status in database
            for robot in fleet_data['robots']:
                self.db.update_robot_status(
                    robot_name=robot['robot_id'],
                    status=robot['status']
                )

            # Broadcast to Admin GUI clients
            self.tcp_server.broadcast({
                'type': 'fleet_status_update',
                'data': fleet_data
            })

        except Exception as e:
            logger.error(f"Error handling fleet status update: {e}")

    def handle_robot_arrival(self, order_id: str, robot_id: str, table_number: str,
                            arrived_at: datetime):
        """
        Handle robot arrival notification from FMS

        This is called when a robot reaches the customer's table.
        Broadcasts 'delivery_notification' to Customer GUI so it can display
        the delivery confirmation screen.
        """
        logger.info(f"Robot arrival: robot={robot_id}, order={order_id}, table={table_number}")

        try:
            # Update order status to DELIVERED in database
            self.db.update_order_status(order_id, 'DELIVERED')

            # Get order details for more context
            order = self.db.get_order(order_id)

            # Broadcast delivery notification to all TCP clients (Customer GUI)
            # Customer GUI will filter by table_number to show only relevant notifications
            self.tcp_server.broadcast({
                'type': 'delivery_notification',
                'data': {
                    'order_id': order_id,
                    'robot_id': robot_id,
                    'table_number': table_number,
                    'menu_id': order.menu_id if order else None,
                    'arrived_at': arrived_at.isoformat(),
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

            logger.info(f"Broadcast delivery notification for order {order_id} at {table_number}")

        except Exception as e:
            logger.error(f"Error handling robot arrival: {e}")

    # ========================================
    # Server Control
    # ========================================

    def run(self):
        """Run main server"""
        self.running = True
        logger.info("Main Server is running...")

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Keep main thread alive
        try:
            while self.running:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")

        self.shutdown()

    def shutdown(self):
        """Shutdown main server"""
        logger.info("Shutting down Main Server...")

        self.running = False

        # Stop TCP server
        if self.tcp_server:
            self.tcp_server.stop()

        # Stop ROS bridge
        if self.ros_bridge:
            self.ros_bridge.destroy_node()

        # Close database connection
        if self.db:
            self.db.close()

        # Shutdown ROS
        rclpy.shutdown()

        logger.info("Main Server shutdown complete")

    def _signal_handler(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {signum}")
        self.shutdown()
        sys.exit(0)


def main():
    """Entry point for Main Server"""
    try:
        server = MainServer()
        server.run()
    except Exception as e:
        logger.error(f"Main Server error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
