-- ========================================
-- Kitchmatic Test Data
-- Sample data for FMS testing and development
-- ========================================
--
-- Run: psql -U kitchmatic_user -d kitchmatic -f database/test_data.sql
--

-- ========================================
-- Section 1: Verify Current Data
-- ========================================

-- Check existing menus
SELECT '=== Current Menus ===' as section;
SELECT id, name, price, category FROM menus;

-- Check existing ingredients
SELECT '=== Current Ingredients ===' as section;
SELECT id, name, unit, category FROM ingredients;

-- Check existing robots
SELECT '=== Current Robots ===' as section;
SELECT id, name, type, status, domain_id, parking_spot FROM robots;


-- ========================================
-- Section 2: Insert Test Orders
-- ========================================

-- Clear test orders (optional - comment out for production)
-- DELETE FROM orders WHERE table_number IN ('TEST_T01', 'TEST_T02', 'TEST_T03', 'TEST_T04');

-- Sample orders for FMS testing
INSERT INTO orders (
    table_number, menu_id, quantity, status, voice_order
) VALUES
    ('TEST_T01', 'M001', 1, 'PENDING', false),
    ('TEST_T02', 'M002', 2, 'PENDING', false),
    ('TEST_T03', 'M003', 1, 'PENDING', false),
    ('TEST_T04', 'M001', 1, 'ORDERED', false)
ON CONFLICT DO NOTHING;

-- Display inserted orders
SELECT '=== Test Orders Created ===' as section;
SELECT id, table_number, menu_id, quantity, status, created_at
FROM orders
WHERE table_number LIKE 'TEST_%'
ORDER BY created_at DESC;


-- ========================================
-- Section 3: Assign Robots to Orders
-- ========================================

-- Get robot IDs for assignment
WITH robot_ids AS (
    SELECT id, type FROM robots WHERE type LIKE 'SERVING_BOT%'
)
UPDATE orders
SET assigned_serving_bot_id = (
    SELECT id FROM robot_ids
    WHERE type = 'SERVING_BOT_1'
    LIMIT 1
)
WHERE table_number = 'TEST_T01' AND assigned_serving_bot_id IS NULL;

WITH robot_ids AS (
    SELECT id, type FROM robots WHERE type LIKE 'SERVING_BOT%'
)
UPDATE orders
SET assigned_serving_bot_id = (
    SELECT id FROM robot_ids
    WHERE type = 'SERVING_BOT_2'
    LIMIT 1
)
WHERE table_number = 'TEST_T02' AND assigned_serving_bot_id IS NULL;

-- Display updated orders
SELECT '=== Orders with Robot Assignments ===' as section;
SELECT
    o.id,
    o.table_number,
    o.status,
    r.name as assigned_robot,
    r.domain_id,
    r.parking_spot
FROM orders o
LEFT JOIN robots r ON o.assigned_serving_bot_id = r.id
WHERE o.table_number LIKE 'TEST_%'
ORDER BY o.created_at DESC;


-- ========================================
-- Section 4: FMS State Transition Test
-- ========================================

-- Update orders through delivery flow
UPDATE orders
SET status = 'AT_POINT13', updated_at = NOW()
WHERE table_number = 'TEST_T01' AND status = 'ORDERED';

UPDATE orders
SET status = 'PRECISION_PARKING', updated_at = NOW()
WHERE table_number = 'TEST_T02' AND status = 'ORDERED';

-- Display order progression
SELECT '=== Order Status Progression ===' as section;
SELECT
    table_number,
    status,
    created_at,
    updated_at,
    EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER as elapsed_seconds
FROM orders
WHERE table_number LIKE 'TEST_%'
ORDER BY table_number;


-- ========================================
-- Section 5: FMS Event Log Test
-- ========================================

-- Insert sample events
INSERT INTO fms_event_log (event_type, order_id, robot_id, details, occurred_at)
SELECT
    'ORDER_CREATED' as event_type,
    o.id as order_id,
    o.assigned_serving_bot_id as robot_id,
    jsonb_build_object(
        'table_number', o.table_number,
        'menu_id', o.menu_id,
        'quantity', o.quantity
    ) as details,
    o.created_at as occurred_at
FROM orders o
WHERE o.table_number LIKE 'TEST_%'
AND NOT EXISTS (
    SELECT 1 FROM fms_event_log
    WHERE event_type = 'ORDER_CREATED' AND order_id = o.id
)
ON CONFLICT DO NOTHING;

-- Display event log
SELECT '=== FMS Event Log ===' as section;
SELECT
    event_type,
    order_id,
    (SELECT table_number FROM orders WHERE id = order_id) as table_number,
    details,
    occurred_at
FROM fms_event_log
WHERE order_id IN (SELECT id FROM orders WHERE table_number LIKE 'TEST_%')
ORDER BY occurred_at DESC;


-- ========================================
-- Section 6: FMS Navigation State Test
-- ========================================

-- Insert sample navigation states
INSERT INTO fms_navigation_states (
    order_id, robot_id, current_x, current_y, current_yaw,
    target_x, target_y, target_yaw, navigation_status
)
SELECT
    o.id,
    o.assigned_serving_bot_id,
    0.585, 0.085, 0.0,  -- Starting position (parking spot)
    0.585, 0.63, 0.0,   -- Target position (point13)
    'NAVIGATING'
FROM orders o
WHERE o.table_number = 'TEST_T01'
AND o.assigned_serving_bot_id IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM fms_navigation_states
    WHERE order_id = o.id
)
ON CONFLICT DO NOTHING;

-- Display navigation states
SELECT '=== FMS Navigation States ===' as section;
SELECT
    ns.order_id,
    (SELECT table_number FROM orders WHERE id = ns.order_id) as table_number,
    (SELECT name FROM robots WHERE id = ns.robot_id) as robot_name,
    ROUND(ns.current_x::NUMERIC, 3) as current_x,
    ROUND(ns.current_y::NUMERIC, 3) as current_y,
    ROUND(ns.target_x::NUMERIC, 3) as target_x,
    ROUND(ns.target_y::NUMERIC, 3) as target_y,
    ns.navigation_status,
    ns.started_at
FROM fms_navigation_states ns
ORDER BY ns.started_at DESC;


-- ========================================
-- Section 7: Robot Status Check
-- ========================================

SELECT '=== Robot Status & Battery ===' as section;
SELECT
    name,
    type,
    domain_id,
    namespace,
    status,
    battery_voltage,
    parking_spot,
    last_heartbeat
FROM robots
WHERE type LIKE 'SERVING_BOT%'
ORDER BY domain_id;


-- ========================================
-- Section 8: Available Robots View
-- ========================================

SELECT '=== Available Robots (using view) ===' as section;
SELECT
    name,
    type,
    domain_id,
    status,
    battery_voltage,
    availability
FROM v_available_robots
ORDER BY availability DESC;


-- ========================================
-- Section 9: Active Orders View
-- ========================================

SELECT '=== Active Orders by Robot (using view) ===' as section;
SELECT
    robot_name,
    domain_id,
    robot_status,
    battery_voltage,
    table_number,
    order_status,
    COALESCE(elapsed_seconds, 0) as elapsed_seconds
FROM v_active_orders_by_robot
WHERE order_id IS NOT NULL
ORDER BY robot_id, order_created_at DESC;


-- ========================================
-- Section 10: Order Timeline View
-- ========================================

SELECT '=== Order Timeline (using view) ===' as section;
SELECT
    table_number,
    status,
    assigned_robot,
    battery_voltage,
    elapsed_seconds,
    estimated_total_seconds
FROM v_order_timeline
WHERE table_number LIKE 'TEST_%'
ORDER BY created_at DESC;


-- ========================================
-- Section 11: Test Data Summary
-- ========================================

SELECT '=== TEST DATA SUMMARY ===' as section;

-- Count statistics
SELECT
    (SELECT COUNT(*) FROM orders WHERE table_number LIKE 'TEST_%') as test_orders,
    (SELECT COUNT(*) FROM fms_event_log WHERE order_id IN (SELECT id FROM orders WHERE table_number LIKE 'TEST_%')) as event_log_entries,
    (SELECT COUNT(*) FROM fms_navigation_states WHERE order_id IN (SELECT id FROM orders WHERE table_number LIKE 'TEST_%')) as navigation_states,
    (SELECT COUNT(*) FROM robots WHERE type LIKE 'SERVING_BOT%') as available_serving_robots,
    (SELECT COUNT(*) FROM robots WHERE type LIKE 'ARM_%') as available_robot_arms;

-- Cleanup instructions
SELECT
    'To remove test data, run:' as info,
    'DELETE FROM orders WHERE table_number LIKE ''TEST_%'';' as command
UNION ALL
SELECT
    'Tables created:' as info,
    'fms_event_log, fms_navigation_states' as command;


-- ========================================
-- Section 12: FMS Integration Checklist
-- ========================================

SELECT '=== FMS Integration Checklist ===' as section;

SELECT
    CASE
        WHEN COUNT(*) > 0 THEN '✓'
        ELSE '✗'
    END || ' ' || item as checklist_item
FROM (
    SELECT 'Robots table extended (domain_id, parking_spot)' as item, COUNT(*) as count
    FROM robots WHERE domain_id IS NOT NULL
    UNION ALL
    SELECT 'fms_navigation_states table created', COUNT(*)
    FROM fms_navigation_states
    UNION ALL
    SELECT 'fms_event_log table created', COUNT(*)
    FROM fms_event_log
    UNION ALL
    SELECT 'Test orders created', COUNT(*)
    FROM orders WHERE table_number LIKE 'TEST_%'
    UNION ALL
    SELECT 'v_available_robots view created', CASE WHEN EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'v_available_robots') THEN 1 ELSE 0 END
    UNION ALL
    SELECT 'v_active_orders_by_robot view created', CASE WHEN EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'v_active_orders_by_robot') THEN 1 ELSE 0 END
    UNION ALL
    SELECT 'v_order_timeline view created', CASE WHEN EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'v_order_timeline') THEN 1 ELSE 0 END
) checklist
WHERE count > 0;

-- ========================================
-- End of test data script
-- ========================================
