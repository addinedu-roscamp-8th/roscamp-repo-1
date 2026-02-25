# Kitchmatic Database Architecture and Optimization

**Last Updated**: 2026-02-25
**Database Architect**: Database Team
**Status**: Verified & Optimized

---

## 1. Current Schema Analysis

### 1.1 Database Overview

- **DBMS**: PostgreSQL 16
- **Database Name**: `kitchmatic`
- **User**: `kitchmatic_user`
- **Connection**: TCP/IP on port 5432

### 1.2 Table Structure

#### Core Business Tables

1. **menus** - Menu catalog
   - Primary Key: `id` (VARCHAR(10))
   - Stores menu items with pricing and availability
   - Data: 3 sandwich items (M001-M003)

2. **ingredients** - Raw materials inventory
   - Primary Key: `id` (VARCHAR(10))
   - Tracks available ingredients by category
   - Data: 6 ingredients (bread, cheese, tomato, lettuce, ham, mushroom)

3. **recipes** - Menu preparation instructions
   - Primary Key: `id` (UUID)
   - Foreign Key: `menu_id` → menus
   - Stores estimated preparation time

4. **recipe_steps** - Step-by-step cooking instructions
   - Primary Key: `id` (UUID)
   - Composite Unique: (recipe_id, step_order)
   - Foreign Key: `recipe_id` → recipes (ON DELETE CASCADE)
   - Tracks robot arm assignment (ARM_1, ARM_2)

5. **inventory** - Current stock levels by location
   - Primary Key: `id` (UUID)
   - Unique: (ingredient_id, location)
   - Locations: STOCK_AREA, INGREDIENT_BED
   - Tracks min/max thresholds

6. **inventory_transactions** - Audit trail for inventory
   - Primary Key: `id` (UUID)
   - Foreign Keys: inventory_id, order_id, robot_id
   - Transaction Types: REPLENISHMENT, CONSUMPTION, REPLACEMENT
   - Records before/after stock levels

7. **robots** - Mobile robots and robot arms
   - Primary Key: `id` (UUID)
   - Unique: `name`
   - Types: ARM_1, ARM_2, SERVING_BOT_1/2/3
   - Status: IDLE, BUSY, ERROR, HALTED
   - Tracks IP, port, and last heartbeat

8. **orders** - Customer orders
   - Primary Key: `id` (UUID)
   - Foreign Keys: robot_arm_id, serving_bot_id → robots
   - Status: PENDING → CONFIRMED → COOKING → READY → INSPECTED → DELIVERING → DELIVERED → COMPLETED
   - Tracks table number, menu, quantity, timing

9. **quality_check_results** - Food quality inspection
   - Primary Key: `id` (UUID)
   - Foreign Keys: order_id → orders, robot_arm_id → robots
   - Status: NORMAL, ABNORMAL
   - Confidence score (0-100)

### 1.3 Current Issues Identified

1. **Missing Namespace Mapping**
   - Database uses UUID for robot identification
   - ROS system uses namespaces (/pinky1, /pinky2, /pinky3)
   - Need mapping between UUID and namespace/robot_id

2. **Incomplete Order State Machine**
   - Current status values don't align with FMS delivery flow:
     - Missing: AT_POINT13, LOADING, RETURNING
     - Extra: CONFIRMED, COOKING (kitchen-specific)

3. **Missing FMS-Specific Fields**
   - Orders lack: current_position, target_position, assigned_table_number
   - Robots lack: battery_voltage, domain_id, parking_spot

4. **No Audit Logging**
   - No event log table for tracking state transitions
   - Difficult to debug order failures

5. **Weak Foreign Key Constraints**
   - Some nullable foreign keys should be non-nullable during delivery

---

## 2. Order State Transition Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Order Lifecycle                           │
└─────────────────────────────────────────────────────────────┘

    [PENDING]
        ↓
    [ORDERED] ← Order received from GUI
        ↓
    [AT_POINT13] ← Robot arrived at kitchen pickup point
        ↓
    [PRECISION_PARKING] ← External: Precision team parks robot
        ↓
    [LOADING] ← Robot arm loading food
        ↓
    [LOADED] ← Food loaded, ready for delivery
        ↓
    [DELIVERING] ← Robot navigating to customer table
        ↓
    [DELIVERED] ← Robot at table, waiting for customer
        ↓
    [COMPLETED] ← Customer clicked delivery complete
        ↓
    [RETURNED] ← Robot returned to parking spot

OR (Error paths):

    [ORDERED] → [CANCELLED] ← Order cancelled before cooking
    [LOADING] → [FAILED] ← Loading failed, retry
    [DELIVERING] → [ABORTED] ← Navigation failed
```

### 2.1 State Responsibility Matrix

| State | Owner | Duration | Next States |
|-------|-------|----------|-------------|
| PENDING | System | < 1s | ORDERED |
| ORDERED | FMS | Variable | AT_POINT13, CANCELLED |
| AT_POINT13 | FMS | 0.5s | PRECISION_PARKING |
| PRECISION_PARKING | Precision Team | 5-30s | LOADING (mock: 2s) |
| LOADING | Robot Arm | 30-60s | LOADED (mock: 3s) |
| LOADED | FMS | 0.5s | DELIVERING |
| DELIVERING | FMS | 10-60s | DELIVERED, ABORTED |
| DELIVERED | GUI | User-driven | COMPLETED |
| COMPLETED | System | < 1s | RETURNED |
| RETURNED | FMS | 20-40s | (cycle complete) |

---

## 3. Database Optimization: Indexes

### 3.1 Current Indexes

```sql
-- Existing indexes
CREATE INDEX idx_recipe_steps_recipe ON recipe_steps(recipe_id);
CREATE INDEX idx_inv_trans_inventory ON inventory_transactions(inventory_id);
CREATE INDEX idx_inv_trans_time ON inventory_transactions(transaction_at DESC);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_table_number ON orders(table_number);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_quality_order ON quality_check_results(order_id);
CREATE INDEX idx_quality_status ON quality_check_results(status);
CREATE INDEX idx_quality_time ON quality_check_results(checked_at DESC);
```

### 3.2 Recommended Additional Indexes

```sql
-- Performance indexes for common queries

-- 1. Order lookup by robot assignment
CREATE INDEX idx_orders_serving_bot ON orders(assigned_serving_bot_id)
WHERE status IN ('AT_POINT13', 'PRECISION_PARKING', 'LOADING', 'LOADED', 'DELIVERING', 'DELIVERED');

CREATE INDEX idx_orders_robot_arm ON orders(assigned_robot_arm_id)
WHERE status IN ('LOADING', 'LOADED');

-- 2. Robot status lookups
CREATE INDEX idx_robots_type_status ON robots(type, status);
CREATE INDEX idx_robots_enabled ON robots(name)
WHERE type LIKE 'SERVING_BOT%';

-- 3. Inventory lookups
CREATE INDEX idx_inventory_current_stock ON inventory(ingredient_id)
WHERE current_stock < min_threshold;

-- 4. Composite indexes for FMS queries
CREATE INDEX idx_orders_status_robot_table ON orders(status, assigned_serving_bot_id, table_number)
WHERE status IN ('DELIVERING', 'DELIVERED', 'COMPLETED');

-- 5. Time-range queries for analytics
CREATE INDEX idx_orders_created_completed ON orders(created_at, completed_at)
WHERE status = 'COMPLETED';

-- 6. Inventory transaction analysis
CREATE INDEX idx_inv_trans_order_time ON inventory_transactions(order_id, transaction_at);
```

### 3.3 Index Usage Guidelines

- **High-frequency Queries**: Use composite indexes
- **Range Queries**: Include DESC order for time fields
- **Partial Indexes**: Filter WHERE clause for conditional lookups
- **Maintenance**: Monitor index bloat and REINDEX monthly

---

## 4. Foreign Key Relationships

### 4.1 Current Foreign Keys

```
orders.assigned_robot_arm_id → robots.id (nullable)
orders.assigned_serving_bot_id → robots.id (nullable)
orders.menu_id → menus.id (not null)

recipe_steps.recipe_id → recipes.id (CASCADE)
recipes.menu_id → menus.id

inventory.ingredient_id → ingredients.id
inventory_transactions.inventory_id → inventory.id
inventory_transactions.order_id → orders.id (nullable)
inventory_transactions.robot_id → robots.id (nullable)

quality_check_results.order_id → orders.id
quality_check_results.robot_arm_id → robots.id
```

### 4.2 Recommended FK Constraints

```sql
-- Make robot assignment non-nullable during delivery phases
ALTER TABLE orders ADD CHECK (
    CASE
        WHEN status IN ('AT_POINT13', 'PRECISION_PARKING', 'LOADING', 'LOADED', 'DELIVERING', 'DELIVERED', 'COMPLETED', 'RETURNED')
        THEN assigned_serving_bot_id IS NOT NULL
        ELSE TRUE
    END
);

-- Ensure quality checks are only for loaded/delivered orders
ALTER TABLE quality_check_results ADD CHECK (
    EXISTS (
        SELECT 1 FROM orders o
        WHERE o.id = quality_check_results.order_id
        AND o.status IN ('LOADED', 'DELIVERING', 'DELIVERED', 'COMPLETED')
    )
);
```

---

## 5. Schema Extensions for FMS

### 5.1 Robot Domain ID Mapping

Add to `robots` table:

```sql
ALTER TABLE robots ADD COLUMN domain_id INTEGER UNIQUE;
ALTER TABLE robots ADD COLUMN parking_spot VARCHAR(50);
ALTER TABLE robots ADD COLUMN battery_voltage FLOAT DEFAULT 0.0;

-- Update robot records with domain IDs
UPDATE robots SET domain_id = 11, parking_spot = 'pinky1_spot'
WHERE name = 'SERVING_BOT_1';
UPDATE robots SET domain_id = 12, parking_spot = 'pinky2_spot'
WHERE name = 'SERVING_BOT_2';
UPDATE robots SET domain_id = 13, parking_spot = 'pinky3_spot'
WHERE name = 'SERVING_BOT_3';
UPDATE robots SET domain_id = 14 WHERE name = 'ARM_1';
UPDATE robots SET domain_id = 15 WHERE name = 'ARM_2';
```

### 5.2 Navigation State Tracking

New table for FMS operations:

```sql
CREATE TABLE fms_navigation_states (
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
    navigation_status VARCHAR(20) NOT NULL,
    -- Values: IDLE, NAVIGATING, REACHED, ABORTED, TIMEOUT

    -- Timestamps
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_nav_status CHECK (navigation_status IN (
        'IDLE', 'NAVIGATING', 'REACHED', 'ABORTED', 'TIMEOUT'
    ))
);

CREATE INDEX idx_fms_nav_order ON fms_navigation_states(order_id);
CREATE INDEX idx_fms_nav_robot ON fms_navigation_states(robot_id, navigation_status);
CREATE INDEX idx_fms_nav_status ON fms_navigation_states(navigation_status);
```

### 5.3 Event Audit Log

For debugging and monitoring:

```sql
CREATE TABLE fms_event_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    -- Values: ORDER_CREATED, ROBOT_ASSIGNED, NAVIGATION_START, GOAL_REACHED,
    --         PRECISION_PARKED, FOOD_LOADED, DELIVERY_COMPLETE, ERROR

    order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
    robot_id UUID REFERENCES robots(id),

    -- Event details
    details JSONB,
    error_message TEXT,

    -- Timestamp
    occurred_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_event_type CHECK (event_type IN (
        'ORDER_CREATED', 'ROBOT_ASSIGNED', 'NAVIGATION_START', 'GOAL_REACHED',
        'PRECISION_PARKED', 'FOOD_LOADED', 'DELIVERY_COMPLETE', 'ERROR',
        'ROBOT_PARKING', 'CYCLE_COMPLETE'
    ))
);

CREATE INDEX idx_fms_event_type ON fms_event_log(event_type);
CREATE INDEX idx_fms_event_order ON fms_event_log(order_id);
CREATE INDEX idx_fms_event_time ON fms_event_log(occurred_at DESC);
CREATE INDEX idx_fms_event_error ON fms_event_log(event_type, occurred_at DESC)
WHERE event_type = 'ERROR';
```

---

## 6. Database Connection Configuration

### 6.1 Current Setup

File: `/home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/main_server_node.py`

```python
db_config = {
    'db_host': 'localhost',  # TODO: Set database server IP
    'db_port': 5432,
    'db_name': 'kitchmatic',
    'db_user': 'kitchmatic_user',
    'db_password': 'your_password_here'  # TODO: Set secure password
}
```

### 6.2 Recommended Configuration Method

Use environment variables or config file:

**Option 1: Environment Variables**

```bash
export DB_HOST=192.168.1.3
export DB_PORT=5432
export DB_NAME=kitchmatic
export DB_USER=kitchmatic_user
export DB_PASSWORD=secure_password_here
```

**Option 2: Config File** (`database_config.yaml`)

```yaml
database:
  host: ${DB_HOST:-localhost}
  port: ${DB_PORT:-5432}
  name: ${DB_NAME:-kitchmatic}
  user: ${DB_USER:-kitchmatic_user}
  password: ${DB_PASSWORD}  # Must be set via env variable
  pool_size: 10
  max_overflow: 20
  pool_timeout: 30
  echo_sql: false  # Set to true for SQL debugging

# Connection pooling
connection_pool:
  min_size: 2
  max_size: 10
  check_interval: 30
```

**Option 3: .env File** (For local development)

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=kitchmatic
DB_USER=kitchmatic_user
DB_PASSWORD=dev_password_12345
```

---

## 7. Database Setup Procedure

### 7.1 Initial Setup

```bash
#!/bin/bash
# setup_database.sh

set -e

DB_USER="kitchmatic_user"
DB_NAME="kitchmatic"
DB_PASSWORD="${DB_PASSWORD:-default_change_me}"

echo "[1/3] Creating database user..."
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"

echo "[2/3] Creating database..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "[3/3] Applying schema..."
psql -U $DB_USER -d $DB_NAME -f database/schema.sql

echo "✓ Database setup complete"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Host: localhost"
echo "  Port: 5432"
```

### 7.2 Network Configuration (if separate server)

File: `/etc/postgresql/*/main/postgresql.conf`

```conf
# Listen on all interfaces
listen_addresses = '*'

# Connection parameters
max_connections = 100
```

File: `/etc/postgresql/*/main/pg_hba.conf`

```conf
# IPv4 local connections
host    kitchmatic    kitchmatic_user    192.168.1.0/24    md5
```

### 7.3 Backup and Recovery

```bash
# Full backup
pg_dump -U kitchmatic_user -d kitchmatic > backup_$(date +%Y%m%d).sql

# Backup specific table
pg_dump -U kitchmatic_user -d kitchmatic -t orders > orders_backup.sql

# Restore from backup
psql -U kitchmatic_user -d kitchmatic < backup_20260225.sql
```

---

## 8. Test Data Scripts

### 8.1 Populate Sample Data

```sql
-- Insert sample orders for testing
INSERT INTO orders (
    table_number, menu_id, quantity, status,
    assigned_robot_arm_id, assigned_serving_bot_id
) VALUES
    ('T01', 'M001', 1, 'PENDING', NULL, NULL),
    ('T02', 'M002', 2, 'PENDING', NULL, NULL),
    ('T03', 'M003', 1, 'PENDING', NULL, NULL);

-- Verify data
SELECT
    id, table_number, menu_id, status, created_at
FROM orders
ORDER BY created_at DESC;
```

### 8.2 FMS Test Scenarios

```sql
-- Scenario 1: Robot assignment
UPDATE orders
SET assigned_serving_bot_id = (
    SELECT id FROM robots WHERE type = 'SERVING_BOT_1'
)
WHERE table_number = 'T01'
RETURNING id, table_number, assigned_serving_bot_id;

-- Scenario 2: State transition
UPDATE orders
SET status = 'AT_POINT13', updated_at = NOW()
WHERE table_number = 'T01'
RETURNING id, status, updated_at;

-- Scenario 3: View order timeline
SELECT
    o.table_number,
    o.status,
    o.created_at,
    o.updated_at,
    EXTRACT(EPOCH FROM (o.updated_at - o.created_at)) AS elapsed_seconds
FROM orders o
ORDER BY o.created_at DESC;
```

---

## 9. Performance Considerations

### 9.1 Query Optimization

**Common FMS Queries:**

```sql
-- Find next available robot (optimized)
SELECT r.* FROM robots r
WHERE r.type = 'SERVING_BOT_1'
AND r.status = 'IDLE'
LIMIT 1;

-- Check robot battery
SELECT id, name, battery_voltage
FROM robots
WHERE battery_voltage < 20.0 AND type LIKE 'SERVING_BOT%';

-- Get order progress
SELECT
    o.id, o.table_number, o.status, o.created_at,
    EXTRACT(EPOCH FROM (NOW() - o.created_at)) AS elapsed_seconds
FROM orders o
WHERE o.status NOT IN ('COMPLETED', 'CANCELLED')
ORDER BY o.created_at;
```

### 9.2 Connection Pooling

Recommended settings:

```python
# SQLAlchemy example
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:password@host/dbname',
    pool_size=10,        # Keep-alive connections
    max_overflow=20,     # Additional connections when needed
    pool_timeout=30,     # Timeout waiting for connection
    pool_recycle=3600,   # Recycle connections every hour
    echo=False           # Set True for SQL debugging
)
```

### 9.3 Monitoring

```sql
-- Check connection count
SELECT usename, count(*)
FROM pg_stat_activity
GROUP BY usename;

-- Find slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC;

-- Check index usage
SELECT relname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY relname;
```

---

## 10. Validation Checklist

Before deploying to production:

- [ ] Database created with correct name and user
- [ ] Schema applied without errors
- [ ] All foreign keys validated
- [ ] Indexes created and verified
- [ ] Sample data inserted successfully
- [ ] Connection pooling configured
- [ ] Backup procedure tested
- [ ] Recovery procedure tested
- [ ] Query performance baseline established
- [ ] Monitoring queries verified
- [ ] Password stored securely (not in code)
- [ ] Network access restricted (firewall)
- [ ] Regular backup schedule configured

---

## References

- PostgreSQL Documentation: https://www.postgresql.org/docs/
- FMS Requirements: `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md`
- Database Schema: `/home/gw/kitchmatics/roscamp-repo-1/database/schema.sql`
- TODO Items: `/home/gw/kitchmatics/roscamp-repo-1/TODO.md` (lines 46-51, 132-137)
