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

    def __init__(self, skip_mode: bool = False):
        """
        Initialize Main Server components

        Args:
            skip_mode: If True, enables skip mode for testing without external teams
        """
        self.running = False
        self.skip_mode = skip_mode

        # Load database configuration from environment or config file
        db_config = self._load_db_config()

        # TCP Server configuration
        tcp_config = {
            'host': '0.0.0.0',  # Listen on all interfaces
            'port': 9999
        }

        # Initialize components
        logger.info(f"Initializing Main Server components (skip_mode={skip_mode})...")

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
        self.ros_bridge = ROSBridge(skip_mode=skip_mode)
        self._register_ros_handlers()

        # Start ROS bridge in separate thread
        self.ros_thread = threading.Thread(target=spin_ros_bridge, args=(self.ros_bridge,), daemon=True)
        self.ros_thread.start()

        logger.info("Main Server initialized successfully")

    def _load_db_config(self) -> Dict[str, Any]:
        """
        Load database configuration from environment variables or config file

        Priority:
        1. Environment variables (DB_HOST, DB_PORT, etc.)
        2. database.env file
        3. Default values

        Returns:
            Database configuration dict
        """
        import os
        from pathlib import Path

        # Try to load from database.env file
        config_dir = Path(__file__).parent.parent / 'config'
        env_file = config_dir / 'database.env'

        if env_file.exists():
            logger.info(f"Loading database config from {env_file}")
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        os.environ[key] = value

        # Read from environment with defaults
        db_config = {
            'db_host': os.getenv('DB_HOST', 'localhost'),
            'db_port': int(os.getenv('DB_PORT', '5432')),
            'db_name': os.getenv('DB_NAME', 'kitchmatic'),
            'db_user': os.getenv('DB_USER', 'kitchmatic_user'),
            'db_password': os.getenv('DB_PASSWORD', 'your_password_here')
        }

        logger.info(f"Database config: host={db_config['db_host']}, port={db_config['db_port']}, db={db_config['db_name']}")
        return db_config

    def _register_tcp_handlers(self):
        """Register TCP message handlers"""
        self.tcp_server.register_handler('order_request', self.handle_order_request)
        self.tcp_server.register_handler('order_status_query', self.handle_order_status_query)
        self.tcp_server.register_handler('fleet_status_query', self.handle_fleet_status_query)
        self.tcp_server.register_handler('delivery_complete', self.handle_delivery_complete)
        # Customer GUI compatibility handlers
        self.tcp_server.register_handler('get_menus', self.handle_get_menus)
        self.tcp_server.register_handler('submit_order', self.handle_submit_order)

    def _register_ros_handlers(self):
        """Register ROS message handlers"""
        self.ros_bridge.set_loading_complete_handler(self.handle_loading_complete)
        self.ros_bridge.set_fleet_status_handler(self.handle_fleet_status_update)
        self.ros_bridge.set_pickup_arrival_handler(self.handle_pickup_arrival)
        self.ros_bridge.set_table_arrival_handler(self.handle_table_arrival)

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

    def handle_get_menus(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get menus request from Customer GUI.
        DB menus 테이블: id, name, price, category, available, description, image_url, created_at.

        Returns:
            {'menus': [{'id', 'name', 'price', 'category', 'available', 'description', 'image_url'}, ...]}
        """
        logger.info(f"Received get menus request: {data}")

        try:
            menus = self.db.get_available_menus()
            menu_list = []
            for menu in menus:
                menu_list.append({
                    'id': menu.id,
                    'name': menu.name,
                    'price': menu.price,
                    'category': menu.category or '',
                    'available': menu.available,
                    'description': menu.description or '',
                    'image_url': menu.image_url or '',
                })

            logger.info(f"Returning {len(menu_list)} menus from DB")
            return {'menus': menu_list}

        except Exception as e:
            logger.warning(f"DB error, returning mock menus: {e}")
            mock_menus = [
                {'id': 'M001', 'name': '햄치즈샌드위치', 'price': 5000, 'description': '', 'image_url': '', 'available': True, 'category': '샌드위치'},
                {'id': 'M002', 'name': '머쉬룸샌드위치', 'price': 5500, 'description': '', 'image_url': '', 'available': True, 'category': '샌드위치'},
                {'id': 'M003', 'name': '올인원샌드위치', 'price': 6500, 'description': '', 'image_url': '', 'available': True, 'category': '샌드위치'},
            ]
            return {'menus': mock_menus}

    def handle_submit_order(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle submit order request from Customer GUI

        Args:
            data: {
                'order': {
                    'table_number': int,
                    'items': [
                        {
                            'menu_id': str,
                            'menu_name': str,
                            'price': int,
                            'quantity': int
                        },
                        ...
                    ],
                    'total_price': int
                }
            }

        Returns:
            {
                'order_id': str,
                'message': str
            }
        """
        logger.info(f"Received submit order request: {data}")

        order_data = data.get('order', data)  # Support both nested and flat structure
        table_number = order_data.get('table_number')
        items = order_data.get('items', [])

        if not items:
            return {
                'status': 'error',
                'message': '주문 항목이 없습니다.'
            }

        first_item = items[0]
        order_id = None

        # Try to create order in database
        try:
            order_id = self.db.create_order(
                table_number=str(table_number),
                menu_id=first_item.get('menu_id'),
                quantity=first_item.get('quantity', 1),
                voice_order=False
            )
            if order_id:
                self.db.update_order_status(str(order_id), 'CONFIRMED')
        except Exception as e:
            logger.warning(f"DB error, using mock order ID: {e}")

        # Generate mock order ID if DB failed
        if not order_id:
            import uuid
            order_id = str(uuid.uuid4())[:8].upper()
            logger.info(f"Using mock order ID: {order_id}")

        # Send order to FMS via ROS (this is the important part)
        try:
            self.ros_bridge.publish_order_request(
                order_id=str(order_id),
                menu_id=first_item.get('menu_id'),
                table_number=str(table_number),
                quantity=first_item.get('quantity', 1),
                sauce_type='mayo',
                voice_order=False,
                created_at=datetime.utcnow()
            )
            logger.info(f"Order {order_id} sent to FMS for table {table_number}")
        except Exception as e:
            logger.error(f"Failed to send order to FMS: {e}")
            return {
                'status': 'error',
                'message': f'FMS 전송 실패: {str(e)}'
            }

        return {
            'status': 'success',
            'order_id': str(order_id),
            'message': '주문이 접수되었습니다.'
        }

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

            # Convert datetime objects to ISO strings for JSON serialization
            serializable_data = {
                'robots': [],
                'pending_orders': fleet_data.get('pending_orders', 0),
                'active_orders': fleet_data.get('active_orders', 0),
                'timestamp': fleet_data['timestamp'].isoformat() if isinstance(fleet_data.get('timestamp'), datetime) else str(fleet_data.get('timestamp', ''))
            }
            for robot in fleet_data['robots']:
                robot_data = {
                    'robot_id': robot['robot_id'],
                    'status': robot['status'],
                    'current_pose': robot.get('current_pose', {}),
                    'battery_voltage': robot.get('battery_voltage', 0),
                    'battery_present': robot.get('battery_present', False),
                    'timestamp': robot['timestamp'].isoformat() if isinstance(robot.get('timestamp'), datetime) else str(robot.get('timestamp', ''))
                }
                serializable_data['robots'].append(robot_data)

            # Broadcast to Admin GUI clients
            self.tcp_server.broadcast({
                'type': 'fleet_status_update',
                'data': serializable_data
            })

        except Exception as e:
            logger.error(f"Error handling fleet status update: {e}")

    def handle_pickup_arrival(self, robot_id: str, order_id: str,
                             current_pose: Dict[str, Any], arrived_at: datetime):
        """
        Handle pickup arrival notification from FMS

        This is called when robot arrives at point13 (kitchen pickup area).
        Flow:
        1. Update order status to AT_POINT13
        2. Send CookingOrder to Robot Arm team
        3. (Skip mode) PrecisionParked will be auto-sent by ros_bridge

        Args:
            robot_id: Robot that arrived (pinky1/2/3)
            order_id: Associated order UUID
            current_pose: Current robot pose at point13
            arrived_at: Arrival timestamp
        """
        logger.info(f"Pickup arrival: robot={robot_id}, order={order_id}")

        try:
            # Update order status to AT_POINT13
            self.db.update_order_status(order_id, 'AT_POINT13')

            # Get order details
            order = self.db.get_order(order_id)
            if not order:
                logger.error(f"Order {order_id} not found in database")
                return

            # Send cooking order to Robot Arm team
            self.ros_bridge.publish_cooking_order(
                order_id=order_id,
                menu_id=order.menu_id,
                quantity=order.quantity,
                sauce_type=getattr(order, 'sauce_type', 'mayo'),  # Default to mayo if not set
                assigned_robot_id=robot_id
            )

            # Broadcast status update to TCP clients
            self.tcp_server.broadcast({
                'type': 'order_status_update',
                'data': {
                    'order_id': order_id,
                    'status': 'AT_POINT13',
                    'table_number': order.table_number,
                    'robot_id': robot_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
            })

            logger.info(f"Order {order_id} marked as AT_POINT13, cooking order sent to robot arm")

            # Note: If skip_mode is enabled, ros_bridge will automatically send
            # mock precision_parked message after configured delay

        except Exception as e:
            logger.error(f"Error handling pickup arrival: {e}")

    def handle_table_arrival(self, robot_id: str, order_id: str, table_number: str,
                            current_pose: Dict[str, Any], arrived_at: datetime):
        """
        Handle table arrival notification from FMS

        SC-183/321: This is called when robot arrives at table for delivery.
        Flow:
        1. Update order status to AT_TABLE
        2. Broadcast delivery notification to kiosk/GUI (with TCP)
        3. Wait for delivery_complete signal from customer GUI

        Args:
            robot_id: Robot that arrived (pinky1/2/3)
            order_id: Associated order UUID
            table_number: Target table number
            current_pose: Current robot pose at table
            arrived_at: Arrival timestamp
        """
        logger.info(f"Table arrival: robot={robot_id}, order={order_id}, table={table_number}")

        # Try to update DB status (but don't fail if DB is down)
        try:
            self.db.update_order_status(order_id, 'AT_TABLE')
        except Exception as e:
            logger.warning(f"DB update failed (continuing): {e}")

        # Broadcast delivery notification to TCP clients (kiosk/GUI)
        # This triggers the customer GUI to show delivery notification
        # This MUST happen regardless of DB status
        try:
            self.tcp_server.broadcast({
                'type': 'delivery_notification',
                'data': {
                    'order_id': order_id,
                    'status': 'AT_TABLE',
                    'table_number': table_number,
                    'robot_id': robot_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
            })
            logger.info(f"Order {order_id} marked as AT_TABLE, delivery notification sent to kiosk")
        except Exception as e:
            logger.error(f"Error sending delivery notification: {e}")

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
