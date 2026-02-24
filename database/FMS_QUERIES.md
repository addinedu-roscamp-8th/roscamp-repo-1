# FMS Database Query Reference

**Purpose**: Common SQL queries for FMS operations
**Target Users**: FMS Developers, Database Team
**Last Updated**: 2026-02-25

---

## Table of Contents

1. [Robot Status Queries](#robot-status-queries)
2. [Order Management Queries](#order-management-queries)
3. [Navigation & State Tracking](#navigation--state-tracking)
4. [Event Logging & Auditing](#event-logging--auditing)
5. [Analytics & Reporting](#analytics--reporting)
6. [Performance & Optimization](#performance--optimization)

---

## Robot Status Queries

### 1.1 Find Available Robots for Assignment

```sql
-- Find idle robots with sufficient battery
SELECT
    id,
    name,
    domain_id,
    namespace,
    status,
    battery_voltage,
    parking_spot
FROM robots
WHERE type = 'SERVING_BOT_1'
AND status = 'IDLE'
AND battery_voltage > 20.0
ORDER BY battery_voltage DESC
LIMIT 1;
```

**Use Case**: Robot task assignment
**Index**: idx_robots_type_status
**Performance**: < 1ms

### 1.2 Get All Active Robots with Current Tasks

```sql
SELECT
    r.id,
    r.name,
    r.domain_id,
    r.status,
    r.battery_voltage,
    o.id as current_order_id,
    o.table_number,
    o.status as order_status,
    EXTRACT(EPOCH FROM (NOW() - o.created_at))::INT as task_duration_seconds
FROM robots r
LEFT JOIN orders o ON (
    r.id = o.assigned_serving_bot_id
    AND o.status NOT IN ('COMPLETED', 'CANCELLED')
)
WHERE r.type LIKE 'SERVING_BOT%'
ORDER BY r.domain_id;
```

**Use Case**: Fleet monitoring, admin dashboard
**Index**: idx_robots_type_status, idx_orders_serving_bot_active
**Performance**: < 10ms

### 1.3 Check Battery Status for All Robots

```sql
SELECT
    name,
    domain_id,
    battery_voltage,
    CASE
        WHEN battery_voltage <= 10.0 THEN 'CRITICAL'
        WHEN battery_voltage <= 20.0 THEN 'LOW'
        WHEN battery_voltage > 20.0 THEN 'OK'
    END as battery_status,
    CASE
        WHEN battery_voltage > 20.0 THEN '✓ Available'
        ELSE '✗ Needs Charging'
    END as availability
FROM robots
WHERE type LIKE 'SERVING_BOT%'
ORDER BY battery_voltage ASC;
```

**Use Case**: Battery monitoring, maintenance scheduling
**Performance**: < 1ms

### 1.4 Find Robot by Domain ID

```sql
-- Get robot by ROS domain ID
SELECT
    id,
    name,
    domain_id,
    namespace,
    type,
    status,
    ip_address,
    parking_spot
FROM robots
WHERE domain_id = 11;
```

**Use Case**: FMS domain routing
**Index**: UNIQUE constraint on domain_id
**Performance**: < 1ms

---

## Order Management Queries

### 2.1 Get Current Orders by Status

```sql
-- Orders in delivery phase (robot assigned)
SELECT
    o.id,
    o.table_number,
    o.status,
    o.quantity,
    m.name as menu_name,
    r.name as assigned_robot,
    r.domain_id,
    o.created_at,
    EXTRACT(EPOCH FROM (NOW() - o.created_at))::INT as elapsed_seconds
FROM orders o
JOIN menus m ON o.menu_id = m.id
LEFT JOIN robots r ON o.assigned_serving_bot_id = r.id
WHERE o.status IN ('AT_POINT13', 'PRECISION_PARKING', 'LOADING', 'LOADED', 'DELIVERING', 'DELIVERED')
ORDER BY o.status, o.created_at;
```

**Use Case**: FMS task manager, track active deliveries
**Index**: idx_orders_status, idx_orders_serving_bot_active
**Performance**: < 5ms

### 2.2 Assign Robot to Order

```sql
-- Assign an available robot to an order
UPDATE orders
SET
    assigned_serving_bot_id = (
        SELECT id FROM robots
        WHERE type = 'SERVING_BOT_1'
        AND status = 'IDLE'
        AND battery_voltage > 20.0
        LIMIT 1
    ),
    updated_at = NOW()
WHERE id = 'order-uuid-here'
AND assigned_serving_bot_id IS NULL
RETURNING id, assigned_serving_bot_id, status;
```

**Use Case**: FMS task assignment
**Constraint**: Validates robot exists and is available
**Performance**: < 5ms

### 2.3 Update Order Status

```sql
-- Transition order through delivery flow
UPDATE orders
SET
    status = 'AT_POINT13',
    updated_at = NOW()
WHERE id = 'order-uuid-here'
AND status = 'ORDERED'
RETURNING id, table_number, status, updated_at;
```

**Use Case**: FMS state machine
**Validation**: Order status must follow defined flow
**Performance**: < 2ms

### 2.4 Get Order History (Complete Timeline)

```sql
-- Show complete order timeline with timestamps
SELECT
    id,
    table_number,
    status,
    created_at,
    updated_at,
    completed_at,
    EXTRACT(EPOCH FROM (created_at))::BIGINT * 1000 as created_timestamp_ms,
    EXTRACT(EPOCH FROM (NOW() - created_at))::INT as total_elapsed_seconds,
    CASE
        WHEN completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (completed_at - created_at))::INT
        ELSE NULL
    END as total_duration_seconds
FROM orders
WHERE table_number = 'T01'
ORDER BY created_at DESC;
```

**Use Case**: Debugging, performance analysis
**Index**: idx_orders_table_number, idx_orders_created_at
**Performance**: < 2ms

### 2.5 Find Orders by Robot Assignment

```sql
-- Get all active orders assigned to a specific robot
SELECT
    o.id,
    o.table_number,
    o.status,
    o.quantity,
    m.name as menu_name,
    EXTRACT(EPOCH FROM (NOW() - o.created_at))::INT as elapsed_seconds
FROM orders o
JOIN menus m ON o.menu_id = m.id
WHERE o.assigned_serving_bot_id = (
    SELECT id FROM robots WHERE domain_id = 11 LIMIT 1
)
AND o.status NOT IN ('COMPLETED', 'CANCELLED')
ORDER BY o.created_at;
```

**Use Case**: Robot-specific task list
**Index**: idx_orders_serving_bot_active
**Performance**: < 2ms

### 2.6 Get Next Order in Queue

```sql
-- Find next order waiting for a robot (FIFO)
SELECT
    id,
    table_number,
    menu_id,
    quantity,
    created_at
FROM orders
WHERE status = 'ORDERED'
AND assigned_serving_bot_id IS NULL
ORDER BY created_at ASC
LIMIT 1;
```

**Use Case**: FMS task manager queue
**Index**: idx_orders_status
**Performance**: < 1ms

---

## Navigation & State Tracking

### 3.1 Create Navigation Record

```sql
-- Start tracking navigation for an order
INSERT INTO fms_navigation_states (
    order_id,
    robot_id,
    current_x, current_y, current_yaw,
    target_x, target_y, target_yaw,
    navigation_status,
    started_at
)
VALUES (
    'order-uuid',
    'robot-uuid',
    0.585, 0.085, 0.0,     -- Starting position
    0.585, 0.63, 0.0,      -- Target position
    'NAVIGATING',
    NOW()
)
RETURNING id, navigation_status;
```

**Use Case**: FMS navigation start
**Index**: idx_fms_nav_order
**Performance**: < 2ms

### 3.2 Update Navigation Status

```sql
-- Update navigation state when goal is reached
UPDATE fms_navigation_states
SET
    current_x = 0.585,
    current_y = 0.63,
    current_yaw = 0.0,
    navigation_status = 'REACHED',
    completed_at = NOW(),
    updated_at = NOW()
WHERE order_id = 'order-uuid'
AND robot_id = 'robot-uuid'
AND navigation_status = 'NAVIGATING'
RETURNING id, navigation_status, completed_at;
```

**Use Case**: FMS goal reached notification
**Index**: idx_fms_nav_order, idx_fms_nav_robot
**Performance**: < 2ms

### 3.3 Get Current Navigation Status

```sql
-- Get current navigation state for an order
SELECT
    ns.id,
    ns.order_id,
    (SELECT table_number FROM orders WHERE id = ns.order_id) as table_number,
    r.name as robot_name,
    r.domain_id,
    ns.current_x, ns.current_y, ns.current_yaw,
    ns.target_x, ns.target_y, ns.target_yaw,
    ns.navigation_status,
    EXTRACT(EPOCH FROM (NOW() - ns.started_at))::INT as elapsed_seconds
FROM fms_navigation_states ns
JOIN robots r ON ns.robot_id = r.id
WHERE ns.order_id = 'order-uuid'
AND ns.navigation_status != 'IDLE'
ORDER BY ns.started_at DESC
LIMIT 1;
```

**Use Case**: FMS status monitoring
**Index**: idx_fms_nav_order, idx_fms_nav_status
**Performance**: < 2ms

### 3.4 Get Navigation by Robot

```sql
-- Get current navigation for a robot
SELECT
    ns.order_id,
    o.table_number,
    ns.navigation_status,
    ns.current_x, ns.current_y,
    ns.target_x, ns.target_y,
    EXTRACT(EPOCH FROM (NOW() - ns.started_at))::INT as elapsed_seconds
FROM fms_navigation_states ns
JOIN orders o ON ns.order_id = o.id
WHERE ns.robot_id = (
    SELECT id FROM robots WHERE domain_id = 11 LIMIT 1
)
AND ns.navigation_status = 'NAVIGATING'
ORDER BY ns.started_at DESC;
```

**Use Case**: Robot current task
**Index**: idx_fms_nav_robot, idx_fms_nav_status
**Performance**: < 2ms

---

## Event Logging & Auditing

### 4.1 Log Order Event

```sql
-- Insert event log entry
INSERT INTO fms_event_log (
    event_type,
    order_id,
    robot_id,
    details,
    occurred_at
)
VALUES (
    'GOAL_REACHED',
    'order-uuid',
    'robot-uuid',
    jsonb_build_object(
        'point_name', 'point13',
        'x', 0.585,
        'y', 0.63
    ),
    NOW()
)
RETURNING id, event_type, occurred_at;
```

**Use Case**: FMS event tracking
**Performance**: < 2ms

### 4.2 Log Error Event

```sql
-- Log error with details
INSERT INTO fms_event_log (
    event_type,
    order_id,
    robot_id,
    error_message,
    details,
    occurred_at
)
VALUES (
    'ERROR',
    'order-uuid',
    'robot-uuid',
    'Navigation failed: Path not found',
    jsonb_build_object(
        'error_code', 'NAV_PATH_NOT_FOUND',
        'retry_count', 2,
        'last_position', jsonb_build_object('x', 0.585, 'y', 0.63)
    ),
    NOW()
)
RETURNING id;
```

**Use Case**: FMS error handling
**Index**: idx_fms_event_error
**Performance**: < 2ms

### 4.3 Get Event Timeline for Order

```sql
-- Get complete event history for an order
SELECT
    event_type,
    robot_id,
    (SELECT name FROM robots WHERE id = robot_id) as robot_name,
    details,
    error_message,
    occurred_at,
    EXTRACT(EPOCH FROM (occurred_at))::BIGINT * 1000 as timestamp_ms
FROM fms_event_log
WHERE order_id = 'order-uuid'
ORDER BY occurred_at;
```

**Use Case**: Debugging, order analysis
**Index**: idx_fms_event_order, idx_fms_event_time
**Performance**: < 5ms

### 4.4 Get Recent Errors

```sql
-- Get last 10 errors in system
SELECT
    id,
    event_type,
    order_id,
    (SELECT table_number FROM orders WHERE id = order_id) as table_number,
    robot_id,
    (SELECT name FROM robots WHERE id = robot_id) as robot_name,
    error_message,
    details,
    occurred_at
FROM fms_event_log
WHERE event_type = 'ERROR'
ORDER BY occurred_at DESC
LIMIT 10;
```

**Use Case**: Error monitoring, system health check
**Index**: idx_fms_event_error
**Performance**: < 5ms

---

## Analytics & Reporting

### 5.1 Delivery Performance Metrics

```sql
-- Average time per delivery phase
SELECT
    'ORDERED -> AT_POINT13' as phase,
    COUNT(*) as total_deliveries,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)))::NUMERIC, 1) as avg_duration_seconds
FROM orders
WHERE status IN ('AT_POINT13', 'PRECISION_PARKING', 'LOADING', 'LOADED', 'DELIVERING', 'DELIVERED', 'COMPLETED')
AND (SELECT status FROM orders o2 WHERE o2.id = orders.id AND o2.status = 'AT_POINT13') IS NOT NULL
UNION ALL
SELECT
    'DELIVERY_DURATION' as phase,
    COUNT(*) as total_deliveries,
    ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - created_at)))::NUMERIC, 1) as avg_duration_seconds
FROM orders
WHERE status = 'COMPLETED'
AND completed_at IS NOT NULL;
```

**Use Case**: Performance analysis, SLA reporting
**Index**: idx_orders_created_completed, idx_orders_status
**Performance**: < 50ms

### 5.2 Robot Utilization

```sql
-- Robot usage statistics
SELECT
    r.name,
    r.domain_id,
    COUNT(o.id) as total_deliveries,
    COUNT(CASE WHEN o.status = 'COMPLETED' THEN 1 END) as completed_deliveries,
    COUNT(CASE WHEN o.status != 'COMPLETED' THEN 1 END) as active_orders,
    ROUND(AVG(EXTRACT(EPOCH FROM (o.completed_at - o.created_at)))::NUMERIC, 1) as avg_delivery_duration_seconds
FROM robots r
LEFT JOIN orders o ON r.id = o.assigned_serving_bot_id
WHERE r.type LIKE 'SERVING_BOT%'
GROUP BY r.id, r.name, r.domain_id
ORDER BY completed_deliveries DESC;
```

**Use Case**: Robot performance analytics
**Index**: idx_orders_serving_bot_active
**Performance**: < 100ms

### 5.3 Orders per Hour

```sql
-- Throughput analysis
SELECT
    DATE_TRUNC('hour', created_at)::TIMESTAMP as hour,
    COUNT(*) as total_orders,
    COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
    COUNT(CASE WHEN status NOT IN ('COMPLETED', 'CANCELLED') THEN 1 END) as pending,
    ROUND(100.0 * COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) / NULLIF(COUNT(*), 0), 1) as completion_rate_percent
FROM orders
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;
```

**Use Case**: System throughput, capacity planning
**Index**: idx_orders_created_at
**Performance**: < 50ms

---

## Performance & Optimization

### 6.1 Verify Index Usage

```sql
-- Check which indexes are being used
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;
```

**Use Case**: Performance monitoring
**Performance**: < 10ms

### 6.2 Find Unused Indexes

```sql
-- Identify unused indexes that can be removed
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
AND idx_scan = 0
AND indexname NOT LIKE 'pg_toast%'
ORDER BY tablename, indexname;
```

**Use Case**: Maintenance, optimize storage
**Performance**: < 10ms

### 6.3 Query Execution Plan

```sql
-- Analyze query performance
EXPLAIN ANALYZE
SELECT
    o.id,
    o.table_number,
    o.status,
    r.name,
    r.domain_id
FROM orders o
LEFT JOIN robots r ON o.assigned_serving_bot_id = r.id
WHERE o.status = 'DELIVERING'
AND o.assigned_serving_bot_id IS NOT NULL;
```

**Use Case**: Query optimization
**Performance**: < 100ms (with ANALYZE)

### 6.4 Table Size Analysis

```sql
-- Check table sizes
SELECT
    schemaname,
    tablename,
    ROUND(pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024::NUMERIC, 2) as size_mb
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Use Case**: Storage monitoring
**Performance**: < 10ms

---

## Best Practices

### Connection Pooling

```python
# Use connection pooling in application
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://kitchmatic_user:password@localhost:5432/kitchmatic',
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600
)
```

### Transaction Handling

```sql
-- Always use transactions for related updates
BEGIN;

UPDATE orders SET status = 'AT_POINT13' WHERE id = 'order-uuid';
INSERT INTO fms_event_log (event_type, order_id, occurred_at)
VALUES ('GOAL_REACHED', 'order-uuid', NOW());
UPDATE robots SET status = 'BUSY' WHERE id = 'robot-uuid';

COMMIT;
```

### Error Handling

```sql
-- Use RETURNING clause to verify updates
UPDATE orders
SET status = 'DELIVERING'
WHERE id = 'order-uuid'
AND status = 'LOADED'
RETURNING id, status;

-- Check if update actually happened
-- If no rows returned, order was not in expected state
```

---

## References

- Database Architecture: `/home/gw/kitchmatics/roscamp-repo-1/database/DATABASE_ARCHITECTURE.md`
- Schema Definition: `/home/gw/kitchmatics/roscamp-repo-1/database/schema.sql`
- FMS Implementation: `/home/gw/kitchmatics/roscamp-repo-1/fms/`
- PostgreSQL Docs: https://www.postgresql.org/docs/current/
