#!/usr/bin/env python3
"""
Zone Manager Usage Examples

This script demonstrates how to use the ZoneManager for:
1. Single robot delivery flow
2. Multi-robot coordination
3. Path validation
4. Cleanup and error handling
"""

import sys
import time
from pathlib import Path

# Add fms package to path
fms_path = Path(__file__).parent.parent
sys.path.insert(0, str(fms_path))

# Import zone manager directly to avoid ROS dependencies
import importlib.util
spec = importlib.util.spec_from_file_location(
    "zone_manager",
    str(fms_path / "fms" / "zone_manager.py")
)
zone_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zone_manager_module)
ZoneManager = zone_manager_module.ZoneManager
Zone = zone_manager_module.Zone


def example_1_single_robot_delivery():
    """Example 1: Complete delivery flow for a single robot"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Single Robot Delivery Flow")
    print("="*60)

    manager = ZoneManager()
    robot_id = 'pinky1'
    table_number = 1

    print(f"\n[Step 1] Reserving pickup zone for {robot_id}...")
    if manager.reserve_zone(robot_id, 'zone_pickup'):
        print("  SUCCESS: Pickup zone reserved")
        status = manager.get_zone_status('zone_pickup')
        print(f"  Status: {status}")
    else:
        print("  FAILED: Pickup zone not available")
        return

    print(f"\n[Step 2] Robot arrives at pickup, occupying zone...")
    manager.occupy_zone(robot_id, 'zone_pickup')
    status = manager.get_zone_status('zone_pickup')
    print(f"  Occupied by: {status['occupied_by']}")
    print(f"  Reserved by: {status['reserved_by']}")

    print(f"\n[Step 3] Reserving table{table_number} zone for delivery...")
    table_zone = manager.get_zone_by_location(f'table{table_number}')
    if manager.reserve_zone(robot_id, table_zone):
        print(f"  SUCCESS: {table_zone} reserved")
    else:
        print(f"  FAILED: {table_zone} not available")

    print(f"\n[Step 4] Robot leaves pickup zone...")
    manager.leave_zone(robot_id, 'zone_pickup')
    status = manager.get_zone_status('zone_pickup')
    print(f"  Pickup available: {status['available']}")

    print(f"\n[Step 5] Robot arrives at table, occupying delivery zone...")
    manager.occupy_zone(robot_id, table_zone)
    status = manager.get_zone_status(table_zone)
    print(f"  Occupied by: {status['occupied_by']}")

    print(f"\n[Step 6] Customer confirms delivery...")
    manager.leave_zone(robot_id, table_zone)
    status = manager.get_zone_status(table_zone)
    print(f"  Table available: {status['available']}")

    print(f"\n[Step 7] Robot returns to parking spot...")
    parking_zone = manager.get_zone_by_location(f'{robot_id}_spot')
    manager.reserve_zone(robot_id, parking_zone)
    manager.occupy_zone(robot_id, parking_zone)
    print(f"  Robot parked at {parking_zone}")

    print("\n[Complete] Delivery flow finished successfully!")


def example_2_multi_robot_coordination():
    """Example 2: Two robots coordinating deliveries"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Multi-Robot Coordination")
    print("="*60)

    manager = ZoneManager()
    robot1 = 'pinky1'
    robot2 = 'pinky2'

    print(f"\n[Robot 1] Attempting to reserve pickup zone...")
    if manager.reserve_zone(robot1, 'zone_pickup'):
        print(f"  SUCCESS: {robot1} reserved pickup")

    print(f"\n[Robot 2] Attempting to reserve pickup zone...")
    if manager.reserve_zone(robot2, 'zone_pickup'):
        print(f"  SUCCESS: {robot2} reserved pickup (shouldn't happen!)")
    else:
        print(f"  BLOCKED: Pickup already reserved by {robot1}")

    print(f"\n[Robot 1] Occupying pickup zone...")
    manager.occupy_zone(robot1, 'zone_pickup')

    print(f"\n[Robot 1] Reserving table1 for delivery...")
    manager.reserve_zone(robot1, 'zone_table1')

    print(f"\n[Robot 1] Leaving pickup zone...")
    manager.leave_zone(robot1, 'zone_pickup')

    print(f"\n[Robot 2] Now can reserve pickup zone...")
    if manager.reserve_zone(robot2, 'zone_pickup'):
        print(f"  SUCCESS: {robot2} now has pickup reserved")
        manager.occupy_zone(robot2, 'zone_pickup')

    print(f"\n[Status Check]")
    print(f"  Robot 1 reserved zones: {manager.get_robot_reserved_zones(robot1)}")
    print(f"  Robot 1 occupied zones: {manager.get_robot_occupied_zones(robot1)}")
    print(f"  Robot 2 reserved zones: {manager.get_robot_reserved_zones(robot2)}")
    print(f"  Robot 2 occupied zones: {manager.get_robot_occupied_zones(robot2)}")


def example_3_path_validation():
    """Example 3: Validating paths before navigation"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Path Validation and Conflict Detection")
    print("="*60)

    manager = ZoneManager()
    robot1 = 'pinky1'
    robot2 = 'pinky2'

    # Robot 1 reserves and occupies some zones
    print(f"\n[Robot 1] Setting up delivery path...")
    path1 = ['zone_parking1', 'zone_point1', 'zone_pickup', 'zone_table3']
    for zone_id in path1:
        manager.reserve_zone(robot1, zone_id)
    manager.occupy_zone(robot1, 'zone_parking1')
    manager.occupy_zone(robot1, 'zone_point1')

    # Robot 2 tries to plan a path
    print(f"\n[Robot 2] Planning delivery path...")
    path2 = ['zone_parking2', 'zone_point1', 'zone_pickup', 'zone_table1']
    print(f"  Planned path: {path2}")

    # Check for conflicts
    print(f"\n[Robot 2] Checking for conflicts...")
    conflicts = manager.check_path_conflicts(robot2, path2)
    if conflicts:
        print(f"  CONFLICT DETECTED: {conflicts}")
        print(f"  Path is blocked! Suggest alternative route.")
    else:
        print(f"  PATH CLEAR: No conflicts detected")

    # Show detailed zone status
    print(f"\n[Zone Status]")
    for zone_id in ['zone_point1', 'zone_pickup']:
        status = manager.get_zone_status(zone_id)
        print(f"  {zone_id}:")
        print(f"    Occupied by: {status['occupied_by']}")
        print(f"    Reserved by: {status['reserved_by']}")
        print(f"    Available: {status['available']}")


def example_4_expiration_and_cleanup():
    """Example 4: Zone reservation expiration and cleanup"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Reservation Expiration and Cleanup")
    print("="*60)

    # Create zone with short timeout for demo
    manager = ZoneManager()

    print(f"\n[Setup] Creating zone with 0.5 second timeout...")
    test_zone = Zone('zone_test', 1.5, 0.5, 0.1, reservation_timeout=0.5)
    manager.zones['zone_test'] = test_zone

    print(f"\n[Step 1] Robot reserves zone...")
    manager.reserve_zone('robot1', 'zone_test')
    status = manager.get_zone_status('zone_test')
    print(f"  Reserved by: {status['reserved_by']}")
    print(f"  Expired: {status['is_reservation_expired']}")

    print(f"\n[Step 2] Waiting 0.6 seconds for reservation to expire...")
    time.sleep(0.6)

    status = manager.get_zone_status('zone_test')
    print(f"  Reserved by: {status['reserved_by']}")
    print(f"  Expired: {status['is_reservation_expired']}")
    print(f"  Reservation age: {status['reservation_age_sec']:.2f}s")

    print(f"\n[Step 3] Running cleanup...")
    cleaned = manager.cleanup_expired_reservations()
    print(f"  Cleaned {cleaned} expired reservations")

    status = manager.get_zone_status('zone_test')
    print(f"  After cleanup - Reserved by: {status['reserved_by']}")
    print(f"  Zone available: {status['available']}")

    print(f"\n[Step 4] Other robots can now use zone...")
    if manager.reserve_zone('robot2', 'zone_test'):
        print(f"  SUCCESS: robot2 can now reserve zone")


def example_5_emergency_cleanup():
    """Example 5: Emergency cleanup when robot goes offline"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Emergency Cleanup for Offline Robot")
    print("="*60)

    manager = ZoneManager()
    robot_id = 'pinky1'

    print(f"\n[Setup] Robot has multiple zones reserved/occupied...")
    manager.reserve_zone(robot_id, 'zone_pickup')
    manager.occupy_zone(robot_id, 'zone_table1')
    manager.occupy_zone(robot_id, 'zone_table2')
    manager.reserve_zone(robot_id, 'zone_parking1')

    reserved = manager.get_robot_reserved_zones(robot_id)
    occupied = manager.get_robot_occupied_zones(robot_id)
    print(f"  Reserved zones: {reserved}")
    print(f"  Occupied zones: {occupied}")

    print(f"\n[Alert] Robot {robot_id} goes offline (network failure)!")
    print(f"  Performing emergency cleanup...")
    manager.clear_robot(robot_id)

    reserved = manager.get_robot_reserved_zones(robot_id)
    occupied = manager.get_robot_occupied_zones(robot_id)
    print(f"  After cleanup - Reserved zones: {reserved}")
    print(f"  After cleanup - Occupied zones: {occupied}")

    print(f"\n[Status] All zones now available for other robots")
    print(f"  zone_pickup available: {manager.is_zone_available('zone_pickup')}")
    print(f"  zone_table1 available: {manager.is_zone_available('zone_table1')}")
    print(f"  zone_table2 available: {manager.is_zone_available('zone_table2')}")


def example_6_zone_status_monitoring():
    """Example 6: Monitoring all zones status"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Zone Status Monitoring")
    print("="*60)

    manager = ZoneManager()

    # Set up some activity
    manager.reserve_zone('pinky1', 'zone_pickup')
    manager.occupy_zone('pinky1', 'zone_table1')
    manager.occupy_zone('pinky2', 'zone_parking2')

    print(f"\n[All Zones Status]")
    print(f"{'Zone ID':<20} {'Occupied':<12} {'Reserved':<12} {'Available':<10}")
    print("-" * 55)

    for status in manager.get_all_zones_status():
        zone_id = status['zone_id']
        occupied = status['occupied_by'] or 'None'
        reserved = status['reserved_by'] or 'None'
        available = 'YES' if status['available'] else 'NO'
        print(f"{zone_id:<20} {occupied:<12} {reserved:<12} {available:<10}")

    print(f"\n[Summary]")
    all_status = manager.get_all_zones_status()
    occupied_count = sum(1 for s in all_status if s['occupied_by'])
    reserved_count = sum(1 for s in all_status if s['reserved_by'])
    available_count = sum(1 for s in all_status if s['available'])

    print(f"  Total zones: {len(all_status)}")
    print(f"  Occupied: {occupied_count}")
    print(f"  Reserved: {reserved_count}")
    print(f"  Available: {available_count}")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("ZONE MANAGER USAGE EXAMPLES")
    print("=" * 60)

    try:
        example_1_single_robot_delivery()
        example_2_multi_robot_coordination()
        example_3_path_validation()
        example_4_expiration_and_cleanup()
        example_5_emergency_cleanup()
        example_6_zone_status_monitoring()

        print("\n" + "=" * 60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
