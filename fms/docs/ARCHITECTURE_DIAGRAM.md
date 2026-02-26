# FMS GUI Order Integration - Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Customer GUI (Port 9000)                        │
│                         (Customer Kiosk / Tablet)                        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ TCP (4-byte header + JSON)
                                   │
                    ┌──────────────▼─────────────┐
                    │   new_order (command)      │
                    │   delivery_complete        │
                    └──────────────┬─────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│                          FMS Node (Master PC)                            │
│                        ROS_DOMAIN_ID = 25/11                             │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Presentation Layer (fms_node.py)                    │   │
│  │  - Initialize components                                         │   │
│  │  - Register callbacks                                            │   │
│  │  - Coordinate ROS2 communication                                 │   │
│  └────────────┬────────────────────────────────────┬────────────────┘   │
│               │                                     │                     │
│  ┌────────────▼──────────────────┐   ┌────────────▼──────────────┐     │
│  │   Application Layer            │   │  Infrastructure Layer      │     │
│  │  (order_handler.py)            │   │  (gui_tcp_server.py)       │     │
│  │                                │   │                            │     │
│  │  - OrderWorkflow (Domain)      │   │  - TCP Server (Port 9000)  │     │
│  │  - handle_new_order()          │   │  - Message routing         │     │
│  │  - handle_cooking_complete()   │   │  - Push notifications      │     │
│  │  - handle_robot_arrived_*()    │   │  - Client management       │     │
│  │  - handle_delivery_confirm()   │   │                            │     │
│  │                                │   │                            │     │
│  │  Dependencies (Callbacks):     │   │  Handlers:                 │     │
│  │  - send_cooking_command        │   │  - new_order               │     │
│  │  - navigate_robot              │   │  - delivery_complete       │     │
│  │  - send_gui_notification       │   │                            │     │
│  │  - fleet_controller            │   │                            │     │
│  └────────────┬───────────────────┘   └────────────┬───────────────┘     │
│               │                                     │                     │
│               └─────────────────┬───────────────────┘                     │
│                                 │                                         │
└─────────────────────────────────┼─────────────────────────────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
        ┌─────────▼─────────┐  ┌─▼──────────┐  ┌▼────────────────┐
        │   Robot Arm       │  │   pinky1   │  │  Fleet Status   │
        │ (ROS2 Topic)      │  │ Navigation │  │  Publishing     │
        │                   │  │ (Action)   │  │  (ROS2 Topic)   │
        │ /cooking/order    │  │            │  │                 │
        │   ↓               │  │ /navigate_ │  │ /fms/fleet_     │
        │ CookingOrder      │  │ to_pose    │  │ status          │
        │   - order_id      │  │            │  │                 │
        │   - menu_id       │  │ Goals:     │  │                 │
        │   - quantity      │  │ - point13  │  └─────────────────┘
        │   - sauce_type    │  │ - table1   │
        │   - robot_id      │  │ - pinky1_  │
        │                   │  │   spot     │
        │ /cooking/loading_ │  │            │
        │ complete          │  │            │
        │   ↑               │  │            │
        │ LoadingComplete   │  │            │
        └───────────────────┘  └────────────┘
```

## Data Flow: Order Processing

```
1. Order Reception
   ════════════════
   Customer GUI
      │
      │ TCP: new_order
      │ {"command": "new_order", "table_number": 1, "order": {...}}
      ▼
   GUITCPServer._process_message()
      │
      │ Route to handler
      ▼
   FMSNode._handle_gui_new_order()
      │
      │ Delegate to application layer
      ▼
   OrderHandler.handle_new_order()
      │
      ├─→ Create OrderWorkflow (RECEIVED state)
      │
      ├─→ Transition to COOKING
      │   └─→ Callback: send_cooking_command
      │       └─→ Publish /cooking/order
      │
      └─→ Transition to LOADING
          └─→ Callback: navigate_robot('pinky1', 'point13')
              └─→ Navigate pinky1 to point13


2. Cooking & Navigation (Parallel)
   ════════════════════════════════
   Robot Arm                         pinky1
      │                                │
      │ Cooking...                     │ Navigating to point13...
      │                                │
      ▼                                ▼
   Cooking Complete                 Arrived at point13
      │                                │
      │ Publish /cooking/             │ Pose update
      │ loading_complete              │
      │                                │
      ▼                                ▼
   FMSNode.loading_complete_callback()
      │
      │ Notify order handler
      ▼
   OrderHandler.handle_cooking_complete()
      │
      ├─→ Check robot at point13
      │
      ├─→ Transition to LOADED
      │
      └─→ Skip precision control (3s delay)
          └─→ Callback: navigate_robot('pinky1', 'table1')


3. Table Delivery
   ═══════════════
   pinky1
      │
      │ Navigating to table1...
      │
      ▼
   Arrived at table1
      │
      │ Pose update triggers navigation check
      ▼
   FMSNode._check_navigation_status_with_order_handler()
      │
      │ Detect table arrival
      ▼
   OrderHandler.handle_robot_arrived_table()
      │
      ├─→ Transition to ARRIVED
      │
      └─→ Callback: send_gui_notification
          │
          │ Push notification
          ▼
   GUITCPServer.broadcast()
      │
      │ TCP: delivery_notification
      │ {"type": "delivery_notification", "data": {...}}
      ▼
   Customer GUI (receives push notification)


4. Delivery Confirmation
   ═══════════════════════
   Customer GUI
      │
      │ Customer confirms receipt
      │
      │ TCP: delivery_complete
      │ {"command": "delivery_complete", "order_id": "...", "table_number": 1}
      ▼
   GUITCPServer._process_message()
      │
      │ Route to handler
      ▼
   FMSNode._handle_gui_delivery_complete()
      │
      │ Delegate to application layer
      ▼
   OrderHandler.handle_delivery_confirmation()
      │
      ├─→ Transition to COMPLETED
      │
      ├─→ Callback: fleet_controller('pinky1', 'complete_delivery')
      │   └─→ Update robot status to RETURNING
      │
      └─→ Callback: navigate_robot('pinky1', 'pinky1_spot')
          │
          │ Navigate to home
          ▼
   pinky1 returns to parking spot
      │
      │ Pose update triggers navigation check
      ▼
   Robot status → IDLE (ready for next order)
```

## State Machine: OrderWorkflow

```
┌─────────────┐
│  RECEIVED   │  ← Initial state (GUI order received)
└──────┬──────┘
       │ send_cooking_command()
       │ navigate_robot('point13')
       ▼
┌─────────────┐
│   COOKING   │  ← Robot arm cooking, pinky1 moving to point13
└──────┬──────┘
       │ robot arrives at point13
       ▼
┌─────────────┐
│   LOADING   │  ← Waiting for cooking completion
└──────┬──────┘
       │ cooking_complete()
       ▼
┌─────────────┐
│   LOADED    │  ← Food ready, skip precision control
└──────┬──────┘
       │ navigate_robot('table1')
       │ (after 3s delay)
       ▼
┌─────────────┐
│ DELIVERING  │  ← Robot moving to table
└──────┬──────┘
       │ robot arrives at table
       │ send_gui_notification()
       ▼
┌─────────────┐
│   ARRIVED   │  ← Waiting for customer confirmation
└──────┬──────┘
       │ delivery_complete from GUI
       │ navigate_robot('pinky1_spot')
       ▼
┌─────────────┐
│  COMPLETED  │  ← Order fulfilled, robot returning home
└─────────────┘
       │
       ▼
   Robot IDLE (ready for next order)


Error Flow:
┌─────────────┐
│    FAILED   │  ← Any error during workflow
└─────────────┘
```

## Component Interaction: SOLID Principles

```
┌────────────────────────────────────────────────────────────────┐
│                    Dependency Inversion                         │
│                                                                  │
│  Application Layer (OrderHandler)                               │
│  depends on ABSTRACTIONS (callbacks), not concrete classes      │
│                                                                  │
│  register_callbacks(                                            │
│      send_cooking_command: Callable,    ← Abstract dependency   │
│      navigate_robot: Callable,          ← Abstract dependency   │
│      send_gui_notification: Callable,   ← Abstract dependency   │
│      fleet_controller: Callable         ← Abstract dependency   │
│  )                                                               │
│                                                                  │
│  Implementation is provided by FMSNode (Infrastructure Layer)   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    Single Responsibility                         │
│                                                                  │
│  OrderHandler:        Order workflow orchestration              │
│  GUITCPServer:        TCP communication                         │
│  FMSNode:             ROS2 integration & coordination           │
│  FleetController:     Robot fleet management                    │
│  OrderWorkflow:       Domain entity (state machine)             │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    Open/Closed Principle                         │
│                                                                  │
│  New message types can be added without modifying existing code │
│                                                                  │
│  gui_tcp_server.register_handler('new_message_type', handler)   │
│                                                                  │
│  New workflow states can be added by extending OrderWorkflow    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

## Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                    kitchmatics WiFi Network                      │
│                         192.168.1.x                              │
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                      │
│  │ Master PC    │         │ Customer GUI │                      │
│  │ 192.168.1.3  │◄────────┤ (Tablet)     │                      │
│  │              │  TCP    │              │                      │
│  │ FMS Node     │  :9000  └──────────────┘                      │
│  │              │                                                │
│  │ DOMAIN_ID:25 │         ┌──────────────┐                      │
│  │   (FMS)      │◄────────┤ Robot Arm    │                      │
│  │              │  ROS2   │ 192.168.1.4  │                      │
│  │ DOMAIN_ID:11 │  Topic  │              │                      │
│  │   (pinky1)   │         │ DOMAIN_ID:20 │                      │
│  └──────┬───────┘         └──────────────┘                      │
│         │                                                         │
│         │ ROS2 Action                                            │
│         │ (cross-domain via bridge)                              │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ pinky1       │                                                │
│  │ 192.168.1.7  │                                                │
│  │              │                                                │
│  │ DOMAIN_ID:11 │                                                │
│  └──────────────┘                                                │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                         Technology Stack                         │
├─────────────────────────────────────────────────────────────────┤
│  Language:           Python 3.10+                                │
│  Framework:          ROS2 Humble                                 │
│  Communication:      TCP (Custom Protocol)                       │
│                      ROS2 Topics/Actions                         │
│  Serialization:      JSON (UTF-8)                                │
│  Concurrency:        Threading (Python)                          │
│  Navigation:         Nav2                                        │
│  Localization:       AMCL                                        │
│  Architecture:       Clean Architecture                          │
│  Principles:         SOLID                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Performance Characteristics

```
┌─────────────────────────────────────────────────────────────────┐
│                    Performance Metrics                           │
├─────────────────────────────────────────────────────────────────┤
│  TCP Server:         Multi-threaded (1 thread per client)       │
│  Message Processing: Asynchronous (non-blocking)                 │
│  Navigation:         Concurrent (multiple robots possible)       │
│  Order Processing:   ~30-60 seconds (cooking + delivery)         │
│  Latency:            < 100ms (order acceptance)                  │
│                      < 50ms (push notification)                  │
│  Throughput:         Limited by robot count (currently 1)        │
│  Scalability:        Horizontal (add more robots/FMS instances)  │
└─────────────────────────────────────────────────────────────────┘
```
