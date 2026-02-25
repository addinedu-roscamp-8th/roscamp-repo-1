# Main Server Architecture Diagram

## 1. Overall System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Master PC (192.168.1.3)                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     Main Server Process                      │  │
│  │                                                              │  │
│  │  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │  │
│  │  │  TCP Server    │  │   ROS Bridge   │  │  Database     │ │  │
│  │  │  (Port 9999)   │  │  (ROS 2 Node)  │  │  Manager      │ │  │
│  │  │                │  │                │  │  (SQLAlchemy) │ │  │
│  │  │  - Kiosk       │  │  - Publishers  │  │               │ │  │
│  │  │  - Admin GUI   │  │  - Subscribers │  │  - Orders     │ │  │
│  │  │  - JSON API    │  │  - Callbacks   │  │  - Robots     │ │  │
│  │  └────────┬───────┘  └────────┬───────┘  │  - Menu       │ │  │
│  │           │                   │          │  - Inventory  │ │  │
│  │           └───────────┬───────┘          └───────┬───────┘ │  │
│  │                       │                          │         │  │
│  │               ┌───────▼──────────────────────────▼──────┐  │  │
│  │               │   Main Server Coordinator             │  │  │
│  │               │   - Message routing                   │  │  │
│  │               │   - State management                  │  │  │
│  │               │   - Error handling                    │  │  │
│  │               └───────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   PostgreSQL Database                     │  │
│  │                   (Port 5432)                             │  │
│  │                   kitchmatic DB                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

         ▲                          ▲                     ▲
         │ TCP                      │ ROS 2               │ ROS 2
         │ (JSON)                   │ (DDS)               │ (DDS)
         │                          │                     │
         │                          │                     │
┌────────┴────────┐     ┌──────────┴──────────┐   ┌─────┴──────┐
│   Kiosk GUI     │     │    FMS Node         │   │ Robot Arm  │
│   Admin GUI     │     │  (Fleet Manager)    │   │  Nodes     │
└─────────────────┘     └─────────────────────┘   └────────────┘
```

## 2. Main Server Internal Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         MainServer Class                         │
│                                                                  │
│  Components:                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │ DatabaseManager│  │   TCPServer    │  │    ROSBridge     │  │
│  │                │  │                │  │                  │  │
│  │ - connect()    │  │ - start()      │  │ - Publishers:    │  │
│  │ - get_session()│  │ - stop()       │  │   • order_req    │  │
│  │ - create_order │  │ - register_    │  │   • cooking_ord  │  │
│  │ - update_order │  │   handler()    │  │   • delivery_cmp │  │
│  │ - get_order    │  │ - broadcast()  │  │   • precision_pk │  │
│  │ - update_robot │  │ - send_to_     │  │                  │  │
│  │ - get_menu     │  │   client()     │  │ - Subscribers:   │  │
│  │                │  │                │  │   • loading_cmp  │  │
│  └────────┬───────┘  └────────┬───────┘  │   • fleet_status │  │
│           │                   │          │   • pickup_arr   │  │
│           │                   │          │                  │  │
│           └───────────┬───────┘          └──────┬───────────┘  │
│                       │                         │              │
│               ┌───────▼─────────────────────────▼───────┐      │
│               │      Message Handler Methods          │      │
│               │                                        │      │
│               │  - handle_order_request()             │      │
│               │  - handle_order_status_query()        │      │
│               │  - handle_fleet_status_query()        │      │
│               │  - handle_delivery_complete()         │      │
│               │  - handle_loading_complete()          │      │
│               │  - handle_fleet_status_update()       │      │
│               │  - handle_pickup_arrival()            │      │
│               │                                        │      │
│               └────────────────────────────────────────┘      │
│                                                                │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Message Flow - Order Processing

```
┌─────────────┐                                          ┌──────────────┐
│   Kiosk     │                                          │     FMS      │
│    GUI      │                                          │    Node      │
└──────┬──────┘                                          └──────▲───────┘
       │                                                        │
       │ 1. TCP: order_request                                 │
       │    {table: T01, menu: M001}                          │
       │                                                        │
       ▼                                                        │
┌─────────────────────────────────────────────┐               │
│          Main Server                        │               │
│  ┌──────────────────────────────────────┐   │               │
│  │  TCP Handler:                        │   │               │
│  │    handle_order_request()            │   │               │
│  │                                      │   │               │
│  │  1. Validate menu ───────────┐      │   │               │
│  │  2. Create order in DB ───┐  │      │   │               │
│  │  3. Update status: CONFIRMED│ │      │   │               │
│  │  4. Publish to ROS ─────────┼─┼──────┼───┼───────────────┘
│  │  5. Broadcast TCP update    │ │      │   │   2. ROS: OrderRequest
│  └─────────────────────┬────────┘ │      │   │      /fms/order_request
│                        │          │      │   │
│                        ▼          ▼      │   │
│              ┌─────────────────────────┐ │   │
│              │  PostgreSQL Database    │ │   │
│              │  - INSERT INTO orders   │ │   │
│              │  - UPDATE orders SET... │ │   │
│              └─────────────────────────┘ │   │
└─────────────────────────────────────────┘   │
                                               │
       ┌───────────────────────────────────────┘
       │ 3. FMS processes order
       │    - Assigns robot
       │    - Navigates to pickup_spot
       │
       ▼
┌──────────────┐
│     FMS      │
│   (later)    │
└──────┬───────┘
       │
       │ 4. ROS: PickupArrival
       │    /fms/pickup_arrival
       │    {robot_id: pinky1, order_id: xxx}
       │
       ▼
┌─────────────────────────────────────────────┐
│          Main Server                        │
│  ┌──────────────────────────────────────┐   │
│  │  ROS Callback:                       │   │
│  │    handle_pickup_arrival()           │   │
│  │                                      │   │
│  │  1. Update order: AT_POINT13 ────┐   │   │
│  │  2. Send CookingOrder to arm ────┼───┼───┼──────────┐
│  │  3. Broadcast TCP update         │   │   │          │
│  │  4. (Skip mode) Auto precision   │   │   │          │
│  └─────────────────────┬──────────────┘   │   │          │
│                        ▼                  │   │          │
│              ┌─────────────────────────┐  │   │          │
│              │  PostgreSQL Database    │  │   │          │
│              │  - UPDATE orders        │  │   │          │
│              │    SET status=AT_POINT13│  │   │          │
│              └─────────────────────────┘  │   │          │
└─────────────────────────────────────────┘   │          │
                                              │          │
                                              │          ▼
                                              │   ┌─────────────┐
                                              │   │ Robot Arm   │
                                              │   │    Node     │
                                              └───┤ 5. Receives │
                                                  │ CookingOrder│
                                                  └──────┬──────┘
                                                         │
                                                         │ 6. Cooks food
                                                         │ 7. Loads onto robot
                                                         │
       ┌─────────────────────────────────────────────────┘
       │ 8. ROS: LoadingComplete
       │    /robot_arm/loading_complete
       │    {order_id: xxx, success: true}
       │
       ▼
┌─────────────────────────────────────────────┐
│          Main Server                        │
│  ┌──────────────────────────────────────┐   │
│  │  ROS Callback:                       │   │
│  │    handle_loading_complete()         │   │
│  │                                      │   │
│  │  1. Update order: READY ─────────┐   │   │
│  │  2. Broadcast TCP update         │   │   │
│  └─────────────────────┬──────────────┘   │   │
│                        ▼                  │   │
│              ┌─────────────────────────┐  │   │
│              │  PostgreSQL Database    │  │   │
│              │  - UPDATE orders        │  │   │
│              │    SET status=READY     │  │   │
│              └─────────────────────────┘  │   │
└─────────────────────────────────────────┘   │
                                              │
       (FMS navigates robot to table)         │
                                              │
       ┌──────────────────────────────────────┘
       │ 9. TCP: delivery_complete
       │    {order_id: xxx, table: T01}
       │
       ▼
┌─────────────────────────────────────────────┐
│          Main Server                        │
│  ┌──────────────────────────────────────┐   │
│  │  TCP Handler:                        │   │
│  │    handle_delivery_complete()        │   │
│  │                                      │   │
│  │  1. Update order: COMPLETED ─────┐   │   │
│  │  2. Publish DeliveryComplete     │   │   │
│  │  3. Broadcast TCP update         │   │   │
│  └─────────────────────┬──────────────┘   │   │
│                        ▼                  │   │
│              ┌─────────────────────────┐  │   │
│              │  PostgreSQL Database    │  │   │
│              │  - UPDATE orders        │  │   │
│              │    SET status=COMPLETED │  │   │
│              └─────────────────────────┘  │   │
└─────────────────────────────────────────┘   │
                                              │
                                              ▼
                                       Order Complete!
```

## 4. Skip Mode Message Flow

```
┌─────────────────────────────────────────────┐
│    Main Server (skip_mode=true)             │
│                                             │
│    ┌──────────────────────────────────┐    │
│    │  ROSBridge                       │    │
│    │    skip_mode = True              │    │
│    │    precision_parking_delay = 2s  │    │
│    │    food_loading_delay = 3s       │    │
│    └──────────────────────────────────┘    │
└─────────────────────────────────────────────┘
                     │
                     │ 1. Receives PickupArrival
                     ▼
              ┌──────────────────┐
              │ pickup_arrival   │
              │   callback()     │
              └────────┬─────────┘
                       │
                       ├─────► handle_pickup_arrival()
                       │       - Update DB: AT_POINT13
                       │       - Send CookingOrder
                       │
                       │ 2. Skip mode check
                       ▼
              ┌──────────────────┐
              │ if skip_mode:    │
              │   create_timer   │
              │   (2s delay)     │
              └────────┬─────────┘
                       │
                       │ 3. Wait 2 seconds
                       ▼
              ┌──────────────────────────┐
              │ _send_mock_precision_    │
              │ parked()                 │
              │                          │
              │ - Create PrecisionParked │
              │   message                │
              │ - Publish to FMS         │
              └────────┬─────────────────┘
                       │
                       │ 4. Skip mode check again
                       ▼
              ┌──────────────────┐
              │ if skip_mode:    │
              │   create_timer   │
              │   (3s delay)     │
              └────────┬─────────┘
                       │
                       │ 5. Wait 3 seconds
                       ▼
              ┌──────────────────────────┐
              │ _send_mock_loading_      │
              │ complete()               │
              │                          │
              │ - Call on_loading_       │
              │   complete callback      │
              │ - Update DB: READY       │
              └──────────────────────────┘
                       │
                       ▼
              Order ready for delivery
              (FMS navigates to table)
```

## 5. TCP Protocol

### Request Format
```json
{
  "type": "message_type",
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

### Response Format
```json
{
  "status": "success" | "error",
  "data": { ... } | "message": "error message"
}
```

### Supported Message Types

#### 1. order_request
```
Request:  {type: "order_request", data: {table_number, menu_id, quantity, sauce_type, voice_order}}
Response: {status: "success", data: {order_id, estimated_time}}
```

#### 2. order_status_query
```
Request:  {type: "order_status_query", data: {order_id}}
Response: {status: "success", data: {order_id, status, table_number, menu_id, created_at, updated_at}}
```

#### 3. fleet_status_query
```
Request:  {type: "fleet_status_query", data: {}}
Response: {status: "success", data: {robots: [...], pending_orders, active_orders}}
```

#### 4. delivery_complete
```
Request:  {type: "delivery_complete", data: {order_id, table_number}}
Response: {status: "success", data: {message: "Order completed"}}
```

### Broadcast Messages (Server → All Clients)

#### order_status_update
```json
{
  "type": "order_status_update",
  "data": {
    "order_id": "uuid",
    "status": "COOKING",
    "table_number": "T01",
    "timestamp": "2026-02-25T10:30:00Z"
  }
}
```

#### fleet_status_update
```json
{
  "type": "fleet_status_update",
  "data": {
    "robots": [...],
    "pending_orders": 2,
    "active_orders": 1,
    "timestamp": "2026-02-25T10:30:00Z"
  }
}
```

## 6. Database Schema (Key Tables)

```
┌─────────────────────────────────────────────┐
│                  orders                     │
├─────────────────────────────────────────────┤
│ id                 UUID (PK)                │
│ table_number       VARCHAR(10)              │
│ menu_id            VARCHAR(10) (FK)         │
│ quantity           INTEGER                  │
│ status             VARCHAR(20)              │
│   - PENDING                                 │
│   - CONFIRMED                               │
│   - AT_POINT13      ← (CRITICAL: Add this) │
│   - COOKING                                 │
│   - READY                                   │
│   - DELIVERING                              │
│   - COMPLETED                               │
│ created_at         TIMESTAMP                │
│ updated_at         TIMESTAMP                │
│ voice_order        BOOLEAN                  │
│ assigned_robot_arm_id      UUID (FK)        │
│ assigned_serving_bot_id    UUID (FK)        │
└─────────────────────────────────────────────┘
                     │
                     │ Foreign Keys
                     │
         ┌───────────┴────────────┐
         ▼                        ▼
┌──────────────────┐     ┌──────────────────┐
│      menus       │     │      robots      │
├──────────────────┤     ├──────────────────┤
│ id     PK        │     │ id        PK     │
│ name             │     │ name             │
│ price            │     │ type             │
│ category         │     │ status           │
│ available        │     │   - IDLE         │
│ created_at       │     │   - NAVIGATING   │
└──────────────────┘     │   - LOADING      │
                         │   - DELIVERING   │
                         │   - ERROR        │
                         │ ip_address       │
                         │ port             │
                         │ last_heartbeat   │
                         └──────────────────┘
```

## 7. Thread Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Server Process                      │
│                                                             │
│  ┌────────────────┐                                         │
│  │  Main Thread   │                                         │
│  │                │                                         │
│  │  - Initialize  │                                         │
│  │  - Signal      │                                         │
│  │    handling    │                                         │
│  │  - Wait loop   │                                         │
│  └────────────────┘                                         │
│                                                             │
│  ┌────────────────┐   ┌────────────────────────────────┐   │
│  │  TCP Thread    │   │     ROS Thread                 │   │
│  │                │   │                                │   │
│  │  - Accept      │   │  - rclpy.spin()                │   │
│  │    clients     │   │  - Callback execution          │   │
│  │  ├─ Client 1   │   │  - Publisher/Subscriber        │   │
│  │  ├─ Client 2   │   │  - Timer callbacks             │   │
│  │  └─ Client N   │   │    (skip mode)                 │   │
│  │                │   │                                │   │
│  │  Each client:  │   └────────────────────────────────┘   │
│  │  ┌──────────┐  │                                        │
│  │  │ Handler  │  │   ┌────────────────────────────────┐   │
│  │  │  Thread  │  │   │   Database Sessions           │   │
│  │  └──────────┘  │   │                                │   │
│  │                │   │  - Session per request         │   │
│  └────────────────┘   │  - Auto-commit/rollback        │   │
│                       │  - Connection pooling          │   │
│                       └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 8. Error Handling Flow

```
┌─────────────────────────────────────────────┐
│           Error Sources                     │
├─────────────────────────────────────────────┤
│  1. TCP Connection Error                   │
│  2. JSON Parse Error                       │
│  3. Database Connection Error              │
│  4. Database Constraint Violation          │
│  5. ROS Communication Error                │
│  6. Invalid Message Type                   │
│  7. Missing Required Fields                │
│  8. Business Logic Error                   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
      ┌────────────────────────┐
      │   Error Handler        │
      │                        │
      │  try:                  │
      │    operation()         │
      │  except Exception as e:│
      │    logger.error(...)   │
      │    return error_resp   │
      │  finally:              │
      │    cleanup()           │
      └────────┬───────────────┘
               │
               ├─────► Log to file/console
               │       [timestamp] [ERROR] [module] message
               │
               ├─────► Return error response
               │       {status: "error", message: "..."}
               │
               └─────► Cleanup resources
                       - Close DB session
                       - Close sockets
                       - Release locks
```

## 9. Configuration Management

```
┌─────────────────────────────────────────────────────────┐
│            Configuration Sources                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. Environment Variables                              │
│     ┌────────────────────────────┐                     │
│     │ SKIP_MODE=true             │                     │
│     │ DB_HOST=localhost          │                     │
│     │ DB_PASSWORD=secret         │                     │
│     │ LOG_LEVEL=INFO             │                     │
│     └────────────────────────────┘                     │
│                                                         │
│  2. Config Files                                       │
│     ┌────────────────────────────┐                     │
│     │ config/database.env        │                     │
│     │   DB_HOST=...              │                     │
│     │   DB_PORT=5432             │                     │
│     │   DB_NAME=kitchmatic       │                     │
│     └────────────────────────────┘                     │
│                                                         │
│  3. ROS 2 Parameters                                   │
│     ┌────────────────────────────┐                     │
│     │ ros2 run main_server       │                     │
│     │   --ros-args               │                     │
│     │   -p skip_mode:=true       │                     │
│     └────────────────────────────┘                     │
│                                                         │
│  4. Default Values (Hardcoded)                         │
│     ┌────────────────────────────┐                     │
│     │ tcp_port = 9999            │                     │
│     │ precision_delay = 2.0      │                     │
│     │ loading_delay = 3.0        │                     │
│     └────────────────────────────┘                     │
│                                                         │
│  Priority: 1 > 2 > 3 > 4                               │
└─────────────────────────────────────────────────────────┘
```

## 10. Deployment View

```
┌─────────────────────────────────────────────────────────────┐
│               Production Environment                        │
│              Master PC (192.168.1.3)                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Systemd Service: main_server.service                │  │
│  │                                                       │  │
│  │  ExecStart=/usr/bin/ros2 run main_server main_server │  │
│  │  Restart=always                                       │  │
│  │  Environment="ROS_DOMAIN_ID=0"                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Service (Port 5432)                      │  │
│  │  - Database: kitchmatic                               │  │
│  │  - User: kitchmatic_user                              │  │
│  │  - Backup: Daily at 02:00                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Log Files                                            │  │
│  │  - /var/log/main_server/server.log                    │  │
│  │  - /var/log/main_server/error.log                     │  │
│  │  - Rotation: Daily, keep 30 days                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

**Reference**: See BACKEND_VALIDATION_REPORT.md for detailed analysis
