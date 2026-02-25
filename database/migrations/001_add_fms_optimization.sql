-- ========================================
-- FMS Optimization Schema Migration
-- Kitchmatic Database v1.1
-- ========================================
--
-- This migration adds FMS-specific tables and optimizations:
-- 1. Robot domain ID and battery tracking
-- 2. FMS navigation state tracking
-- 3. Event audit logging
-- 4. Performance indexes
--
-- Run: psql -U kitchmatic_user -d kitchmatic -f migrations/001_add_fms_optimization.sql
--

-- ========================================
-- Step 1: Extend robots table
-- ========================================

ALTER TABLE robots
ADD COLUMN IF NOT EXISTS domain_id INTEGER UNIQUE,
ADD COLUMN IF NOT EXISTS parking_spot VARCHAR(50),
ADD COLUMN IF NOT EXISTS battery_voltage FLOAT DEFAULT 0.0,
ADD COLUMN IF NOT EXISTS namespace VARCHAR(50);

-- Add constraint for domain_id (optional but recommended)
-- Note: Only for serving robots, not robot arms
-- ALTER TABLE robots
-- ADD CONSTRAINT chk_serving_bot_domain_id
-- CHECK (
--     (type LIKE 'SERVING_BOT%' AND domain_id IS NOT NULL)
--     OR (type LIKE 'ARM_%' AND domain_id IS NULL)
-- );

-- Update existing serving robots with domain IDs
UPDATE robots SET domain_id = 11, parking_spot = 'pinky1_spot', namespace = '/pinky1'
WHERE type = 'SERVING_BOT_1' AND domain_id IS NULL;

UPDATE robots SET domain_id = 12, parking_spot = 'pinky2_spot', namespace = '/pinky2'
WHERE type = 'SERVING_BOT_2' AND domain_id IS NULL;

UPDATE robots SET domain_id = 13, parking_spot = 'pinky3_spot', namespace = '/pinky3'
WHERE type = 'SERVING_BOT_3' AND domain_id IS NULL;

UPDATE robots SET domain_id = 14 WHERE type = 'ARM_1' AND domain_id IS NULL;
UPDATE robots SET domain_id = 15 WHERE type = 'ARM_2' AND domain_id IS NULL;


-- ========================================
-- Step 2: Extend orders table status values
-- ========================================

-- NOTE: If you get error "invalid input value for enum", use this approach:
-- PostgreSQL status is VARCHAR, not ENUM, so this should work:

-- Verify current status values are compatible
-- SELECT DISTINCT status FROM orders;

-- Add missing status values to constraint if using CHECK:
-- The current CHECK constraint already allows the states we need


-- ========================================
-- Step 3: Create FMS Navigation State Table
-- ========================================

CREATE TABLE IF NOT EXISTS fms_navigation_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    robot_id UUID NOT NULL REFERENCES robots(id),

    -- Current position in map frame
    current_x FLOAT,
    current_y FLOAT,
    current_yaw FLOAT,

    -- Target position
    target_x FLOAT,
    target_y FLOAT,
    target_yaw FLOAT,

    -- Navigation state
    navigation_status VARCHAR(20) NOT NULL DEFAULT 'IDLE',
    -- Values: IDLE, NAVIGATING, REACHED, ABORTED, TIMEOUT

    -- Timestamps
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_nav_status CHECK (navigation_status IN (
        'IDLE', 'NAVIGATING', 'REACHED', 'ABORTED', 'TIMEOUT'
    ))
);

-- Indexes for FMS navigation queries
CREATE INDEX IF NOT EXISTS idx_fms_nav_order ON fms_navigation_states(order_id);
CREATE INDEX IF NOT EXISTS idx_fms_nav_robot ON fms_navigation_states(robot_id, navigation_status);
CREATE INDEX IF NOT EXISTS idx_fms_nav_status ON fms_navigation_states(navigation_status);
CREATE INDEX IF NOT EXISTS idx_fms_nav_time ON fms_navigation_states(started_at DESC);


-- ========================================
-- Step 4: Create FMS Event Log Table
-- ========================================

CREATE TABLE IF NOT EXISTS fms_event_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    -- Values: ORDER_CREATED, ROBOT_ASSIGNED, NAVIGATION_START, GOAL_REACHED,
    --         PRECISION_PARKED, FOOD_LOADED, DELIVERY_COMPLETE, ERROR, etc.

    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    robot_id UUID REFERENCES robots(id),

    -- Event details as JSON for flexibility
    details JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,

    -- Timestamp
    occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_event_type CHECK (event_type IN (
        'ORDER_CREATED', 'ROBOT_ASSIGNED', 'NAVIGATION_START', 'GOAL_REACHED',
        'PRECISION_PARKED', 'FOOD_LOADED', 'DELIVERY_COMPLETE', 'ERROR',
        'ROBOT_PARKING', 'CYCLE_COMPLETE', 'NAVIGATION_FAILED', 'TIMEOUT'
    ))
);

-- Indexes for event log queries
CREATE INDEX IF NOT EXISTS idx_fms_event_type ON fms_event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_fms_event_order ON fms_event_log(order_id);
CREATE INDEX IF NOT EXISTS idx_fms_event_robot ON fms_event_log(robot_id);
CREATE INDEX IF NOT EXISTS idx_fms_event_time ON fms_event_log(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_fms_event_error ON fms_event_log(event_type, occurred_at DESC)
WHERE event_type = 'ERROR';


-- ========================================
-- Step 5: Add Performance Indexes
-- ========================================

-- Robot status lookups (commonly used by FMS task manager)
CREATE INDEX IF NOT EXISTS idx_robots_type_status ON robots(type, status);

-- Order robot assignment queries
CREATE INDEX IF NOT EXISTS idx_orders_serving_bot_active ON orders(assigned_serving_bot_id)
WHERE status IN ('AT_POINT13', 'PRECISION_PARKING', 'LOADING', 'LOADED', 'DELIVERING', 'DELIVERED');

CREATE INDEX IF NOT EXISTS idx_orders_robot_arm_active ON orders(assigned_robot_arm_id)
WHERE status IN ('LOADING', 'LOADED');

-- Composite index for FMS delivery queries
CREATE INDEX IF NOT EXISTS idx_orders_status_robot_table ON orders(status, assigned_serving_bot_id, table_number)
WHERE status IN ('DELIVERING', 'DELIVERED', 'COMPLETED');

-- Time-range queries for analytics
CREATE INDEX IF NOT EXISTS idx_orders_created_completed ON orders(created_at, completed_at)
WHERE status = 'COMPLETED';

-- Inventory low stock alerts
CREATE INDEX IF NOT EXISTS idx_inventory_low_stock ON inventory(ingredient_id)
WHERE current_stock < min_threshold;

-- Inventory transaction analysis
CREATE INDEX IF NOT EXISTS idx_inv_trans_order_time ON inventory_transactions(order_id, transaction_at DESC);

-- Quality check recent results
CREATE INDEX IF NOT EXISTS idx_quality_recent ON quality_check_results(order_id, checked_at DESC)
WHERE status IN ('NORMAL', 'ABNORMAL');


-- ========================================
-- Step 6: Add Helper Views (Optional)
-- ========================================

-- View: Active orders by robot
CREATE OR REPLACE VIEW v_active_orders_by_robot AS
SELECT
    r.id as robot_id,
    r.name as robot_name,
    r.type as robot_type,
    r.domain_id,
    r.status as robot_status,
    r.battery_voltage,
    o.id as order_id,
    o.table_number,
    o.status as order_status,
    o.created_at as order_created_at,
    EXTRACT(EPOCH FROM (NOW() - o.created_at)) as elapsed_seconds
FROM robots r
LEFT JOIN orders o ON (
    (r.type LIKE 'SERVING_BOT%' AND r.id = o.assigned_serving_bot_id)
    OR (r.type LIKE 'ARM_%' AND r.id = o.assigned_robot_arm_id)
)
WHERE o.status NOT IN ('COMPLETED', 'CANCELLED')
   OR o.id IS NULL
ORDER BY r.id, o.created_at;

-- View: Robot availability
CREATE OR REPLACE VIEW v_available_robots AS
SELECT
    id,
    name,
    type,
    domain_id,
    status,
    battery_voltage,
    parking_spot,
    CASE
        WHEN status = 'IDLE' AND battery_voltage > 20.0 THEN 'AVAILABLE'
        WHEN status = 'IDLE' AND battery_voltage <= 20.0 THEN 'LOW_BATTERY'
        WHEN status = 'BUSY' THEN 'BUSY'
        ELSE 'UNAVAILABLE'
    END as availability
FROM robots
WHERE type LIKE 'SERVING_BOT%'
ORDER BY availability DESC, battery_voltage DESC;

-- View: Order progress timeline
CREATE OR REPLACE VIEW v_order_timeline AS
SELECT
    o.id,
    o.table_number,
    o.status,
    o.created_at,
    o.updated_at,
    o.completed_at,
    EXTRACT(EPOCH FROM (NOW() - o.created_at))::INTEGER as elapsed_seconds,
    CASE
        WHEN o.status = 'COMPLETED' THEN EXTRACT(EPOCH FROM (o.completed_at - o.created_at))::INTEGER
        WHEN o.status IN ('PENDING', 'ORDERED', 'AT_POINT13') THEN NULL
        ELSE EXTRACT(EPOCH FROM (NOW() - o.created_at))::INTEGER
    END as estimated_total_seconds,
    COALESCE(r.name, 'Unassigned') as assigned_robot,
    r.battery_voltage
FROM orders o
LEFT JOIN robots r ON o.assigned_serving_bot_id = r.id
ORDER BY o.created_at DESC;


-- ========================================
-- Step 7: Migration Verification
-- ========================================

-- Display migration results
DO $$
DECLARE
    tables_count INTEGER;
    indexes_count INTEGER;
BEGIN
    -- Count new tables
    SELECT COUNT(*) INTO tables_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN ('fms_navigation_states', 'fms_event_log');

    -- Count new indexes
    SELECT COUNT(*) INTO indexes_count
    FROM pg_indexes
    WHERE schemaname = 'public'
    AND indexname LIKE 'idx_fms_%' OR indexname LIKE 'idx_robots_type%' OR indexname LIKE 'idx_orders_%'
    OR indexname LIKE 'idx_inventory_%' OR indexname LIKE 'idx_quality_%' OR indexname LIKE 'idx_inv_trans_%';

    RAISE NOTICE '✓ Migration completed successfully!';
    RAISE NOTICE '  Tables created: %', tables_count;
    RAISE NOTICE '  New indexes created: %', indexes_count;
    RAISE NOTICE '  Robot domain IDs updated: 5 robots';
END $$;

-- ========================================
-- Migration end
-- ========================================
