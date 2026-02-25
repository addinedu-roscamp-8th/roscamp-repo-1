# Kitchmatic Database Setup Guide

**Quick Start**: 5 minutes to get the database running
**Complete Setup**: 15 minutes with verification and testing
**Estimated Read Time**: 10 minutes

---

## Overview

This guide walks you through setting up the Kitchmatic PostgreSQL database with the optimized FMS schema. It includes:

1. PostgreSQL installation verification
2. Database and user creation
3. Schema initialization
4. FMS optimization layer
5. Verification and testing

---

## Prerequisites

- [ ] PostgreSQL 12+ installed (`sudo apt install postgresql postgresql-contrib`)
- [ ] sudo access on the machine
- [ ] `psql` command available
- [ ] Basic understanding of PostgreSQL

**Check Prerequisites:**

```bash
# Check PostgreSQL version
psql --version

# Check PostgreSQL service status
sudo systemctl status postgresql

# Start PostgreSQL if not running
sudo systemctl start postgresql
```

---

## Quick Start (Automated)

### Option 1: Fully Automated Setup

```bash
# Navigate to database directory
cd /home/gw/kitchmatics/roscamp-repo-1/database

# Run setup script with default settings
./setup_database.sh

# When prompted, enter: y
# Setup will complete automatically
```

**What this does:**
- Creates user `kitchmatic_user`
- Creates database `kitchmatic`
- Applies schema from `schema.sql`
- Applies optimizations from `migrations/001_add_fms_optimization.sql`
- Creates configuration file `database_config.env`
- Verifies installation

### Option 2: With Custom Password

```bash
./setup_database.sh --password "MySecurePassword123!"
```

### Option 3: For Remote Database Server

```bash
./setup_database.sh \
    --host 192.168.1.3 \
    --port 5432 \
    --password "MySecurePassword123!"
```

---

## Manual Setup (Step-by-Step)

### Step 1: Verify PostgreSQL

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start if needed
sudo systemctl start postgresql

# Check version
psql --version
```

### Step 2: Create Database User

```bash
# Connect as postgres superuser
sudo -u postgres psql

# Create user with password
CREATE USER kitchmatic_user WITH PASSWORD 'kitchmatic_secure_password_2025';

# Grant database creation rights (optional, for migrations)
ALTER USER kitchmatic_user CREATEDB;

# Exit
\q
```

### Step 3: Create Database

```bash
# As postgres user
sudo -u postgres psql

# Create database owned by kitchmatic_user
CREATE DATABASE kitchmatic OWNER kitchmatic_user;

# Exit
\q
```

### Step 4: Apply Base Schema

```bash
# Navigate to database directory
cd /home/gw/kitchmatics/roscamp-repo-1/database

# Apply schema
psql -U kitchmatic_user -d kitchmatic -f schema.sql

# Verify (should show "INSERT 0 3" for menus, ingredients, robots)
```

### Step 5: Apply FMS Optimization

```bash
# Apply optimization migration
psql -U kitchmatic_user -d kitchmatic -f migrations/001_add_fms_optimization.sql

# Should see: "✓ Migration completed successfully!"
```

### Step 6: Verify Installation

```bash
# Connect to database
psql -U kitchmatic_user -d kitchmatic

# Inside psql:

-- Check tables
\dt

-- Count rows in each table
SELECT 'menus' as table_name, COUNT(*) as row_count FROM menus
UNION ALL
SELECT 'robots', COUNT(*) FROM robots
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'fms_navigation_states', COUNT(*) FROM fms_navigation_states
UNION ALL
SELECT 'fms_event_log', COUNT(*) FROM fms_event_log;

-- Exit
\q
```

---

## Configuration

### Environment Variables

After setup, configure your application with these variables:

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=kitchmatic
export DB_USER=kitchmatic_user
export DB_PASSWORD=kitchmatic_secure_password_2025
```

Or source the config file created by setup script:

```bash
source database_config.env
```

### For Remote Database Server

If your database is on a different machine:

**1. Update PostgreSQL Config** (on database server)

Edit `/etc/postgresql/*/main/postgresql.conf`:

```conf
listen_addresses = '*'
```

Edit `/etc/postgresql/*/main/pg_hba.conf`:

```conf
# Allow connections from FMS server network
host    kitchmatic    kitchmatic_user    192.168.1.0/24    md5
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

**2. Test Connection from FMS Server**

```bash
psql -h 192.168.1.3 -U kitchmatic_user -d kitchmatic -c "SELECT version();"
```

---

## Testing

### Load Test Data

```bash
# Apply test data
psql -U kitchmatic_user -d kitchmatic -f test_data.sql

# This creates:
# - 4 sample orders (TEST_T01 - TEST_T04)
# - Robot assignments
# - Navigation states
# - Event log entries
# - And displays comprehensive summary
```

### Verify FMS Views

```bash
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM v_available_robots;"
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM v_active_orders_by_robot;"
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM v_order_timeline;"
```

### Run Performance Check

```sql
-- Test query performance
EXPLAIN ANALYZE
SELECT
    o.id, o.table_number, o.status, r.name, r.domain_id
FROM orders o
LEFT JOIN robots r ON o.assigned_serving_bot_id = r.id
WHERE o.status IN ('DELIVERING', 'DELIVERED')
LIMIT 10;
```

---

## FMS Database Integration

### For FMS Node (Python)

```python
import psycopg2
from psycopg2 import sql
import os

# Load from environment
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'database': os.getenv('DB_NAME', 'kitchmatic'),
    'user': os.getenv('DB_USER', 'kitchmatic_user'),
    'password': os.getenv('DB_PASSWORD', '')
}

# Connect
conn = psycopg2.connect(**db_config)
cursor = conn.cursor()

# Example: Get available robot
cursor.execute("""
    SELECT id, name, domain_id FROM robots
    WHERE type = 'SERVING_BOT_1' AND status = 'IDLE'
    LIMIT 1
""")

robot = cursor.fetchone()
conn.close()
```

### For Main Server Node

```python
from app.database_manager import DatabaseManager

db = DatabaseManager(
    db_host=os.getenv('DB_HOST'),
    db_port=int(os.getenv('DB_PORT')),
    db_name=os.getenv('DB_NAME'),
    db_user=os.getenv('DB_USER'),
    db_password=os.getenv('DB_PASSWORD')
)

# Connect and run queries
if db.connect():
    # Use db.query() or db.execute()
    pass
```

---

## Common Issues & Troubleshooting

### Issue 1: "role 'kitchmatic_user' does not exist"

**Solution:**

```bash
# Create the user
sudo -u postgres psql -c "CREATE USER kitchmatic_user WITH PASSWORD 'password';"
```

### Issue 2: "database 'kitchmatic' does not exist"

**Solution:**

```bash
# Create the database
sudo -u postgres psql -c "CREATE DATABASE kitchmatic OWNER kitchmatic_user;"
```

### Issue 3: Connection refused on remote host

**Solution:**

1. Verify PostgreSQL is listening on all interfaces:
   ```bash
   sudo netstat -pltn | grep postgres
   # Should show: 0.0.0.0:5432
   ```

2. Check firewall allows port 5432:
   ```bash
   sudo ufw allow 5432/tcp
   ```

3. Test connection:
   ```bash
   telnet <server-ip> 5432
   ```

### Issue 4: "permission denied for schema public"

**Solution:**

```bash
sudo -u postgres psql -d kitchmatic -c "GRANT ALL ON SCHEMA public TO kitchmatic_user;"
```

### Issue 5: Migration fails with "already exists"

**Solution:** The migration includes `IF NOT EXISTS` clauses, so it's safe to re-run:

```bash
psql -U kitchmatic_user -d kitchmatic -f migrations/001_add_fms_optimization.sql
```

---

## Backup and Recovery

### Create Backup

```bash
# Full database backup
pg_dump -U kitchmatic_user -d kitchmatic > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup (smaller file)
pg_dump -U kitchmatic_user -d kitchmatic | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Specific table only
pg_dump -U kitchmatic_user -d kitchmatic -t orders > orders_backup.sql
```

### Restore from Backup

```bash
# From SQL file
psql -U kitchmatic_user -d kitchmatic < backup_20260225.sql

# From compressed file
gunzip -c backup_20260225.sql.gz | psql -U kitchmatic_user -d kitchmatic

# Restore specific table
psql -U kitchmatic_user -d kitchmatic < orders_backup.sql
```

### Automated Backups (Linux)

```bash
# Add to crontab (daily backup at 2 AM)
# crontab -e

0 2 * * * pg_dump -U kitchmatic_user -d kitchmatic | gzip > /backups/kitchmatic_$(date +\%Y\%m\%d).sql.gz
```

---

## Monitoring and Maintenance

### Check Database Size

```bash
# Database size
psql -U kitchmatic_user -d kitchmatic -c "SELECT pg_size_pretty(pg_database_size('kitchmatic'));"

# Table sizes
psql -U kitchmatic_user -d kitchmatic << 'EOF'
SELECT
    schemaname,
    tablename,
    ROUND(pg_total_relation_size(schemaname||'.'||tablename) / 1024 / 1024::NUMERIC, 2) as size_mb
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF
```

### Vacuum and Analyze

```bash
# Optimize database
psql -U kitchmatic_user -d kitchmatic -c "VACUUM ANALYZE;"

# Check table bloat
psql -U kitchmatic_user -d kitchmatic -c "SELECT schemaname, tablename, ROUND(100*live_tuples/(live_tuples+dead_tuples), 2) as live_ratio FROM pg_stat_user_tables;"
```

### Index Maintenance

```bash
# Rebuild all indexes
psql -U kitchmatic_user -d kitchmatic -c "REINDEX DATABASE kitchmatic;"

# Find unused indexes
psql -U kitchmatic_user -d kitchmatic << 'EOF'
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(indexrelname) DESC;
EOF
```

---

## Next Steps

1. **Test FMS Integration**
   ```bash
   # Run test_data.sql to create sample orders
   psql -U kitchmatic_user -d kitchmatic -f test_data.sql
   ```

2. **Configure FMS to Use Database**
   - Update `/home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/main_server_node.py`
   - Set DB connection parameters

3. **Create Monitoring Queries**
   - Use queries from `FMS_QUERIES.md`
   - Set up dashboard for robot status

4. **Set Up Backups**
   - Configure automated daily backups
   - Test recovery procedure

5. **Performance Tuning** (Optional)
   - Adjust `shared_buffers`, `work_mem` in PostgreSQL
   - Monitor query performance
   - Create additional indexes if needed

---

## Support and References

| Document | Purpose |
|----------|---------|
| DATABASE_ARCHITECTURE.md | Detailed schema design, optimization strategies |
| FMS_QUERIES.md | Common SQL queries for FMS operations |
| schema.sql | Base database schema |
| migrations/001_add_fms_optimization.sql | FMS-specific tables and indexes |
| test_data.sql | Sample data for testing |

---

## Security Checklist

- [ ] Change default password to strong one (`MySecurePass2025!`)
- [ ] Restrict database access via firewall (only from FMS server)
- [ ] Enable SSL connections for remote access
- [ ] Regular backups (daily recommended)
- [ ] Restrict PostgreSQL user permissions (already minimal)
- [ ] Monitor database logs for suspicious activity
- [ ] Review user permissions regularly

---

## Verification Checklist

After setup, verify these items:

```bash
# 1. Database exists and is accessible
psql -U kitchmatic_user -d kitchmatic -c "SELECT 1;"

# 2. All required tables exist
psql -U kitchmatic_user -d kitchmatic -c "\dt"

# 3. FMS tables exist
psql -U kitchmatic_user -d kitchmatic -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('fms_navigation_states', 'fms_event_log');"

# 4. Views are created
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM information_schema.views WHERE table_schema = 'public';"

# 5. Test query works
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM v_available_robots;"

# 6. Connection pooling settings (optional)
# Verify in FMS config: pool_size, max_overflow, pool_timeout
```

---

## Performance Tips

### 1. Connection Pooling

Always use connection pooling in application code. Example for 10 concurrent FMS nodes:

```yaml
# config.yaml
database:
  pool_size: 20      # Keep-alive connections
  max_overflow: 10   # Additional on demand
  pool_timeout: 30   # seconds to wait
  pool_recycle: 3600 # Recycle every hour
```

### 2. Query Optimization

Use provided indexes in `FMS_QUERIES.md`. Most queries should run in < 5ms.

### 3. Regular Maintenance

```bash
# Weekly
psql -U kitchmatic_user -d kitchmatic -c "ANALYZE;"

# Monthly
psql -U kitchmatic_user -d kitchmatic -c "VACUUM ANALYZE; REINDEX DATABASE kitchmatic;"
```

---

**Last Updated**: 2026-02-25
**Database Version**: 1.1 with FMS Optimization
**Status**: Production Ready
