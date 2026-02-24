# Kitchmatics FMS Agent Team - Startup Prompt

Copy and paste this prompt to start the agent team:

---

Create an agent team for the Kitchmatics FMS project with 10 teammates working in parallel. Use tmux split-pane mode.

## Project Context

We're implementing a delivery flow from Customer GUI order to table delivery using autonomous mobile robots (PinkyPro) in a restaurant environment.

**Our FMS scope:**
- Navigate pinky robots to point13 (kitchen pickup point)
- Send goal_arrived message after point13 arrival
- Navigate to customer table after food loading
- Return robot to parking spot after delivery

**External teams (NOT our responsibility):**
- Precision parking (point13→pickup_spot) - handled by precision control team
- Robot arm food loading - handled by robot arm team

**Test strategy:**
Use skip mode to mock external team steps (precision_parked and food_loaded messages) for testing without dependencies.

**CRITICAL architecture requirement:**
Use ROS_DOMAIN_ID (11, 12, 13, 14, 15) on closed network WiFi, NOT namespaces. Each robot operates on separate domain ID.

**Delivery Flow:**
1. GUI order → FMS
2. FMS navigates pinky to point13 ✅ (our scope)
3. Point13 arrival → send goal_arrived message ✅ (our scope)
4. Precision parking point13→pickup_spot ⏭️ (external team, skip in test)
5. Receive precision_parked message ⏭️ (mock in test)
6. FMS requests robot arm to load food
7. Robot arm loads food ⏭️ (external team, skip in test)
8. Receive food_loaded message ⏭️ (mock in test)
9. FMS navigates pinky to table ✅ (our scope)
10. Customer clicks delivery complete
11. FMS returns pinky to parking spot ✅ (our scope)

**ROS_DOMAIN_ID Assignments:**
- pinky1: 11
- pinky2: 12
- pinky3: 13
- robot_arm_1: 14
- robot_arm_2: 15

## Team Instructions

**IMPORTANT: Start Product Planner first.** Product Planner must read Jira issues and Confluence documentation, then brief all teammates before anyone starts implementation.

Spawn the following teammates:

**1. Product Planner (Team Leader)**
Use Sonnet for this teammate. Spawn a Product Planner teammate to lead the team by reading Jira issues and related Confluence documentation using jira_get_issue, jira_search, confluence_search, and confluence_get_page tools. Extract requirements, clarify FMS scope vs external team responsibilities, identify current ticket priorities and acceptance criteria, then brief the entire team. After briefing, coordinate other teammates and manage the shared task list.

**2. FMS Controller**
Use Sonnet for this teammate. Require plan approval before they make any changes. Spawn an FMS Controller teammate to implement FMS core logic including order management, robot assignment, and path planning. They should navigate pinky robots to point13 with proper rotation (face kitchen, yaw=π), send goal_arrived message after point13 rotation, and navigate to table after receiving food_loaded mock message. CRITICAL: Use ROS_DOMAIN_ID (11, 12, 13, 14, 15) for robot control, NOT namespaces. Each robot operates on separate domain ID in closed network. Focus on fms/fms/fms_node.py, path_planner.py, and fleet_controller.py.

**3. Backend/Main Server Lead**
Use Sonnet for this teammate. Require plan approval before they make any changes. Spawn a Backend Lead teammate to handle Main Server ROS2 + TCP + PostgreSQL integration. They should route messages between GUI, FMS, and external teams, handle goal_arrived, precision_parked, and food_loaded messages, implement skip mode for testing (mock external messages), and ensure proper ROS2 communication across different domain IDs. Focus on app/backend/main_server/.

**4. Communication Validator**
Use Haiku for this teammate. Spawn a Communication Validator to test all TCP and ROS2 communication endpoints. They should verify goal_arrived, precision_parked, and food_loaded message protocols, create mock message generators for skip mode testing, test ROS2 communication across multiple domain IDs (11-15), perform network connectivity testing on closed network, and validate domain isolation works correctly.

**5. GUI Specialist**
Use Haiku for this teammate. Spawn a GUI Specialist to implement Customer GUI order placement and delivery confirmation UI, Admin GUI fleet monitoring, TCP client integration with Main Server, and display robot status from multiple domain IDs. Focus on app/gui/customer_gui/ and app/gui/admin_gui/.

**6. Navigation Expert**
Use Sonnet for this teammate. Require plan approval before they make any changes. Spawn a Navigation Expert to handle Nav2 configuration and waypoint path planning. They should ensure point13 approach and rotation logic works correctly, verify point2→point13 (counterclockwise rotation) and point3→point13 (clockwise rotation), configure Nav2 to work with ROS_DOMAIN_ID (remove all namespace references), and update launch files to set ROS_DOMAIN_ID environment variable per robot. Focus on mobile_robot/, nav2_params.yaml, AMCL localization, and bringup_launch.py.

**7. Integration Coordinator**
Use Haiku for this teammate. Spawn an Integration Coordinator to define message protocols with external teams (precision control, robot arm), document interface specifications (precision_parked, food_loaded), design skip mode behavior for testing without external teams, and coordinate domain ID assignments with external teams. Do NOT implement precision control or robot arm logic. Ensure external teams understand domain ID communication model.

**8. Database Architect**
Use Haiku for this teammate. Spawn a Database Architect to design PostgreSQL schema for orders and robot status. They should track order states (ORDERED → AT_POINT13 → LOADING → DELIVERING → COMPLETED), store robot identification by domain ID (not namespace), and create SQLAlchemy models. Focus on database/.

**9. QA Tester**
Use Haiku for this teammate. Spawn a QA Tester to perform end-to-end integration testing with skip mode enabled. They should test complete flow (GUI order → point13 → skip → table → return), verify all messages and state transitions, test multi-robot scenarios with different domain IDs (11, 12, 13), verify domain isolation (robots don't interfere with each other), and create test scenarios and validation scripts.

**10. DevOps & Documentation**
Use Haiku for this teammate. Spawn a DevOps teammate to manage network_config.yaml and fms_config.yaml. They should update configuration files to use ROS_DOMAIN_ID instead of namespaces, document domain ID assignments (pinky1=11, pinky2=12, pinky3=13, arm1=14, arm2=15), handle robot file synchronization (robot_file_sync.py), update CLAUDE.md with ROS_DOMAIN_ID setup instructions and skip mode procedures, ensure all launch files set ROS_DOMAIN_ID correctly, and remove namespace-based configuration from all config files.

## Critical Requirements

- Product Planner must start first and brief the team before implementation begins
- FMS scope is LIMITED to: point13 navigation, table delivery, parking return
- External teams handle: precision parking and robot arm (skip these in tests)
- All teammates requiring plan approval must submit plans before coding
- MANDATORY: Remove ALL namespace usage, use ROS_DOMAIN_ID (11-15) for robot isolation
- Each robot runs on separate domain ID in closed network WiFi
- Update all configuration, launch files, and code to use domain IDs

---

**Ready to start? The Product Planner will lead the charge!**
