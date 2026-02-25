# Task Scheduler Integration Guide

## Overview

The `TaskScheduler` manages multi-robot task assignment and pickup spot access control. It solves the critical problem: **multiple robots arriving at pickup_spot simultaneously cannot physically occupy the same space**.

## Architecture

### Components

1. **TaskScheduler**: Main coordinator
   - Task queue management (FIFO)
   - Robot-task assignment logic
   - Task state tracking

2. **PickupSlotManager**: Pickup access control
   - Single pickup slot (only 1 robot at a time)
   - Queue management (FIFO)
   - Waiting zone assignment
   - Timeout handling

### Task States

```
PENDING
  ↓
ASSIGNED → MOVING_TO_PICKUP
  ↓
WAITING_FOR_PICKUP (queued)
  ↓
AT_PICKUP (has slot access)
  ↓
LOADED
  ↓
MOVING_TO_TABLE → AT_TABLE → COMPLETED

FAILED (error occurred)
```

## Usage Patterns

### 1. Initialization

```python
from fms.task_scheduler import TaskScheduler
from fms.zone_manager import ZoneManager

# In FMS node __init__:
self.zone_manager = ZoneManager()
self.task_scheduler = TaskScheduler(self.zone_manager)
```

### 2. New Order Handling

```python
def on_order_received(self, order_msg):
    # Create task from order
    task = Task(
        order_id=order_msg.order_id,
        menu_id=order_msg.menu_id,
        table_number=order_msg.table_number,
        quantity=order_msg.quantity,
        sauce_type=order_msg.sauce_type,
        voice_order=order_msg.voice_order
    )

    # Add to scheduler queue
    task_id = self.task_scheduler.add_task(task)
    logger.info(f"Order {order_msg.order_id} queued as task {task_id}")
```

### 3. Task Assignment to Available Robots

Call periodically (e.g., 2 Hz) to match pending tasks with idle robots:

```python
def assign_tasks_timer(self):
    # Get idle robots from fleet controller
    idle_robots = [
        robot.robot_id for robot in self.fleet_controller.get_all_robots()
        if robot.is_available()
    ]

    # Assign pending tasks to idle robots
    for robot_id in idle_robots:
        task = self.task_scheduler.assign_task_to_robot(robot_id)
        if task:
            # Send task to robot (navigate to pickup_spot)
            self.send_navigate_goal(robot_id, 'pickup_spot')
            logger.info(f"Robot {robot_id} assigned task {task.task_id}")
```

### 4. Robot Reaches Pickup Spot

When robot reaches pickup_spot:

```python
def on_robot_reached_pickup(self, robot_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        logger.warning(f"Robot {robot_id} reached pickup but has no task")
        return

    # Request pickup slot access
    is_granted = self.task_scheduler.request_pickup_access(
        robot_id, task.task_id
    )

    if is_granted:
        # Robot can load immediately
        logger.info(f"Robot {robot_id} has pickup access, loading...")
        # Publish goal_arrived message
        self.publish_goal_arrived(robot_id, task.order_id)
    else:
        # Robot must wait
        waiting_zone = self.task_scheduler.get_next_waiting_zone(robot_id)
        logger.info(f"Robot {robot_id} waiting, moving to {waiting_zone}")
        # Send robot to waiting zone (point13 for next in queue)
        self.send_navigate_goal(robot_id, waiting_zone)
```

### 5. Robot Finished Loading

When food loading completes:

```python
def on_food_loaded(self, robot_id: str, order_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        logger.warning(f"Robot {robot_id} has no current task")
        return

    # Release pickup slot and load next robot in queue
    self.task_scheduler.robot_loaded(robot_id, task.task_id)

    # Send robot to table
    table_location = self.get_table_location(task.table_number)
    self.send_navigate_goal(robot_id, table_location)

    # Check if next robot in queue can now enter
    self.check_pickup_queue_and_advance()
```

### 6. Delivery Complete

```python
def on_delivery_complete(self, robot_id: str, order_id: str):
    task = self.task_scheduler.get_robot_task(robot_id)
    if not task:
        return

    # Mark task complete
    self.task_scheduler.robot_delivered(robot_id, task.task_id)

    # Send robot back to parking spot
    parking_spot = self.fleet_controller.parking_spots.get(robot_id)
    self.send_navigate_goal(robot_id, parking_spot)
```

### 7. Periodic Queue Advancement

Call frequently (e.g., 10 Hz) to advance pickup queue:

```python
def check_pickup_queue_timer(self):
    queue_status = self.task_scheduler.get_pickup_queue_status()

    # Check timeout (robot exceeded max pickup time)
    if self.task_scheduler.pickup_manager.check_slot_timeout():
        logger.warning("Pickup slot timeout, forcing release")
        next_robot = self.task_scheduler.pickup_manager.force_release_slot()
        if next_robot:
            # Notify next robot it can now enter
            task = self.task_scheduler.get_robot_task(next_robot)
            if task:
                self.send_navigate_goal(next_robot, 'pickup_spot')

    # Log queue status if busy
    if queue_status['queue_length'] > 0:
        logger.debug(f"Pickup queue: {queue_status['waiting_robots']}")
```

### 8. Error Handling

```python
def on_robot_error(self, robot_id: str, error_msg: str):
    logger.error(f"Robot {robot_id}: {error_msg}")

    # Scheduler handles cleanup:
    # - Releases pickup slot
    # - Removes from queue
    # - Fails task and returns to queue
    # - Next robot gets pickup access
    self.task_scheduler.handle_robot_error(robot_id, error_msg)

    # Check if queue can advance
    self.check_pickup_queue_and_advance()
```

## Example Workflow: 3 Orders Simultaneously

### Scenario

Three orders arrive while all robots are idle:

| Time | Event | State |
|------|-------|-------|
| T0 | 3 orders arrive | Queue: [order1, order2, order3] |
| T1 | pinky1, pinky2, pinky3 assigned | Active: 3 tasks, Pending: 0 |
| T2 | pinky1 reaches pickup | pinky1 has slot, pinky2/3 moving to pickup |
| T3 | pinky2 reaches pickup | pinky2 queued (waiting at point13) |
| T4 | pinky3 reaches pickup | pinky3 queued (waiting at parking_spot) |
| T5 | pinky1 loaded, leaves | pinky2 granted slot, waiting robots = 1 |
| T6 | pinky2 loaded, leaves | pinky3 granted slot, waiting robots = 0 |
| T7 | pinky3 loaded, leaves | All robots delivering to tables |
| T8+ | Deliveries complete | All robots return to parking |

### Code Flow

```python
# T0-T1: Orders arrive and get assigned
for order in orders:
    fms.on_order_received(order)
for robot_id in available_robots:
    fms.assign_tasks_to_available_robots(robot_id)

# T2: pinky1 reaches pickup
fms.on_robot_reached_pickup('pinky1')
# → Request pickup access
# → Is granted (queue empty)
# → Publish goal_arrived

# T3: pinky2 reaches pickup (different point in time)
# Navigation continues, pinky1 still loading
fms.on_robot_reached_pickup('pinky2')
# → Request pickup access
# → NOT granted (pinky1 holding slot)
# → Queue pinky2
# → Move to waiting zone (point13)

# T4: pinky3 reaches pickup
fms.on_robot_reached_pickup('pinky3')
# → Request pickup access
# → NOT granted (pinky1 still holding)
# → Queue pinky3
# → Move to waiting zone (pinky3_spot - no longer needed by it)

# T5: pinky1 finishes loading
fms.on_food_loaded('pinky1', task1.task_id)
# → Release slot
# → Notify pinky2 it has access
# → pinky2 moves to pickup_spot

# T6: pinky2 finishes loading
fms.on_food_loaded('pinky2', task2.task_id)
# → Release slot
# → Notify pinky3 it has access
# → pinky3 moves to pickup_spot

# ... and so on
```

## Waiting Zone Strategy

### Point13 vs Parking Spot

When robot is waiting for pickup slot:

1. **First in Queue**: Moves to `point13` (closest to pickup_spot)
   - Can immediately move to pickup when slot opens
   - Minimal delay (~0.5s navigation to pickup)

2. **Others in Queue**: Stay at parking_spot or move there
   - Wait until first in queue finishes
   - Will advance to point13 when they become first

### Configuration

Edit waiting zones in `PickupSlotManager`:

```python
self.waiting_zone_positions = {
    'point13': {'x': 0.585, 'y': 0.63, 'zone_id': 'zone_point13'},
    'pinky1_spot': {'x': 0.585, 'y': 0.085, 'zone_id': 'zone_parking1'},
    'pinky2_spot': {'x': 0.585, 'y': 0.255, 'zone_id': 'zone_parking2'},
    'pinky3_spot': {'x': 0.585, 'y': 0.915, 'zone_id': 'zone_parking3'},
}
```

## Status Monitoring

### Get Current Status

```python
# Comprehensive status
status = task_scheduler.get_scheduler_status()
print(f"Pending: {status['pending_tasks']}")
print(f"Active: {status['active_tasks']}")
print(f"Waiting for pickup: {status['robots_waiting_for_pickup']}")
print(f"Queue: {status['pickup_queue']}")

# Task summary by state
summary = task_scheduler.get_task_summary()
print(f"Pending: {summary['PENDING']}")
print(f"At pickup: {summary['AT_PICKUP']}")
print(f"Loaded: {summary['LOADED']}")
print(f"Completed: {summary['COMPLETED']}")

# Pickup queue detail
queue = task_scheduler.get_pickup_queue_status()
print(f"Current holder: {queue['current_holder']}")
print(f"Waiting robots: {queue['waiting_robots']}")
print(f"Queue positions: {queue['queue_positions']}")
```

### Publisher for Monitoring

```python
def publish_scheduler_status(self):
    status = self.task_scheduler.get_scheduler_status()
    # Publish to /fms/scheduler_status
    self.scheduler_status_pub.publish(status)
```

## Timeout Handling

### Scenario: Robot at Pickup Exceeds Time Limit

Default timeout: 60 seconds

```python
def check_pickup_queue_timer(self):
    if self.task_scheduler.pickup_manager.check_slot_timeout():
        logger.warning("Pickup timeout exceeded")
        next_robot = self.task_scheduler.pickup_manager.force_release_slot()
        # Old robot is forced out, next gets access
```

### Customization

```python
# Set custom timeout (e.g., 30 seconds)
task_scheduler.pickup_manager.holding_timeout = 30.0
```

## Testing

### Run Integration Example

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m fms.fms.scheduler_integration_example
```

Output shows workflow timeline for 3 simultaneous orders:

```
=== WORKFLOW: 3 Simultaneous Orders ===

T0: 3 orders arrive
Queue size: 3

T1: Assign tasks to 3 available robots
Assignments: 3
Pending: 0
Active: 3

T2: pinky1 reaches pickup_spot
Pickup queue: 0 waiting

T3: pinky2 reaches pickup_spot
Pickup queue: 1 waiting
pinky2 waiting zone: point13

T4: pinky3 reaches pickup_spot
Pickup queue: 2 waiting
pinky3 waiting zone: pinky3_spot

T5: pinky1 finishes loading
Pickup queue: 1 waiting
Next robot: pinky2

...
```

## Integration Checklist

When integrating into FMS node:

- [ ] Import TaskScheduler and Task classes
- [ ] Initialize scheduler in FMS.__init__()
- [ ] Create order handling method with task creation
- [ ] Create assignment timer (2 Hz)
- [ ] Hook robot reached pickup event
- [ ] Hook food loaded event
- [ ] Hook delivery complete event
- [ ] Hook robot error event
- [ ] Create pickup queue check timer (10 Hz)
- [ ] Create status publisher
- [ ] Test with skip_robot_arm=True mode
- [ ] Test with multiple simultaneous orders
- [ ] Monitor queue status in logs

## ROS 2 Topic Integration

```python
# Subscribers
self.order_request_sub = self.create_subscription(
    OrderRequest,
    '/fms/order_request',
    self.on_order_received,
    10
)

self.delivery_complete_sub = self.create_subscription(
    DeliveryComplete,
    '/fms/delivery_complete',
    self.on_delivery_complete,
    10
)

# Publisher for scheduler status
self.scheduler_status_pub = self.create_publisher(
    Dict,  # Use custom message type
    '/fms/scheduler_status',
    10
)

# Timers
self.assign_tasks_timer = self.create_timer(0.5, self.assign_tasks_timer)  # 2 Hz
self.queue_check_timer = self.create_timer(0.1, self.check_pickup_queue_timer)  # 10 Hz
```

## Performance Considerations

- **Queue operations**: O(1) for FIFO (deque)
- **Task lookup**: O(1) with dict
- **Zone operations**: O(n) where n = number of zones
- **Typical case**: 1-3 waiting robots, negligible overhead

For 3 robots and 10-20 pending tasks:
- Memory: ~1 KB per task
- CPU: <1% for queue operations

## Troubleshooting

### Problem: Robot stuck at pickup

**Check**: Is pickup slot timeout exceeding 60s?

```python
queue = task_scheduler.get_pickup_queue_status()
print(f"Current holder: {queue['current_holder']}")
print(f"Arrival time: {queue['holder_arrival_time']}")
```

**Solution**: Force release in check_pickup_queue_timer()

### Problem: Queue not advancing

**Check**: Is next robot being notified to move to pickup?

```python
queue = task_scheduler.get_pickup_queue_status()
next_robot = queue['waiting_robots'][0]
# Make sure robot is receiving navigate goal to pickup_spot
```

**Solution**: Ensure on_food_loaded() calls check_pickup_queue_and_advance()

### Problem: Task stuck in WAITING_FOR_PICKUP

**Check**: Is robot at point13 receiving command to move to pickup_spot when queue advances?

```python
robot_task = task_scheduler.get_robot_task(robot_id)
print(f"Task state: {task_scheduler.get_task_state(robot_task.task_id)}")
```

**Solution**: Implement callback when robot released from queue

## Next Steps

1. **Integrate into fms_node.py**: Use patterns from scheduler_integration_example.py
2. **Add topic publications**: Publish scheduler_status for monitoring
3. **Add unit tests**: Test queue management and timeouts
4. **Tune waiting zones**: Optimize point13 distance and parking spot alternatives
5. **Implement GUI display**: Show pickup queue status to operators
