# Zone Manager Pre-Reservation System

## Quick Start

The Zone Manager implements a comprehensive collision avoidance system with pre-reservation for multi-robot coordination in the Kitchmatics FMS.

### Basic Usage

```python
from fms.zone_manager import ZoneManager

# Initialize manager (loads zones from config)
manager = ZoneManager()

# Reserve a zone before entering
manager.reserve_zone('pinky1', 'zone_pickup')

# Occupy zone when robot enters
manager.occupy_zone('pinky1', 'zone_pickup')

# Leave zone when robot exits
manager.leave_zone('pinky1', 'zone_pickup')

# Check if zone is available
if manager.is_zone_available('zone_table1'):
    manager.reserve_zone('pinky1', 'zone_table1')
```

## Core Features

### 1. Pre-Reservation System

Robots reserve zones BEFORE navigating to guarantee exclusive access.

**Benefits:**
- Prevents collisions between multiple robots
- Ensures zones are available when robot arrives
- Reservation expires after 30 seconds (configurable)
- Other robots cannot block reserved zones

### 2. Three-State Zone Management

```
AVAILABLE → RESERVED → OCCUPIED → AVAILABLE
                ↓
           EXPIRED
```

**Available:** Zone is free, any robot can reserve it

**Reserved:** Zone is promised to a specific robot (up to 30s timeout)

**Occupied:** Robot physically occupies the zone

**Expired:** Reservation timeout elapsed (auto-cleanup needed)

### 3. Conflict Detection

Check if planned path has conflicts:

```python
path_zones = ['zone_parking1', 'zone_point1', 'zone_pickup']
conflicts = manager.check_path_conflicts('pinky1', path_zones)

if conflicts:
    print(f"Path blocked: {conflicts}")
    # Re-plan or wait
else:
    # Reserve and navigate path
    for zone_id in path_zones:
        manager.reserve_zone('pinky1', zone_id)
```

### 4. Periodic Cleanup

Expired reservations must be cleaned periodically:

```python
# Call every 5 seconds in main FMS loop
cleaned = manager.cleanup_expired_reservations()
if cleaned > 0:
    logger.info(f"Cleaned {cleaned} expired zones")
```

## API Methods

### Reservation Operations

| Method | Purpose | Returns |
|--------|---------|---------|
| `reserve_zone(robot_id, zone_id)` | Reserve zone for robot | bool |
| `release_reservation(robot_id, zone_id)` | Cancel reservation | bool |
| `occupy_zone(robot_id, zone_id)` | Mark zone as occupied | bool |
| `leave_zone(robot_id, zone_id)` | Release occupied zone | bool |

### Query Operations

| Method | Purpose | Returns |
|--------|---------|---------|
| `is_zone_available(zone_id)` | Check if zone can be reserved | bool |
| `get_zone_status(zone_id)` | Get detailed zone status | dict |
| `get_all_zones_status()` | Get status of all zones | list[dict] |
| `get_robot_reserved_zones(robot_id)` | Get robot's reservations | list[str] |
| `get_robot_occupied_zones(robot_id)` | Get robot's occupancies | list[str] |

### Conflict Detection

| Method | Purpose | Returns |
|--------|---------|---------|
| `check_path_conflicts(robot_id, path_zones)` | Validate path | list[str] |
| `check_collision_risk(robot_id, zone_id)` | Quick collision check | bool |

### Maintenance

| Method | Purpose | Returns |
|--------|---------|---------|
| `cleanup_expired_reservations()` | Remove expired reservations | int |
| `clear_robot(robot_id)` | Emergency cleanup for offline robot | None |
| `get_zone_by_location(location_name)` | Convert location to zone ID | str |

## Typical Delivery Flow

```python
def complete_delivery(robot_id, table_number):
    """Complete delivery with zone management"""
    manager = ZoneManager()

    # 1. Reserve and occupy pickup
    if not manager.reserve_zone(robot_id, 'zone_pickup'):
        print("Pickup busy")
        return False

    navigate_to('pickup_spot', robot_id)
    manager.occupy_zone(robot_id, 'zone_pickup')

    # 2. Wait for food loading (external system)
    wait_for_food_loaded()

    # 3. Reserve delivery table
    table_zone = manager.get_zone_by_location(f'table{table_number}')
    if not manager.reserve_zone(robot_id, table_zone):
        print("Table busy, try another")
        return False

    manager.leave_zone(robot_id, 'zone_pickup')

    # 4. Navigate to and occupy table
    navigate_to(f'table{table_number}', robot_id)
    manager.occupy_zone(robot_id, table_zone)

    # 5. Wait for delivery confirmation
    wait_for_customer_confirmation()

    manager.leave_zone(robot_id, table_zone)

    # 6. Return to parking
    parking_zone = manager.get_zone_by_location(f'{robot_id}_spot')
    manager.reserve_zone(robot_id, parking_zone)
    navigate_to('parking_spot', robot_id)
    manager.occupy_zone(robot_id, parking_zone)

    return True
```

## Configuration

Zones are defined in `fms/config/fms_config.yaml`:

```yaml
zones:
  - id: "zone_pickup"
    center_x: 0.47
    center_y: 0.63
    radius: 0.10
    reservation_timeout: 30.0  # Optional

  - id: "zone_table1"
    center_x: 1.785
    center_y: 0.35
    radius: 0.10
```

### Zone Parameters

- **id**: Unique zone identifier
- **center_x, center_y**: Center coordinates (meters)
- **radius**: Zone radius for collision (meters)
- **reservation_timeout**: Seconds before reservation expires (optional, default 30)

## Available Zones

### Pickup Zone
- `zone_pickup` → location: `pickup_spot`

### Table Zones
- `zone_table1` through `zone_table8` → locations: `table1` through `table8`

### Parking Zones
- `zone_parking1` → location: `pinky1_spot`
- `zone_parking2` → location: `pinky2_spot`
- `zone_parking3` → location: `pinky3_spot`

### Waypoint Zones
- `zone_point1` through `zone_point4` → waypoints on left side
- `zone_point13` → pickup approach point

## Multi-Robot Coordination Example

```python
def schedule_multi_robot_delivery(orders, manager):
    """Schedule multiple deliveries with collision avoidance"""

    for order in orders:
        robot = select_best_robot(order)

        # Get required zones
        pickup_zone = 'zone_pickup'
        table_zone = manager.get_zone_by_location(f'table{order.table}')
        parking_zone = manager.get_zone_by_location(f'{robot}_spot')

        # Try to reserve all zones at once
        if (manager.reserve_zone(robot, pickup_zone) and
            manager.reserve_zone(robot, table_zone)):

            # Create delivery task
            task = Task(
                robot_id=robot,
                order_id=order.id,
                table=order.table,
                zones=[pickup_zone, table_zone, parking_zone]
            )
            schedule_task(task)
        else:
            # Zones not available, retry later
            queue_order(order)
```

## Testing

Run comprehensive test suite:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
```

**Tests cover:**
- Zone creation and state transitions
- Single and multi-robot coordination
- Path conflict detection
- Reservation expiration
- Complete delivery flows
- Emergency cleanup

## Usage Examples

Run example scenarios:

```bash
python3 fms/scripts/zone_manager_example.py
```

**Includes:**
1. Single robot delivery flow
2. Multi-robot coordination
3. Path validation
4. Expiration and cleanup
5. Emergency cleanup
6. Zone monitoring

## Troubleshooting

### Zone Stays Reserved/Occupied

**Issue:** `is_zone_available()` returns False

**Causes:**
- Zone actually in use by another robot (check `get_zone_status()`)
- Robot crashed without releasing zone
- Reservation not timing out

**Solution:**
```python
# Check zone status
status = manager.get_zone_status('zone_pickup')
print(status['occupied_by'], status['reserved_by'])

# If orphaned by offline robot:
manager.clear_robot('pinky1')

# Ensure cleanup is called periodically
manager.cleanup_expired_reservations()
```

### Multi-Robot Deadlock

**Issue:** Robots blocking each other

**Causes:**
- Poor path planning
- Zone reservation timeout too long
- Robots reserving zones in circular dependency

**Solution:**
- Use `check_path_conflicts()` before committing to path
- Reserve entire path at once (all-or-nothing)
- Reduce timeout for high-traffic zones
- Plan paths to avoid intersections

### Slow Zone Access

**Issue:** Frequent failed reservations

**Causes:**
- Too many robots competing for same zone
- Timeouts too long (robots holding zones)
- No re-planning when conflicts detected

**Solution:**
- Implement priority queuing for hot zones
- Reduce reservation timeout for congested areas
- Add automatic re-planning on conflicts
- Consider zone groups for adjacent areas

## Integration with FMS

Add zone manager to FMS node:

```python
class FMSNode:
    def __init__(self):
        # Load config
        config = load_yaml('fms/config/fms_config.yaml')

        # Initialize zone manager
        self.zone_manager = ZoneManager(config)

        # Create cleanup timer
        self.cleanup_timer = self.create_timer(
            5.0,  # Every 5 seconds
            self.cleanup_expired_zones
        )

    def cleanup_expired_zones(self):
        """Periodic cleanup callback"""
        cleaned = self.zone_manager.cleanup_expired_reservations()
        if cleaned > 0:
            self.get_logger().info(f"Cleaned {cleaned} expired zones")

    def handle_new_order(self, order):
        """Assign delivery with zone coordination"""
        robot = self.select_robot(order)

        # Get zones
        pickup = 'zone_pickup'
        table = self.zone_manager.get_zone_by_location(f'table{order.table}')

        # Reserve zones
        if not self.zone_manager.reserve_zone(robot, pickup):
            return False
        if not self.zone_manager.reserve_zone(robot, table):
            self.zone_manager.release_reservation(robot, pickup)
            return False

        # Assign task
        self.assign_delivery_task(robot, order)
        return True
```

## Performance

**Memory:** ~1KB per zone + robot tracking (negligible for 20 zones, 3 robots)

**CPU:** O(1) zone lookup, O(path_length) conflict check

**Scalability:** Tested with 17 zones and 3 robots simultaneously

## Future Enhancements

- Dynamic timeout adjustment based on zone traffic
- Priority queuing for time-sensitive deliveries
- Zone groups for coordinated multi-zone access
- Visualization plugin for zone occupancy
- Deadline-aware reservation (reserve until X time)
- Machine learning-based path planning integration

## Files

| File | Purpose |
|------|---------|
| `/fms/fms/zone_manager.py` | Core implementation |
| `/fms/tests/test_zone_manager_reservation.py` | 30 comprehensive tests |
| `/fms/ZONE_RESERVATION_GUIDE.md` | Detailed API documentation |
| `/fms/scripts/zone_manager_example.py` | Usage examples |
| `/fms/config/fms_config.yaml` | Zone configuration |

## References

- **ZONE_RESERVATION_GUIDE.md**: Detailed API documentation
- **zone_manager_example.py**: Complete working examples
- **test_zone_manager_reservation.py**: Test cases and usage patterns

## Questions?

Refer to:
1. ZONE_RESERVATION_GUIDE.md for detailed API docs
2. zone_manager_example.py for working code
3. Test cases for edge cases and error handling
