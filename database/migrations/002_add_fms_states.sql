-- Migration: Add FMS-specific order and robot states
-- Version: 002
-- Date: 2026-02-25
-- Description: Add states required for FMS delivery flow

-- ========================================
-- 1. Update orders status constraint
-- ========================================

-- Drop existing constraint
ALTER TABLE orders DROP CONSTRAINT IF EXISTS chk_status;

-- Add new constraint with FMS states
ALTER TABLE orders ADD CONSTRAINT chk_status CHECK (status IN (
    -- Initial states
    'PENDING',           -- Order created, waiting for assignment
    'ASSIGNED',          -- Robot assigned to order

    -- Navigation to pickup
    'TO_PICKUP',         -- Robot navigating to pickup_spot
    'AT_PICKUP',         -- Robot arrived at pickup_spot (goal_arrived sent)

    -- Precision parking and loading (external teams)
    'PRECISION_PARKING', -- Precision control in progress
    'LOADING',           -- Robot arm loading food
    'LOADED',            -- Food loaded, ready for delivery

    -- Delivery
    'TO_TABLE',          -- Robot navigating to table
    'AT_TABLE',          -- Robot at table, waiting for customer
    'DELIVERED',         -- Customer confirmed delivery

    -- Completion
    'RETURNING',         -- Robot returning to parking spot
    'COMPLETED',         -- Order fully completed, robot parked

    -- Error states
    'CANCELLED',         -- Order cancelled
    'FAILED',            -- Order failed (navigation error, etc.)
    'HALTED'             -- Emergency stop
));

-- ========================================
-- 2. Update robots status constraint
-- ========================================

-- Drop existing constraint
ALTER TABLE robots DROP CONSTRAINT IF EXISTS chk_robot_status;

-- Add new constraint with FMS states
ALTER TABLE robots ADD CONSTRAINT chk_robot_status CHECK (status IN (
    'IDLE',              -- Robot at parking spot, available
    'MOVING_TO_PICKUP',  -- Navigating to pickup_spot
    'AT_PICKUP',         -- At pickup_spot, waiting for loading
    'LOADING',           -- Robot arm loading food
    'MOVING_TO_TABLE',   -- Navigating to customer table
    'AT_TABLE',          -- At table, waiting for delivery confirmation
    'RETURNING',         -- Returning to parking spot
    'ERROR',             -- Error state
    'HALTED'             -- Emergency stop
));

-- ========================================
-- 3. Add sauce_type column to orders
-- ========================================

ALTER TABLE orders ADD COLUMN IF NOT EXISTS sauce_type VARCHAR(20) DEFAULT '';

-- ========================================
-- 4. Add domain_id to robots if not exists
-- ========================================

ALTER TABLE robots ADD COLUMN IF NOT EXISTS domain_id INTEGER UNIQUE;
ALTER TABLE robots ADD COLUMN IF NOT EXISTS parking_spot VARCHAR(50);

-- Update existing robots with domain IDs
UPDATE robots SET domain_id = 11, parking_spot = 'pinky1_spot' WHERE type = 'SERVING_BOT_1' AND domain_id IS NULL;
UPDATE robots SET domain_id = 12, parking_spot = 'pinky2_spot' WHERE type = 'SERVING_BOT_2' AND domain_id IS NULL;
UPDATE robots SET domain_id = 13, parking_spot = 'pinky3_spot' WHERE type = 'SERVING_BOT_3' AND domain_id IS NULL;
UPDATE robots SET domain_id = 20 WHERE type = 'ARM_1' AND domain_id IS NULL;
UPDATE robots SET domain_id = 21 WHERE type = 'ARM_2' AND domain_id IS NULL;

-- ========================================
-- 5. Create index for faster status queries
-- ========================================

CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_robots_status_type ON robots(status, type);

-- ========================================
-- 6. Verification
-- ========================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 002_add_fms_states completed successfully';
    RAISE NOTICE 'Orders status values: PENDING, ASSIGNED, TO_PICKUP, AT_PICKUP, PRECISION_PARKING, LOADING, LOADED, TO_TABLE, AT_TABLE, DELIVERED, RETURNING, COMPLETED, CANCELLED, FAILED, HALTED';
    RAISE NOTICE 'Robots status values: IDLE, MOVING_TO_PICKUP, AT_PICKUP, LOADING, MOVING_TO_TABLE, AT_TABLE, RETURNING, ERROR, HALTED';
END $$;
