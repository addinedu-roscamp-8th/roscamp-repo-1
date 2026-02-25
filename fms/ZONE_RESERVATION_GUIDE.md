# Zone Manager - Pre-Reservation System Guide

## Overview

The Zone Manager implements a comprehensive zone-based collision avoidance system with a pre-reservation mechanism for coordinating multi-robot operations in the Kitchmatics FMS.

### Key Concepts

**Zones**: Circular areas on the map around important locations (pickup, tables, parking spots, waypoints)

**Reservation**: A robot pre-reserves a zone to guarantee exclusive access when it arrives (up to 30 seconds)

**Occupation**: A robot actively occupies a zone after physically entering it

**Conflict**: When another robot tries to use a zone already reserved or occupied by another robot

## Architecture

### Zone Class

Represents a single zone on the map with collision avoidance properties.

**Properties:**
- `zone_id`: Unique identifier (e.g., 'zone_pickup', 'zone_table1')
- `center_x`, `center_y`: Zone center coordinates (meters)
- `radius`: Zone radius (meters)
- `occupied_by`: Robot ID currently in the zone (None if empty)
- `reserved_by`: Robot ID that reserved the zone (None if not reserved)
- `reserved_at`: Timestamp of reservation
- `reservation_timeout`: Seconds before reservation expires (default: 30.0)

**State Machine:**
```
AVAILABLE → RESERVED → OCCUPIED → AVAILABLE
                ↓
           EXPIRED
```

### ZoneManager Class

Manages all zones and coordinates multi-robot access.

**Key Responsibilities:**
1. Zone initialization and management
2. Pre-reservation of zones
3. Occupancy state tracking
4. Expiration and cleanup
5. Conflict detection
6. Path validation

## API Reference

### Core Methods

#### `reserve_zone(robot_id: str, zone_id: str) -> bool`

Pre-reserve a zone for a robot.

**Parameters:**
- `robot_id`: Robot identifier
- `zone_id`: Zone identifier

**Returns:** True if successful, False if zone unavailable

**Example:**
```python
manager = ZoneManager()
if manager.reserve_zone('pinky1', 'zone_pickup'):
    print("Reservation successful")
else:
    print("Zone already reserved or occupied")
```

**Behavior:**
- Only works if zone is completely available (not occupied or reserved)
- Records reservation timestamp
- Blocks other robots from accessing the zone

#### `occupy_zone(robot_id: str, zone_id: str) -> bool`

Transition a zone from reserved to occupied state.

**Parameters:**
- `robot_id`: Robot identifier
- `zone_id`: Zone identifier

**Returns:** True if successful, False otherwise

**Example:**
```python
# After navigating to zone
if manager.occupy_zone('pinky1', 'zone_pickup'):
    print("Zone entered successfully")
```

**Behavior:**
- Can occupy if reserved by this robot or zone is available
- Clears reservation (one robot can't reserve then occupy indefinitely)
- Marks zone as actively occupied

#### `leave_zone(robot_id: str, zone_id: str) -> bool`

Release zone after robot leaves.

**Parameters:**
- `robot_id`: Robot identifier
- `zone_id`: Zone identifier

**Returns:** True if successful, False if robot doesn't own zone

**Example:**
```python
# After delivery or moving to next zone
manager.leave_zone('pinky1', 'zone_table1')
```

**Behavior:**
- Only works if zone is occupied by this robot
- Frees zone for other robots to reserve
- Should be called when robot exits zone area

#### `release_reservation(robot_id: str, zone_id: str) -> bool`

Release a zone reservation (without occupying).

**Parameters:**
- `robot_id`: Robot identifier
- `zone_id`: Zone identifier

**Returns:** True if reservation existed, False otherwise

**Example:**
```python
# Cancel planned delivery if new order has higher priority
manager.release_reservation('pinky1', 'zone_table1')
```

**Behavior:**
- Only works if zone is reserved by this robot
- Used when robot changes plans
- Doesn't affect occupied zones

### Query Methods

#### `is_zone_available(zone_id: str) -> bool`

Check if zone can be reserved.

**Example:**
```python
if manager.is_zone_available('zone_pickup'):
    manager.reserve_zone('pinky2', 'zone_pickup')
```

#### `get_zone_status(zone_id: str) -> Dict`

Get detailed status of a zone.

**Returns:** Dictionary with:
- `zone_id`: Zone identifier
- `occupied_by`: Current occupier (or None)
- `reserved_by`: Current reserver (or None)
- `reserved_at`: ISO timestamp of reservation
- `reservation_age_sec`: Seconds since reservation
- `reservation_timeout`: Timeout duration
- `is_reservation_expired`: Boolean expiration flag
- `available`: Boolean availability flag

**Example:**
```python
status = manager.get_zone_status('zone_pickup')
print(f"Zone occupied by: {status['occupied_by']}")
print(f"Reserved by: {status['reserved_by']}")
print(f"Available: {status['available']}")
```

#### `get_all_zones_status() -> List[Dict]`

Get status of all zones at once.

**Example:**
```python
for zone_status in manager.get_all_zones_status():
    if not zone_status['available']:
        print(f"{zone_status['zone_id']} is in use")
```

#### `get_robot_reserved_zones(robot_id: str) -> List[str]`

Get all zones currently reserved by a robot.

**Example:**
```python
reserved = manager.get_robot_reserved_zones('pinky1')
print(f"Robot has {len(reserved)} zones reserved")
```

#### `get_robot_occupied_zones(robot_id: str) -> List[str]`

Get all zones currently occupied by a robot.

**Example:**
```python
occupied = manager.get_robot_occupied_zones('pinky1')
for zone_id in occupied:
    print(f"Robot is in {zone_id}")
```

### Path and Conflict Detection

#### `check_path_conflicts(robot_id: str, path_zones: List[str]) -> List[str]`

Check if a planned path has zone conflicts.

**Parameters:**
- `robot_id`: Robot identifier
- `path_zones`: List of zone IDs in planned path

**Returns:** List of zone IDs with conflicts (empty if no conflicts)

**Example:**
```python
path = ['zone_parking1', 'zone_point1', 'zone_pickup', 'zone_table1']
conflicts = manager.check_path_conflicts('pinky1', path)

if conflicts:
    print(f"Path blocked by: {conflicts}")
    # Re-plan route
else:
    # Reserve path zones
    for zone_id in path:
        manager.reserve_zone('pinky1', zone_id)
```

**Behavior:**
- Returns zones occupied by OTHER robots
- Returns zones reserved by OTHER robots
- Does NOT include zones reserved by the requesting robot
- Use for path validation before committing to navigation

#### `check_collision_risk(robot_id: str, target_zone_id: str) -> bool`

Quick check if entering a zone would cause collision.

**Example:**
```python
if manager.check_collision_risk('pinky1', 'zone_pickup'):
    print("Zone occupied, wait")
else:
    manager.reserve_zone('pinky1', 'zone_pickup')
```

### Maintenance and Cleanup

#### `cleanup_expired_reservations() -> int`

Remove reservations that exceeded timeout.

**Returns:** Number of reservations cleaned up

**Example:**
```python
# Call periodically (e.g., every 5 seconds)
expired_count = manager.cleanup_expired_reservations()
if expired_count > 0:
    logger.info(f"Cleaned up {expired_count} expired reservations")
```

**Behavior:**
- Checks all zones for expired reservations
- Default timeout is 30 seconds per zone
- Logs which zones were cleaned
- Frees those zones for other robots

#### `clear_robot(robot_id: str)`

Emergency cleanup: release all zones for a robot.

**Example:**
```python
# When robot error or goes offline
manager.clear_robot('pinky1')
```

**Behavior:**
- Releases all occupied zones
- Releases all reserved zones
- Removes from internal tracking
- Use when robot error detected

### Utility Methods

#### `get_zone_by_location(location_name: str) -> Optional[str]`

Convert location name to zone ID.

**Supported Location Names:**
- `pickup_spot` → `zone_pickup`
- `table1` through `table8` → `zone_table1` through `zone_table8`
- `pinky1_spot`, `pinky2_spot`, `pinky3_spot` → `zone_parking1` through `zone_parking3`

**Example:**
```python
zone_id = manager.get_zone_by_location('table3')
manager.reserve_zone('pinky1', zone_id)
```

## Typical Usage Patterns

### Single Robot Delivery

```python
manager = ZoneManager()
robot_id = 'pinky1'

# 1. Reserve pickup zone
if not manager.reserve_zone(robot_id, 'zone_pickup'):
    print("Pickup busy, wait")
    return

# 2. Navigate to pickup
navigate_to_pickup_spot(robot_id)

# 3. Occupy pickup zone when arrived
manager.occupy_zone(robot_id, 'zone_pickup')

# 4. Load food (external system)
wait_for_food_loaded()

# 5. Reserve delivery table
table_zone = manager.get_zone_by_location(f'table{order.table_number}')
if not manager.reserve_zone(robot_id, table_zone):
    print("Table busy, try another")
    return

# 6. Leave pickup
manager.leave_zone(robot_id, 'zone_pickup')

# 7. Navigate to table
navigate_to_location(robot_id, order.table_number)

# 8. Occupy table zone
manager.occupy_zone(robot_id, table_zone)

# 9. Customer confirmation
wait_for_delivery_complete()

# 10. Leave table
manager.leave_zone(robot_id, table_zone)

# 11. Return to parking
parking_zone = manager.get_zone_by_location(f'{robot_id}_spot')
manager.reserve_zone(robot_id, parking_zone)
navigate_to_parking_spot(robot_id)
manager.occupy_zone(robot_id, parking_zone)
```

### Multi-Robot Delivery Coordination

```python
manager = ZoneManager()

# Check if delivery is possible
table_zone = manager.get_zone_by_location('table1')
pickup_zone = manager.get_zone_by_location('pickup_spot')

if manager.is_zone_available(pickup_zone):
    robot = select_available_robot()

    # Reserve both zones before committing
    if (manager.reserve_zone(robot, pickup_zone) and
        manager.reserve_zone(robot, table_zone)):

        # Execute delivery
        complete_delivery(robot, 'table1')

        # Cleanup
        manager.leave_zone(robot, table_zone)
        manager.leave_zone(robot, pickup_zone)
    else:
        print("Zones not available, try later")
else:
    print("Pickup busy")
```

### Path Validation

```python
# Plan route for robot
path_zones = ['zone_parking1', 'zone_point1', 'zone_pickup']

# Check for conflicts
conflicts = manager.check_path_conflicts('pinky1', path_zones)

if conflicts:
    print(f"Path blocked by: {conflicts}")
    # Trigger re-planning or wait for conflicts to clear
else:
    # Reserve path zones
    for zone_id in path_zones:
        manager.reserve_zone('pinky1', zone_id)

    # Execute navigation
    for zone_id in path_zones:
        navigate_to_zone(zone_id)
        manager.occupy_zone('pinky1', zone_id)
        # ... navigate
        manager.leave_zone('pinky1', zone_id)
```

## Zone Configuration

Zones are defined in `fms/config/fms_config.yaml`:

```yaml
zones:
  - id: "zone_pickup"
    center_x: 0.47
    center_y: 0.63
    radius: 0.10
    reservation_timeout: 30.0  # Optional, defaults to 30 seconds

  - id: "zone_table1"
    center_x: 1.785
    center_y: 0.35
    radius: 0.10
```

**Parameters:**
- `id`: Unique zone identifier
- `center_x`, `center_y`: Zone center (meters)
- `radius`: Zone radius (meters) - collision margin
- `reservation_timeout`: Optional custom timeout (seconds)

## Reservation Timeout Mechanism

### How It Works

1. Zone is reserved at time T
2. Timeout is set to T + 30 seconds
3. If robot doesn't occupy zone within 30 seconds, reservation expires
4. `cleanup_expired_reservations()` must be called to remove expired reservations
5. Other robots can then reserve the expired zone

### Why Timeout is Important

**Scenarios:**
- Robot navigates to pickup but crashes mid-way
- Network failure prevents robot from sending occupancy update
- Robot stuck in obstacle and can't proceed
- Order cancelled but reservation not released

**Solution:**
- Timeout prevents zones from being permanently locked
- Periodic cleanup frees up deadlocked zones
- Can be tuned per zone (some zones may need longer timeout)

### Recommended Cleanup Interval

```python
# In main FMS loop
cleanup_timer = 0
cleanup_interval = 5.0  # seconds

def main_loop():
    global cleanup_timer

    while running:
        # ... handle robot orders and movements

        cleanup_timer += loop_delta_time
        if cleanup_timer >= cleanup_interval:
            count = manager.cleanup_expired_reservations()
            cleanup_timer = 0
```

## Testing

Run the comprehensive test suite:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
```

**Test Coverage:**
- Zone creation and state transitions
- Reservation and occupation
- Expiration detection
- Multi-robot coordination
- Path conflict detection
- Complete delivery flow scenarios

## Integration with FMS

The ZoneManager should be integrated into the main FMS node:

```python
# In fms_node.py or fleet_controller.py

class FMSNode:
    def __init__(self):
        # Load zone config from fms_config.yaml
        config = load_config('fms/config/fms_config.yaml')
        self.zone_manager = ZoneManager(config)

        # Create cleanup timer
        self.create_timer(5.0, self.cleanup_zones)

    def cleanup_zones(self):
        """Periodic cleanup of expired reservations"""
        cleaned = self.zone_manager.cleanup_expired_reservations()
        if cleaned > 0:
            self.get_logger().info(f"Cleaned {cleaned} expired zones")

    def assign_delivery(self, order):
        """Assign delivery to robot with zone coordination"""
        robot = self.select_robot(order)

        # Get zone IDs
        pickup_zone = self.zone_manager.get_zone_by_location('pickup_spot')
        table_zone = self.zone_manager.get_zone_by_location(f'table{order.table}')

        # Try to reserve zones
        if not self.zone_manager.reserve_zone(robot.id, pickup_zone):
            return False  # Pickup busy

        if not self.zone_manager.reserve_zone(robot.id, table_zone):
            self.zone_manager.release_reservation(robot.id, pickup_zone)
            return False  # Table busy

        # Create task with zone information
        task = Task(
            robot_id=robot.id,
            order_id=order.id,
            pickup_zone=pickup_zone,
            delivery_zone=table_zone
        )

        self.task_manager.assign_task(task)
        return True
```

## Troubleshooting

### Zone Not Available

**Problem:** `reserve_zone()` returns False when zone seems empty

**Causes:**
1. Zone actually occupied by another robot
2. Zone reserved by another robot (check with `get_zone_status()`)
3. Robot offline but zone not cleaned (call `clear_robot()`)

**Solution:**
```python
status = manager.get_zone_status('zone_pickup')
print(f"Occupied: {status['occupied_by']}, Reserved: {status['reserved_by']}")

# If occupied by offline robot:
manager.clear_robot('pinky1')
```

### Zones Never Cleanup

**Problem:** Zones stay occupied/reserved indefinitely

**Causes:**
1. `cleanup_expired_reservations()` not being called
2. Robot not calling `leave_zone()` properly
3. Robot crashed without cleanup

**Solution:**
1. Ensure cleanup is called periodically
2. Add error handling to always call cleanup:
   ```python
   try:
       deliver_package(robot)
   finally:
       manager.clear_robot(robot.id)
   ```

### Multi-Robot Deadlock

**Problem:** Robots blocking each other in circular path

**Causes:**
1. Poor path planning through zones
2. Multiple robots reserving same zones in different order
3. No timeout or timeout too long

**Solution:**
1. Use `check_path_conflicts()` before committing to path
2. Reserve entire path at once (all or nothing)
3. Use shorter timeout for congested zones:
   ```yaml
   zones:
     - id: "zone_point1"
       reservation_timeout: 10.0  # Shorter timeout
   ```

## Performance Considerations

- Zone lookup is O(1) with zone_id
- Path conflict check is O(path_length)
- Cleanup is O(num_zones)
- Memory usage: ~1KB per zone + robot tracking

**For 20 zones, 3 robots:** ~50KB memory usage (negligible)

## Future Enhancements

1. **Dynamic Timeout:** Adjust timeout based on zone type
2. **Priority Zones:** Some zones get priority reservation
3. **Zone Groups:** Treat adjacent zones as single unit
4. **Deadline Tracking:** Reserve zone with task deadline
5. **Visualization:** RViz plugin showing zone occupancy
