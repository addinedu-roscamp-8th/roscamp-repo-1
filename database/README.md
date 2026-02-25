# Kitchmatic Database

**Latest Version**: 1.1 with FMS Optimization
**Last Updated**: 2026-02-25
**Status**: Production Ready with FMS Support

---

## Quick Start

```bash
# Automated setup (recommended)
cd database
./setup_database.sh

# Or manual setup
source SETUP_GUIDE.md
```

---

## Documentation Index

### Essential Reading
- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Complete setup instructions (15 min)
  - Quick automated setup
  - Manual step-by-step instructions
  - Troubleshooting guide
  - Backup and recovery procedures

### For Database Architects
- **[DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md)** - Detailed schema design (20 min)
  - Current schema analysis
  - Order state transition diagram
  - FMS optimization layer
  - Performance considerations
  - Index strategy

### For Developers
- **[FMS_QUERIES.md](FMS_QUERIES.md)** - SQL query reference (15 min)
  - Robot status queries
  - Order management queries
  - Navigation state tracking
  - Event logging and auditing
  - Analytics queries

### SQL Files
- **[schema.sql](schema.sql)** - Base database schema (production schema)
- **[migrations/001_add_fms_optimization.sql](migrations/001_add_fms_optimization.sql)** - FMS tables and indexes
- **[test_data.sql](test_data.sql)** - Sample test data for development

---

## Features

### v1.0 - Kitchen Management
- ✅ Menu and ingredient management
- ✅ Recipe and cooking steps
- ✅ Inventory tracking with transactions
- ✅ Robot and arm catalog
- ✅ Order lifecycle management
- ✅ Quality inspection results

### v1.1 - FMS Integration (NEW)
- ✅ Robot domain ID mapping (ROS_DOMAIN_ID)
- ✅ FMS navigation state tracking
- ✅ Event audit logging
- ✅ Performance optimized indexes
- ✅ Helper views for FMS queries
- ✅ Order state machine for delivery flow

---

## Database Configuration

### Default Credentials
- **Host**: localhost
- **Port**: 5432
- **Database**: kitchmatic
- **User**: kitchmatic_user
- **Password**: (set during setup)

### Environment Variables
```bash
# After setup, configure application with:
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=kitchmatic
export DB_USER=kitchmatic_user
export DB_PASSWORD=your_secure_password
```

Or source config file:
```bash
source database_config.env
```

---

## Directory Structure

```
database/
├── README.md                           # This file
├── SETUP_GUIDE.md                      # Setup instructions
├── DATABASE_ARCHITECTURE.md            # Schema design and optimization
├── FMS_QUERIES.md                      # SQL query reference
├── schema.sql                          # Base database schema
├── test_data.sql                       # Test data
├── setup_database.sh                   # Automated setup script
├── migrations/
│   ├── 001_add_fms_optimization.sql    # FMS tables and indexes
│   └── ...                             # Future migrations
└── db_server/                          # Optional REST API server
    ├── README.md
    ├── app/
    ├── docs/
    └── tests/
```

---

## Order State Flow

```
PENDING → ORDERED → AT_POINT13 → PRECISION_PARKING → LOADING → LOADED → DELIVERING → DELIVERED → COMPLETED → RETURNED

Or (error paths):
ORDERED → CANCELLED
LOADING → FAILED
DELIVERING → ABORTED
```

See [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md) for state responsibility matrix.

---

## Verification

After setup, verify installation:

```bash
# Connect to database
psql -U kitchmatic_user -d kitchmatic

# Inside psql, check:
\dt              -- List all tables
SELECT * FROM robots;      -- View robots
SELECT * FROM v_available_robots;  -- View FMS robot status
```

Full verification checklist in [SETUP_GUIDE.md](SETUP_GUIDE.md#verification-checklist).

---

## Common Tasks

### Load Test Data
```bash
psql -U kitchmatic_user -d kitchmatic -f test_data.sql
```

### Backup Database
```bash
pg_dump -U kitchmatic_user -d kitchmatic > backup_$(date +%Y%m%d).sql
```

### Restore from Backup
```bash
psql -U kitchmatic_user -d kitchmatic < backup_20260225.sql
```

### Apply Migrations
```bash
psql -U kitchmatic_user -d kitchmatic -f migrations/001_add_fms_optimization.sql
```

---

## Key Tables for FMS

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| **orders** | Customer orders | order_id, table_number, status, assigned_robot |
| **robots** | Mobile robots & arms | robot_id, domain_id, type, status, battery_voltage |
| **fms_navigation_states** | Robot position tracking | order_id, current_x/y, target_x/y, navigation_status |
| **fms_event_log** | Event audit trail | event_type, order_id, robot_id, details, error_message |
| **inventory_transactions** | Stock changes | ingredient_id, qty_delta, order_id, robot_id |
| **quality_check_results** | Food inspection | order_id, status, confidence_score |

---

## FMS Integration Points

### 1. Robot Management
- Query available robots by domain_id
- Update robot battery voltage
- Track robot status (IDLE, BUSY, ERROR)

### 2. Order Management
- Create orders from GUI
- Update order status through delivery flow
- Assign robots to orders

### 3. Navigation Tracking
- Log navigation start (current position, target)
- Update when goal reached
- Track navigation failures

### 4. Event Logging
- Log all state transitions
- Log errors with details
- Generate audit trail for debugging

---

## Performance

### Query Performance Targets
- Robot queries: < 1ms
- Order assignment: < 5ms
- Navigation updates: < 2ms
- Event logging: < 2ms
- Fleet analytics: < 50ms

### Optimization Strategies
- Composite indexes for common queries
- Partial indexes for filtered lookups
- Connection pooling in application
- Regular VACUUM ANALYZE

See [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md#performance-considerations) for details.

---

## Security

- [ ] Use strong password (minimum 12 chars, mixed case, numbers, symbols)
- [ ] Restrict database access via firewall
- [ ] Enable SSL for remote connections
- [ ] Regular backups (daily recommended)
- [ ] Review user permissions regularly
- [ ] Monitor database logs

---

## Support

### Issues?
1. Check [SETUP_GUIDE.md - Troubleshooting](SETUP_GUIDE.md#common-issues--troubleshooting)
2. Review [DATABASE_ARCHITECTURE.md](DATABASE_ARCHITECTURE.md) for schema details
3. Check [FMS_QUERIES.md](FMS_QUERIES.md) for query examples

### Need Help?
- Database queries: See FMS_QUERIES.md
- Schema questions: See DATABASE_ARCHITECTURE.md
- Setup issues: See SETUP_GUIDE.md

---

## Related Files

- FMS Config: `/home/gw/kitchmatics/roscamp-repo-1/fms/config/fms_config.yaml`
- Main Server: `/home/gw/kitchmatics/roscamp-repo-1/app/backend/main_server/main_server_node.py`
- TODOs: `/home/gw/kitchmatics/roscamp-repo-1/TODO.md` (lines 46-51, 132-137)
- Project Guide: `/home/gw/kitchmatics/roscamp-repo-1/CLAUDE.md`

---

**Status**: ✅ Production Ready | **Version**: 1.1 | **Last Updated**: 2026-02-25
