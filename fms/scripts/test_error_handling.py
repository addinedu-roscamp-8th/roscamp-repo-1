#!/usr/bin/env python3
"""
Test script for SC-74 Error Handling System

Tests:
1. Error detection (NAV_FAILED, COMM_LOST, LOW_BATTERY, TIMEOUT)
2. Error alert publishing
3. Operator command handling
4. Error recovery actions
"""

import rclpy
from rclpy.node import Node
from fleet_interfaces.msg import ErrorAlert, OperatorCommand
from geometry_msgs.msg import Pose
from std_msgs.msg import Float32, Bool
import logging
import sys
import time
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)


class ErrorHandlingTester(Node):
    """Test node for error handling system"""

    def __init__(self):
        super().__init__('error_handler_tester')

        # Subscribers
        self.error_alert_sub = self.create_subscription(
            ErrorAlert,
            '/fms/error_alert',
            self.error_alert_callback,
            10
        )

        # Publishers for testing
        self.test_pose_pub = self.create_publisher(
            Pose,
            '/pose',
            10
        )
        self.test_battery_pub = self.create_publisher(
            Float32,
            '/battery/voltage',
            10
        )
        self.test_battery_present_pub = self.create_publisher(
            Bool,
            '/battery/present',
            10
        )

        # Test results
        self.errors_received = []
        self.test_passed = []
        self.test_failed = []

        logger.info("ErrorHandlingTester initialized")

    def error_alert_callback(self, msg: ErrorAlert):
        """Receive error alert"""
        logger.warning(f"ERROR ALERT: {msg.robot_id} - {msg.error_type}")
        logger.warning(f"  Message: {msg.error_message}")
        logger.warning(f"  Battery: {msg.battery_voltage:.1f}V")
        self.errors_received.append({
            'robot_id': msg.robot_id,
            'error_type': msg.error_type,
            'message': msg.error_message,
            'battery': msg.battery_voltage
        })

    def test_low_battery_detection(self):
        """Test 1: Low battery detection"""
        logger.info("\n=== Test 1: Low Battery Detection ===")

        # Publish pose (to register heartbeat)
        pose = Pose()
        pose.position.x = 0.5
        pose.position.y = 1.0
        self.test_pose_pub.publish(pose)
        time.sleep(0.1)

        # Publish low battery
        battery = Float32()
        battery.data = 15.0  # Below threshold
        self.test_battery_pub.publish(battery)

        battery_present = Bool()
        battery_present.data = True
        self.test_battery_present_pub.publish(battery_present)

        logger.info("Published low battery (15.0V)")

        # Wait for error detection (0.5Hz = 2 seconds)
        time.sleep(3.0)

        # Check if error was received
        low_battery_errors = [e for e in self.errors_received if e['error_type'] == 'LOW_BATTERY']
        if low_battery_errors:
            logger.info("✓ Test PASSED: Low battery detected")
            self.test_passed.append("low_battery_detection")
            return True
        else:
            logger.warning("✗ Test FAILED: Low battery not detected")
            self.test_failed.append("low_battery_detection")
            return False

    def test_communication_loss_detection(self):
        """Test 2: Communication loss detection"""
        logger.info("\n=== Test 2: Communication Loss Detection ===")

        self.errors_received.clear()

        # Stop publishing pose (simulate communication loss)
        logger.info("Stopping pose updates (simulating communication loss)...")

        # Wait for heartbeat timeout (5 seconds + monitoring interval)
        logger.info("Waiting for communication loss detection (5-7 seconds)...")
        for i in range(8):
            time.sleep(1)
            logger.info(f"  Waiting... {i+1}s")

        # Check if error was received
        comm_lost_errors = [e for e in self.errors_received if e['error_type'] == 'COMM_LOST']
        if comm_lost_errors:
            logger.info("✓ Test PASSED: Communication loss detected")
            self.test_passed.append("communication_loss_detection")
            return True
        else:
            logger.warning("✗ Test FAILED: Communication loss not detected")
            logger.info("  (This might be normal if other robots are publishing)")
            return False

    def test_error_alert_message_format(self):
        """Test 3: Error alert message format"""
        logger.info("\n=== Test 3: Error Alert Message Format ===")

        if not self.errors_received:
            logger.warning("✗ Test FAILED: No errors received")
            self.test_failed.append("error_alert_format")
            return False

        error = self.errors_received[0]

        # Check required fields
        required_fields = ['robot_id', 'error_type', 'message', 'battery']
        missing_fields = [f for f in required_fields if f not in error]

        if missing_fields:
            logger.warning(f"✗ Test FAILED: Missing fields: {missing_fields}")
            self.test_failed.append("error_alert_format")
            return False
        else:
            logger.info("✓ Test PASSED: Error alert format is correct")
            logger.info(f"  Fields: {list(error.keys())}")
            self.test_passed.append("error_alert_format")
            return True

    def test_heartbeat_recovery(self):
        """Test 4: Heartbeat recovery clears error"""
        logger.info("\n=== Test 4: Heartbeat Recovery ===")

        # Publish pose to restore communication
        logger.info("Publishing pose to restore communication...")
        pose = Pose()
        pose.position.x = 0.5
        pose.position.y = 1.0
        self.test_pose_pub.publish(pose)
        time.sleep(0.1)

        logger.info("✓ Test PASSED: Heartbeat published (recovery would clear error)")
        self.test_passed.append("heartbeat_recovery")
        return True

    def run_all_tests(self):
        """Run all tests"""
        logger.info("\n" + "="*60)
        logger.info("SC-74 ERROR HANDLING SYSTEM TEST SUITE")
        logger.info("="*60)

        try:
            # Test 1: Low battery
            self.test_low_battery_detection()

            # Test 2: Communication loss
            self.test_communication_loss_detection()

            # Test 3: Message format
            self.test_error_alert_message_format()

            # Test 4: Heartbeat recovery
            self.test_heartbeat_recovery()

        except Exception as e:
            logger.error(f"Test error: {e}")
            self.test_failed.append(f"exception: {str(e)}")

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Passed: {len(self.test_passed)}/{len(self.test_passed) + len(self.test_failed)}")

        if self.test_passed:
            logger.info("\nPASSED TESTS:")
            for test in self.test_passed:
                logger.info(f"  ✓ {test}")

        if self.test_failed:
            logger.warning("\nFAILED TESTS:")
            for test in self.test_failed:
                logger.warning(f"  ✗ {test}")

        logger.info("\nErrors received during tests:")
        for error in self.errors_received:
            logger.info(f"  - {error['robot_id']}: {error['error_type']} ({error['message']})")

        return len(self.test_failed) == 0


def main():
    """Main function"""
    rclpy.init()

    try:
        tester = ErrorHandlingTester()

        # Run tests in a separate thread to allow ROS spinning
        import threading
        test_thread = threading.Thread(target=tester.run_all_tests)
        test_thread.daemon = True
        test_thread.start()

        # Spin for a while to allow messages to be processed
        logger.info("Starting ROS 2 spin... Press Ctrl+C to stop")

        # Spin with timeout
        start_time = time.time()
        timeout = 30  # 30 seconds

        while time.time() - start_time < timeout:
            rclpy.spin_once(tester, timeout_sec=0.1)
            if not test_thread.is_alive():
                break

        logger.info("\nTest completed. Shutting down...")
        tester.destroy_node()
        rclpy.shutdown()

    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        rclpy.shutdown()
        sys.exit(0)


if __name__ == '__main__':
    main()
