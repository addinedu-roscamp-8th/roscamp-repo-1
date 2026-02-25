"""
Unit tests for ZoneManager pre-reservation system

Tests the zone pre-reservation functionality including:
- Zone reservation and occupancy transitions
- Reservation expiration and cleanup
- Path conflict detection
- Multi-robot zone coordination
"""

import unittest
import time
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add fms package to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import zone manager directly to avoid ROS dependencies
import importlib.util
spec = importlib.util.spec_from_file_location(
    "zone_manager",
    str(Path(__file__).parent.parent / "fms" / "zone_manager.py")
)
zone_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zone_manager_module)
Zone = zone_manager_module.Zone
ZoneManager = zone_manager_module.ZoneManager


class TestZone(unittest.TestCase):
    """Test Zone class"""

    def test_zone_creation(self):
        """Test zone creation with default parameters"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        self.assertEqual(zone.zone_id, 'zone_test')
        self.assertEqual(zone.center_x, 1.0)
        self.assertEqual(zone.center_y, 2.0)
        self.assertEqual(zone.radius, 0.1)
        self.assertIsNone(zone.occupied_by)
        self.assertIsNone(zone.reserved_by)
        self.assertEqual(zone.reservation_timeout, 30.0)

    def test_zone_creation_with_timeout(self):
        """Test zone creation with custom timeout"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1, reservation_timeout=60.0)
        self.assertEqual(zone.reservation_timeout, 60.0)

    def test_zone_available(self):
        """Test zone availability check"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        self.assertTrue(zone.is_available())

    def test_zone_reserve(self):
        """Test zone reservation"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        result = zone.reserve('robot1')
        self.assertTrue(result)
        self.assertEqual(zone.reserved_by, 'robot1')
        self.assertIsNotNone(zone.reserved_at)
        self.assertFalse(zone.is_available())

    def test_zone_reserve_occupied(self):
        """Test reservation of occupied zone fails"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        zone.reserve('robot1')
        zone.occupy('robot1')
        result = zone.reserve('robot2')
        self.assertFalse(result)

    def test_zone_occupy_from_reserved(self):
        """Test zone occupation after reservation"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        zone.reserve('robot1')
        zone.occupy('robot1')
        self.assertEqual(zone.occupied_by, 'robot1')
        self.assertIsNone(zone.reserved_by)

    def test_zone_release(self):
        """Test zone release"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        zone.reserve('robot1')
        zone.release('robot1')
        self.assertIsNone(zone.reserved_by)
        self.assertTrue(zone.is_available())

    def test_zone_reservation_expired(self):
        """Test reservation expiration detection"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1, reservation_timeout=0.1)
        zone.reserve('robot1')
        time.sleep(0.2)
        self.assertTrue(zone.is_reservation_expired())

    def test_zone_reservation_not_expired(self):
        """Test reservation not expired"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1, reservation_timeout=10.0)
        zone.reserve('robot1')
        self.assertFalse(zone.is_reservation_expired())

    def test_zone_contains_point(self):
        """Test point containment"""
        zone = Zone('zone_test', 1.0, 2.0, 0.1)
        # Point inside zone
        self.assertTrue(zone.contains_point(1.0, 2.0))
        self.assertTrue(zone.contains_point(1.05, 2.0))
        # Point outside zone
        self.assertFalse(zone.contains_point(2.0, 2.0))


class TestZoneManager(unittest.TestCase):
    """Test ZoneManager class"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = ZoneManager()

    def test_initialization(self):
        """Test zone manager initialization"""
        self.assertGreater(len(self.manager.zones), 0)
        self.assertIn('zone_pickup', self.manager.zones)
        self.assertIn('zone_table1', self.manager.zones)
        self.assertIn('zone_parking1', self.manager.zones)

    def test_reserve_zone(self):
        """Test zone reservation"""
        result = self.manager.reserve_zone('robot1', 'zone_pickup')
        self.assertTrue(result)
        self.assertEqual(
            self.manager.zones['zone_pickup'].reserved_by,
            'robot1'
        )

    def test_reserve_zone_not_found(self):
        """Test reservation of non-existent zone"""
        result = self.manager.reserve_zone('robot1', 'zone_invalid')
        self.assertFalse(result)

    def test_reserve_zone_already_reserved(self):
        """Test reservation of already reserved zone fails"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        result = self.manager.reserve_zone('robot2', 'zone_pickup')
        self.assertFalse(result)

    def test_occupy_zone(self):
        """Test zone occupation"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        result = self.manager.occupy_zone('robot1', 'zone_pickup')
        self.assertTrue(result)
        self.assertEqual(
            self.manager.zones['zone_pickup'].occupied_by,
            'robot1'
        )
        self.assertIsNone(self.manager.zones['zone_pickup'].reserved_by)

    def test_leave_zone(self):
        """Test leaving zone"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.manager.occupy_zone('robot1', 'zone_pickup')
        result = self.manager.leave_zone('robot1', 'zone_pickup')
        self.assertTrue(result)
        self.assertIsNone(self.manager.zones['zone_pickup'].occupied_by)

    def test_release_reservation(self):
        """Test releasing reservation"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        result = self.manager.release_reservation('robot1', 'zone_pickup')
        self.assertTrue(result)
        self.assertIsNone(self.manager.zones['zone_pickup'].reserved_by)

    def test_is_zone_available(self):
        """Test zone availability check"""
        self.assertTrue(self.manager.is_zone_available('zone_pickup'))
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.assertFalse(self.manager.is_zone_available('zone_pickup'))

    def test_get_zone_status(self):
        """Test getting zone status"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        status = self.manager.get_zone_status('zone_pickup')
        self.assertIsNotNone(status)
        self.assertEqual(status['zone_id'], 'zone_pickup')
        self.assertEqual(status['reserved_by'], 'robot1')
        self.assertFalse(status['available'])

    def test_check_path_conflicts(self):
        """Test path conflict detection"""
        # Reserve zone for robot1
        self.manager.reserve_zone('robot1', 'zone_pickup')

        # Check path for robot2 that includes reserved zone
        conflicts = self.manager.check_path_conflicts(
            'robot2',
            ['zone_table1', 'zone_pickup', 'zone_table2']
        )
        self.assertIn('zone_pickup', conflicts)

    def test_check_path_no_conflicts(self):
        """Test path with no conflicts"""
        # Reserve zone for robot1
        self.manager.reserve_zone('robot1', 'zone_pickup')

        # Check path for robot1 that includes its own zone
        conflicts = self.manager.check_path_conflicts(
            'robot1',
            ['zone_table1', 'zone_pickup', 'zone_table2']
        )
        self.assertNotIn('zone_pickup', conflicts)

    def test_cleanup_expired_reservations(self):
        """Test cleanup of expired reservations"""
        # Create zone with short timeout
        zone = Zone('zone_test', 1.0, 2.0, 0.1, reservation_timeout=0.1)
        self.manager.zones['zone_test'] = zone

        # Reserve zone
        zone.reserve('robot1')
        self.assertEqual(zone.reserved_by, 'robot1')

        # Wait for reservation to expire
        time.sleep(0.2)

        # Cleanup
        cleaned = self.manager.cleanup_expired_reservations()
        self.assertEqual(cleaned, 1)
        self.assertIsNone(zone.reserved_by)

    def test_get_robot_reserved_zones(self):
        """Test getting robot's reserved zones"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.manager.reserve_zone('robot1', 'zone_table1')

        reserved = self.manager.get_robot_reserved_zones('robot1')
        self.assertEqual(len(reserved), 2)
        self.assertIn('zone_pickup', reserved)
        self.assertIn('zone_table1', reserved)

    def test_get_robot_occupied_zones(self):
        """Test getting robot's occupied zones"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.manager.occupy_zone('robot1', 'zone_pickup')
        self.manager.reserve_zone('robot1', 'zone_table1')
        self.manager.occupy_zone('robot1', 'zone_table1')

        occupied = self.manager.get_robot_occupied_zones('robot1')
        self.assertEqual(len(occupied), 2)
        self.assertIn('zone_pickup', occupied)
        self.assertIn('zone_table1', occupied)

    def test_clear_robot(self):
        """Test clearing all robot zones"""
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.manager.occupy_zone('robot1', 'zone_table1')

        self.manager.clear_robot('robot1')

        self.assertIsNone(self.manager.zones['zone_pickup'].reserved_by)
        self.assertIsNone(self.manager.zones['zone_table1'].occupied_by)

    def test_multi_robot_coordination(self):
        """Test multi-robot zone coordination"""
        # Robot 1 reserves and occupies pickup
        self.assertTrue(self.manager.reserve_zone('robot1', 'zone_pickup'))
        self.assertTrue(self.manager.occupy_zone('robot1', 'zone_pickup'))

        # Robot 2 tries to reserve pickup (should fail)
        self.assertFalse(self.manager.reserve_zone('robot2', 'zone_pickup'))

        # Robot 1 leaves pickup
        self.assertTrue(self.manager.leave_zone('robot1', 'zone_pickup'))

        # Now robot 2 can reserve pickup
        self.assertTrue(self.manager.reserve_zone('robot2', 'zone_pickup'))

    def test_get_zone_by_location(self):
        """Test location name to zone ID mapping"""
        zone_id = self.manager.get_zone_by_location('pickup_spot')
        self.assertEqual(zone_id, 'zone_pickup')

        zone_id = self.manager.get_zone_by_location('table1')
        self.assertEqual(zone_id, 'zone_table1')

        zone_id = self.manager.get_zone_by_location('pinky1_spot')
        self.assertEqual(zone_id, 'zone_parking1')

    def test_collision_risk_check(self):
        """Test collision risk detection"""
        # Robot1 occupies zone_pickup
        self.manager.reserve_zone('robot1', 'zone_pickup')
        self.manager.occupy_zone('robot1', 'zone_pickup')

        # Check collision risk for robot2
        has_risk = self.manager.check_collision_risk('robot2', 'zone_pickup')
        self.assertTrue(has_risk)

        # Check collision risk for robot1 (no risk, it owns the zone)
        has_risk = self.manager.check_collision_risk('robot1', 'zone_pickup')
        self.assertFalse(has_risk)


class TestDeliveryFlowScenario(unittest.TestCase):
    """Test realistic delivery flow scenarios"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = ZoneManager()

    def test_delivery_flow_single_robot(self):
        """Test complete delivery flow for single robot"""
        robot_id = 'robot1'

        # Step 1: Reserve pickup zone and navigate
        self.assertTrue(
            self.manager.reserve_zone(robot_id, 'zone_pickup')
        )

        # Step 2: Arrive at pickup and occupy zone
        self.assertTrue(
            self.manager.occupy_zone(robot_id, 'zone_pickup')
        )

        # Step 3: Reserve table1 for delivery
        self.assertTrue(
            self.manager.reserve_zone(robot_id, 'zone_table1')
        )

        # Step 4: Leave pickup
        self.assertTrue(
            self.manager.leave_zone(robot_id, 'zone_pickup')
        )

        # Step 5: Arrive at table and occupy zone
        self.assertTrue(
            self.manager.occupy_zone(robot_id, 'zone_table1')
        )

        # Step 6: Leave table
        self.assertTrue(
            self.manager.leave_zone(robot_id, 'zone_table1')
        )

        # Step 7: Return to parking
        self.assertTrue(
            self.manager.reserve_zone(robot_id, 'zone_parking1')
        )
        self.assertTrue(
            self.manager.occupy_zone(robot_id, 'zone_parking1')
        )

    def test_delivery_flow_multi_robot(self):
        """Test delivery flow with multiple robots"""
        # Robot1 picks up order for table1
        self.assertTrue(
            self.manager.reserve_zone('robot1', 'zone_pickup')
        )
        self.assertTrue(
            self.manager.occupy_zone('robot1', 'zone_pickup')
        )

        # Robot2 cannot use pickup while robot1 is there
        self.assertFalse(
            self.manager.reserve_zone('robot2', 'zone_pickup')
        )

        # Robot1 reserves table1
        self.assertTrue(
            self.manager.reserve_zone('robot1', 'zone_table1')
        )

        # Robot1 leaves pickup
        self.assertTrue(
            self.manager.leave_zone('robot1', 'zone_pickup')
        )

        # Now robot2 can use pickup
        self.assertTrue(
            self.manager.reserve_zone('robot2', 'zone_pickup')
        )
        self.assertTrue(
            self.manager.occupy_zone('robot2', 'zone_pickup')
        )

        # Robot1 can still use table1 (it has reservation)
        self.assertTrue(
            self.manager.occupy_zone('robot1', 'zone_table1')
        )

        # Robot2 cannot use table1
        self.assertFalse(
            self.manager.reserve_zone('robot2', 'zone_table1')
        )


if __name__ == '__main__':
    unittest.main()
